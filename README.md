# Cold Outreach Researcher Agent (LangGraph)

LangGraph-based autonomous agent that researches a target company (via Tavily search + landing page scrape), summarizes findings, drafts a personalized cold email, and pauses for human approval before a mock send.

## Features
- **LangGraph workflow**: deterministic state machine with explicit nodes for search, scraping, drafting, review, and send.
- **Tavily search**: two focused queries (`news`, `what they do`) to gather fresh intel.
- **Scraping**: BeautifulSoup pulls plain text from the company homepage/About page.
- **LLM drafting**: OpenAI (or Anthropic drop-in) crafts the summary and cold email using the collected context.
- **Human-in-the-loop**: the graph stops and asks for approval before "sending" the email.

## Quickstart (CLI)
1) **Install deps** (Python 3.10+):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2) **Configure env** (copy/edit):
```bash
cp .env.example .env
```
Populate `TAVILY_API_KEY` and an LLM key (`OPENAI_API_KEY` or set up Anthropic).

3) **Run**:
```bash
python -m src.main "Acme Corp" --url https://www.acme.com
# Swap providers/models if you like:
python -m src.main "Acme Corp" --provider anthropic --model claude-3-sonnet-20240229
```
The agent will search, scrape, draft an email, pause for your approval, and then perform a mock send.

## Web UI (local demo)
1) **Start API**:
```bash
uvicorn src.server:app --reload --port 8000
```
2) **Start frontend** (Vite/React):
```bash
cd frontend
npm install
npm run dev  # defaults to http://localhost:5173
```
3) Open the browser, enter a company name/URL, run the agent, review the draft, optionally edit, and click **Approve & mock send**.

Frontend hits the FastAPI backend at `http://localhost:8000` by default; override via `VITE_API_BASE` in `.env`.

## Configuration notes
- **LLM provider**: defaults to OpenAI GPT-4o-mini; switch models at runtime via `--provider/--model`.
- **Search depth**: tweak `RESULTS_PER_QUERY` and `MAX_TEXT_CHARS` constants as needed.
- **Persistence**: minimal stateless demo; LangGraph makes it easy to add checkpoints if you want resumability.

## Repo layout
- `src/main.py` — LangGraph workflow, CLI entrypoint.
- `requirements.txt` — Python dependencies.
- `.env.example` — environment variable template.

## Safety & control
The approval node prints the drafted email and asks for explicit `y/n` confirmation before the mock send step. This makes it easy to add additional guardrails (PII checks, tone filters, etc.) inside `approval_node` in `src/main.py`.
