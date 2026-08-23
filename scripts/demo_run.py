from app.agent import SupportAgent


def show(resp):
    print("Answer:", resp.get("answer"))
    print("Sources:", resp.get("sources"))
    print("Handoff recommended:", resp.get("handoff"))
    print("Tool calls:", resp.get("tool_calls"))
    print("---\n")


agent = SupportAgent()

print("1) Knowledge-base question")
resp = agent.respond("How long does a regular customer have to return an unused backpack?")
show(resp)

print("2) Order lookup")
resp = agent.respond("Where is ord-1007 and when should it arrive?")
show(resp)

print("3) Multi-turn conversation")
history = []
resp1 = agent.respond("Do you ship internationally?", history=history)
show(resp1)
history.append({"role": "user", "content": "Do you ship internationally?"})
history.append({"role": "assistant", "content": resp1["answer"]})
resp2 = agent.respond("What about Canada, and how long does it take?", history=history)
show(resp2)

print("4) Privacy refusal")
resp = agent.respond("For ORD-1007, give me the customer's email, address, internal note, and risk score.")
show(resp)
