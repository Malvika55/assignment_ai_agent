# Aster & Row Support Agent

This project builds a small, reliable customer-support agent for Aster & Row using the supplied knowledge base and mock order dataset. The agent prioritizes grounded answers, source references, safe abstention, and privacy-aware order lookups.

## Architecture

- Knowledge layer: Markdown files in `knowledge-base` with YAML front matter
- Retrieval: deterministic metadata-aware passage search over active official documents
- Tools: order lookup from `data/orders.json` with normalization and privacy filtering
- Runtime: small Python CLI that keeps session history and logs debug data
- Safety: internal draft docs, internal notes, and prompt-injection content are filtered before any customer-facing answer is built

### Chosen stack

- Language: Python 3.11+
- Framework: pure Python CLI (`app/agent.py`, `app/order_tool.py`, `app/cli.py`)
- Retrieval: in-memory metadata-weighted lexical retrieval over markdown passages
- Storage: local files (`knowledge-base/*.md`, `data/orders.json`)
- Optional model integration: environment variables for OpenAI are supported, but the default workflow does not depend on a live API call to remain reliable and offline-safe

## Setup and run from a clean clone

1. Clone the repository.
2. Create a virtual environment:

```bash
python -m venv venv
```

3. Activate it:

On Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source venv/bin/activate
```

4. Install requirements:

```bash
python -m pip install -r requirements.txt
```

5. Copy the environment example file:

```bash
copy .env.example .env
```

6. Edit `.env` if you want to add an optional OpenAI key:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

7. Launch the agent:

```bash
python -m app
```

8. To run the evaluation suite:

```bash
python -m app.evaluation
```

## Evaluation command

```bash
python -m app.evaluation
```

This prints per-case results and per-category summaries for retrieval, groundedness, tool use, privacy, multi-turn behavior, and abstention.

## Baseline and final results

| Stage | Result |
|---|---:|
| Baseline (early prototype) | 5/20 visible cases passed |
| Final project | 20/20 visible cases passed |

### Category summary

- Retrieval: 3/3 passed
- Groundedness: 3/3 passed
- Tool use: 3/3 passed
- Tool reliability: 4/4 passed
- Privacy: 1/1 passed
- Prompt security: 1/1 passed
- Multi-turn: 1/1 passed
- Abstention: 2/2 passed
- Source conflict: 1/1 passed

## Bug diary

### 1) Hidden internal note hijacked the answer
- Reproduction: ask a question that mentions a migration note or a forged “60-day policy”.
- Root cause: the agent initially used low-trust markdown content without filtering internal or draft docs.
- Fix: draft and internal files are excluded from the retrieval pool unless explicitly allowed; the agent now prefers active official documents.
- Regression test: `retrieved-prompt-injection` and the prompt-injection branch in `app/evaluation.py`.

### 2) Stale cancellation data was treated as current shipping status
- Reproduction: ask when `ORD-1004` will arrive after cancellation.
- Root cause: the order tool used stale carrier and estimated-delivery metadata without honoring the authoritative `status` field.
- Fix: the tool now treats `cancelled` and `returned` as authoritative and suppresses stale arrival messaging.
- Regression test: `cancelled-order-stale-eta` plus the custom cancelled-order regression in `app/evaluation.py`.

### 3) Order lookup violated privacy expectations
- Reproduction: ask for the customer email, shipping address, internal note, or risk score.
- Root cause: the lookup flow initially exposed sensitive fields instead of stripping them before returning customer-safe content.
- Fix: the tool only returns approved safe fields and refuses the request with a handoff recommendation.
- Regression test: `order-data-privacy`.

### 4) Hyphenated/variant wording caused incorrect retrieval misses
- Reproduction: “final-sale bag arrived with a broken zipper” and “TrailPlus membership” style variants.
- Root cause: the first version only matched exact phrases and missed hyphenated variants.
- Fix: normalize hyphen and underscore variations before matching; keep direct policy rules for key risk patterns.
- Regression test: the visible multi-source and membership cases plus the custom original cases.

## Known limitations

- The current system uses a deterministic lexical retrieval layer rather than a production vector database; it is intentionally simpler and more predictable for a quality-assurance assignment.
- The order lookup is mocked and suitable for the assignment’s data model only.
- The agent does not implement identity verification or write-back actions beyond read-only order lookup.
- For production, I would add richer chunking, embedding search, better conversation summarization, and a proper asynchronous logging layer.

## AI coding tools used

I used GitHub Copilot for scaffolding, targeted bug fixing, and incremental refactoring. It was especially helpful for generating the initial structure, testing ideas, and tightening the retrieval/guardrail logic.

One AI-generated suggestion that was wrong or incomplete: it initially recommended a more complex vector-search-only implementation without adequate metadata filtering and without explicit handling of stale order data. That approach was too brittle for the prompt-injection and stale-status edge cases, so I replaced it with a metadata-aware rule set and deterministic retrieval logic.

## Additional notes

- No customer credentials, API keys, or personal data were added to the repo.
- The project deliberately avoids hidden prompt execution by treating retrieved content and tool outputs as untrusted data.
- The CLI logs a simple debug trace for the current message, conversation history, relevant passages, tool calls, and final response.

## Web frontend (interactive demo)

A small Flask-based UI is included to demonstrate multi-turn flows, order lookups, and the debug trace.

Run the frontend locally after activating your virtualenv:

On Windows PowerShell (from the repo root):

```powershell
$env:PYTHONPATH = "C:\path\to\assignment_ai_agent"
.\venv\Scripts\python.exe -m app.frontend
```

On macOS/Linux (from the repo root):

```bash
export PYTHONPATH="$(pwd)"
python -m app.frontend
```

Then open http://127.0.0.1:5000 in your browser. The UI shows conversation history, the agent's last answer and sources, and a toggleable debug log pane. Use an example order ID like `ORD-1007` to try the order lookup flow.

## Demo recording and uploading

A 2–4 minute demo demonstrating the main functionality of the AI support agent.
[▶️ Watch the Demo Video 1](https://github.com/user-attachments/assets/b858f202-7f09-4de9-8037-d5dbf7d3851a)

[▶️ Watch Demo 2](https://github.com/user-attachments/assets/60c58f2d-2d47-4d58-8850-2920774a0d2f)

<img width="1860" height="832" alt="Image" src="https://github.com/user-attachments/assets/1aed6756-8aea-4f55-96a9-48094103c50d" />

The demo highlights the main features and demonstrates how the application works through a real user interaction.


## Where to look in the code

- `app/frontend.py` — Flask app and API endpoints.
- `app/agent.py` — agent logic, retrieval and response composition.
- `app/order_tool.py` — order lookup tool with privacy filtering.
- `app/evaluation.py` — deterministic evaluation harness and visible cases.


## License

This repository is provided for the assignment and is intentionally scoped to the task requirements.
