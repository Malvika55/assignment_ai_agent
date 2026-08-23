from __future__ import annotations

import argparse
import json

from app.agent import SupportAgent


def main():
    parser = argparse.ArgumentParser(description="Aster & Row support agent")
    parser.add_argument("--debug", action="store_true", help="Print debug information for each turn.")
    args = parser.parse_args()

    agent = SupportAgent()
    history = []
    print("Aster & Row Support Agent")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit", "q"}:
            break
        if not user_input:
            continue
        response = agent.respond(user_input, history=history)
        print(f"Agent: {response['answer']}")
        if response.get("sources"):
            print(f"Sources: {', '.join(response['sources'])}")
        if response.get("handoff"):
            print("Handoff: recommended")
        if args.debug:
            print(json.dumps(response.get("debug_log", {}), indent=2))
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response["answer"]})


if __name__ == "__main__":
    main()
