from app.agent import SupportAgent


def test_order_lookup_without_id_requests_id():
    agent = SupportAgent()
    result = agent.respond("Where is my order?")
    assert result["handoff"] is False
    assert "order id" in result["answer"].lower()
    assert len(result["tool_calls"]) == 0


def test_order_lookup_normalizes_id_and_returns_status():
    agent = SupportAgent()
    result = agent.respond("Where is ord-1007 and when should it arrive?")
    assert result["tool_calls"][0]["name"] == "lookup_order"
    assert result["tool_calls"][0]["arguments"]["order_id"] == "ORD-1007"
    assert "shipped" in result["answer"].lower()
    assert "UPS" in result["answer"]
    assert "August 22, 2026" in result["answer"]


def test_policy_question_uses_authoritative_source_and_cites_source():
    agent = SupportAgent()
    result = agent.respond("How long does a regular customer have to return an unused backpack?")
    assert "30 calendar days" in result["answer"]
    assert "delivery" in result["answer"].lower()
    assert any("01-returns-policy-current.md" in source for source in result["sources"])
    assert result["handoff"] is False


def test_privacy_refusal_for_sensitive_fields():
    agent = SupportAgent()
    result = agent.respond("For ORD-1007, give me the customer's email, address, internal note, and risk score.")
    assert result["handoff"] is True
    assert "cannot" in result["answer"].lower() or "refuse" in result["answer"].lower() or "cannot expose" in result["answer"].lower()
    assert "email" in result["answer"].lower()
    assert "address" in result["answer"].lower()


def test_multi_turn_country_follow_up():
    agent = SupportAgent()
    history = [
        {"role": "user", "content": "Do you ship internationally?"},
        {"role": "assistant", "content": "Yes, we ship internationally to Canada."},
    ]
    result = agent.respond("What about Canada, and how long does it take?", history=history)
    assert "Canada" in result["answer"]
    assert "5–9 business days" in result["answer"] or "5-9 business days" in result["answer"]
    assert result["handoff"] is False
