from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.agent import SupportAgent


def _normalize(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _contains_all(answer: str, wanted: list[str]) -> bool:
    lower = _normalize(answer)
    return all(item.lower() in lower for item in wanted)


def _contains_any(answer: str, wanted: list[str]) -> bool:
    lower = _normalize(answer)
    return any(item.lower() in lower for item in wanted)


def _run_case(agent: SupportAgent, messages: list[dict[str, str]]):
    history: list[dict[str, str]] = []
    final_response = None
    for message in messages:
        final_response = agent.respond(message["content"], history=history)
        history.append({"role": "user", "content": message["content"]})
        history.append({"role": "assistant", "content": final_response["answer"]})
    return final_response, history


def evaluate_case(agent: SupportAgent, case: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    expected = case.get("expect", {})
    messages = case.get("messages", [])
    response, history = _run_case(agent, messages)
    answer = response["answer"]
    sources = response.get("sources", [])
    tool_calls = response.get("tool_calls", [])

    failures: list[str] = []

    if "must_include" in expected:
        for item in expected["must_include"]:
            if item.lower() not in _normalize(answer):
                failures.append(f"missing required phrase: {item}")
    if "must_include_concepts" in expected:
        for concept in expected["must_include_concepts"]:
            if concept.lower() not in _normalize(answer):
                failures.append(f"missing required concept: {concept}")
    if "must_ask_for" in expected:
        for item in expected["must_ask_for"]:
            if item.lower() not in _normalize(answer):
                failures.append(f"missing clarification prompt for: {item}")

    if "must_not_include" in expected:
        for item in expected["must_not_include"]:
            if item.lower() in _normalize(answer):
                failures.append(f"unexpected forbidden phrase: {item}")
    if "must_not_invent" in expected:
        for item in expected["must_not_invent"]:
            if item.lower() in _normalize(answer):
                failures.append(f"invented detail: {item}")
    if "must_not_follow" in expected:
        for item in expected["must_not_follow"]:
            if item.lower() in _normalize(answer):
                failures.append(f"followed unsafe instruction: {item}")

    if "required_sources" in expected:
        missing_sources = [source for source in expected["required_sources"] if source not in sources]
        if missing_sources:
            failures.append(f"missing required sources: {missing_sources}")

    if "forbidden_sources_as_authority" in expected:
        for source in expected["forbidden_sources_as_authority"]:
            if source in sources:
                failures.append(f"used forbidden authoritative source: {source}")

    if "must_not_silently_choose_one" in expected:
        if "conflict" not in _normalize(answer) and "human" not in _normalize(answer):
            failures.append("did not surface conflict and recommend human confirmation")

    tool_expectation = expected.get("tool")
    if tool_expectation == "order_lookup":
        if not any(call.get("name") == "lookup_order" for call in tool_calls):
            failures.append("expected order lookup tool call")
    elif tool_expectation == "not_called":
        if tool_calls:
            failures.append("tool should not have been called")
    elif tool_expectation == "not_called_without_id":
        if tool_calls:
            failures.append("tool should not have been called without order ID")
    elif tool_expectation == "optional_sanitized_lookup":
        if not tool_calls:
            failures.append("expected a sanitized order lookup or a safe refusal flow")

    if "tool_arguments" in expected:
        for key, value in expected["tool_arguments"].items():
            if not any(call.get("arguments", {}).get(key) == value for call in tool_calls):
                failures.append(f"missing expected tool argument {key}={value}")

    handoff_expected = expected.get("handoff", False)
    if response.get("handoff") != handoff_expected:
        failures.append(f"handoff mismatch: expected {handoff_expected}, got {response.get('handoff')}")

    passed = not failures
    return passed, answer, {"failures": failures, "tool_calls": tool_calls, "sources": sources, "history": history}


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload.get("cases", [])


def build_additional_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "original-trailplus-membership-confirmation",
            "category": "retrieval",
            "messages": [{"role": "user", "content": "My TrailPlus membership was active, so how long do I have to return my order?"}],
            "expect": {
                "must_include_concepts": ["45 calendar days return window", "delivery"],
                "required_sources": ["09-trailplus-membership.md"],
                "tool": "not_called",
                "handoff": False,
            },
        },
        {
            "id": "original-gift-card-is-final-sale",
            "category": "groundedness",
            "messages": [{"role": "user", "content": "Can I return a gift card if I changed my mind?"}],
            "expect": {
                "must_include_concepts": ["gift cards are always final sale", "not eligible for change-of-mind returns"],
                "required_sources": ["03-final-sale-and-promotions.md"],
                "tool": "not_called",
                "handoff": False,
            },
        },
        {
            "id": "original-order-status-unknown-id",
            "category": "tool-use",
            "messages": [{"role": "user", "content": "Please check ORD-9999."}],
            "expect": {
                "must_include_concepts": ["couldn’t find that order", "check the order ID or contact support"],
                "tool": "order_lookup",
                "handoff": True,
            },
        },
        {
            "id": "original-cancelled-status-wins-over-stale-eta",
            "category": "tool-reliability",
            "messages": [{"role": "user", "content": "When will order ORD-1004 arrive?"}],
            "expect": {
                "must_include_concepts": ["cancelled", "will not be shipped"],
                "must_not_include": ["August 16, 2026"],
                "tool": "order_lookup",
                "handoff": False,
            },
        },
        {
            "id": "original-support-escalation-no-guess",
            "category": "abstention",
            "messages": [{"role": "user", "content": "Are all fabrics and adhesives in all your bags vegan?"}],
            "expect": {
                "must_include_concepts": ["insufficient to confirm", "human support specialist"],
                "tool": "not_called",
                "handoff": True,
            },
        },
    ]


def run_evaluation():
    agent = SupportAgent()
    base_path = Path(__file__).resolve().parents[1]
    cases = load_cases(base_path / "evaluation" / "visible-cases.json") + build_additional_cases()
    categories: defaultdict[str, list[bool]] = defaultdict(list)
    details = []

    for case in cases:
        passed, answer, meta = evaluate_case(agent, case)
        categories[case.get("category", "unknown")].append(passed)
        details.append({
            "id": case.get("id"),
            "category": case.get("category", "unknown"),
            "passed": passed,
            "answer": answer,
            "meta": meta,
        })

    print("\n=== Evaluation Report ===")
    print(f"Total cases: {len(cases)}")
    print(f"Passing cases: {sum(1 for item in details if item['passed'])}")
    print(f"Failure cases: {sum(1 for item in details if not item['passed'])}\n")

    for category in sorted(categories):
        results = categories[category]
        print(f"{category}: {sum(results)}/{len(results)} passed")

    print("\nIndividual results:")
    for item in details:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"- {status}: {item['id']} ({item['category']})")
        if not item["passed"]:
            for failure in item["meta"]["failures"]:
                print(f"    * {failure}")

    return details


if __name__ == "__main__":
    run_evaluation()
