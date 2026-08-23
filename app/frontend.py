from __future__ import annotations

import os
import re
from typing import List
from flask import Flask, render_template, request, session, jsonify

from app.agent import SupportAgent


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key")
agent = SupportAgent()


_ORDER_RE = re.compile(r"(ORD-)(\d{2,})")


def _mask_pii(text: str) -> str:
    if not text:
        return text

    def repl(m: re.Match) -> str:
        prefix = m.group(1)
        digits = m.group(2)
        keep = 4
        if len(digits) <= keep:
            return prefix + "*" * len(digits)
        return prefix + "*" * (len(digits) - keep) + digits[-keep:]

    return _ORDER_RE.sub(repl, text)


def _session_history() -> List[dict]:
    return session.setdefault("history", [])


@app.route("/", methods=["GET"]) 
def index():
    history = _session_history()
    # Render the page; JS will call /api/query for actions
    return render_template("index.html", history=history)


@app.route("/api/query", methods=["POST"]) 
def api_query():
    payload = request.get_json() or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400

    history = _session_history()
    # pass a shallow copy of history to the agent
    resp = agent.respond(message, history=list(history))

    # Mask PII in debug fields before returning to UI
    resp_safe = dict(resp)
    for key in ("debug_log", "tool_calls"):
        if key in resp_safe and isinstance(resp_safe[key], str):
            resp_safe[key] = _mask_pii(resp_safe[key])

    # Append to session history
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": resp_safe.get("answer", "")})
    session["history"] = history

    return jsonify(resp_safe)


@app.route("/api/clear", methods=["POST"]) 
def api_clear():
    session.pop("history", None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
