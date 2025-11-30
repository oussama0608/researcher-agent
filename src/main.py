from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from tavily import TavilyClient

# Tunables
RESULTS_PER_QUERY = 4
SCRAPE_TIMEOUT = 12
MAX_TEXT_CHARS = 6000


def append_log(state: AgentState, message: str) -> List[str]:
    verbose = state.get("verbose", True)
    log = list(state.get("log", []))
    log.append(message)
    if verbose:
        print(message)
    return log


class AgentState(TypedDict, total=False):
    company: str
    company_url: Optional[str]
    queries: List[str]
    search_results: List[Dict[str, Any]]
    website_content: str
    summary: Optional[str]
    email_draft: Optional[str]
    approved: Optional[bool]
    interactive: bool
    verbose: bool
    log: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LangGraph Cold Outreach Researcher Agent",
    )
    parser.add_argument(
        "company",
        help="Target company name (or domain) to research.",
    )
    parser.add_argument(
        "--url",
        help="Optional company homepage URL to prioritize for scraping.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="LLM model id (OpenAI); swap here if using another provider.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic"],
        default="openai",
        help="LLM provider to use.",
    )
    return parser.parse_args()


def load_env(provider: str) -> None:
    load_dotenv()
    if not os.getenv("TAVILY_API_KEY"):
        raise RuntimeError("Missing TAVILY_API_KEY. Set it in .env.")
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Missing OPENAI_API_KEY for OpenAI provider.")
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Missing ANTHROPIC_API_KEY for Anthropic provider.")


def generate_queries_node(state: AgentState) -> AgentState:
    company = state["company"]
    queries = [
        f"{company} latest news",
        f"{company} what they do overview",
    ]
    log = append_log(state, f"[generate_queries] Prepared queries: {queries}")
    return {"queries": queries, "log": log}


def pick_first_url(search_results: List[Dict[str, Any]]) -> Optional[str]:
    for block in search_results:
        for item in block.get("results", []):
            url = item.get("url")
            if url:
                return url
    return None


def search_node(state: AgentState) -> AgentState:
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    gathered: List[Dict[str, Any]] = []
    log = list(state.get("log", []))
    log_state = {**state, "log": log}
    for query in state["queries"]:
        log = append_log(log_state, f"[search] Tavily query -> {query}")
        log_state["log"] = log
        resp = client.search(query=query, max_results=RESULTS_PER_QUERY)
        gathered.append(
            {
                "query": query,
                "results": resp.get("results", []),
            }
        )
    resolved_url = state.get("company_url") or pick_first_url(gathered)
    if resolved_url:
        log = append_log({**log_state, "log": log}, f"[search] Using '{resolved_url}' as primary URL")
    else:
        log = append_log({**log_state, "log": log}, "[search] No URL found; scraping step will be skipped.")
    return {"search_results": gathered, "company_url": resolved_url, "log": log}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"https://{url}"
    return url


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text_nodes = soup.find_all(["h1", "h2", "h3", "p", "li"])
    text = " ".join(node.get_text(" ", strip=True) for node in text_nodes)
    return textwrap.shorten(" ".join(text.split()), width=MAX_TEXT_CHARS, placeholder=" ...")


def find_about_link(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    for tag in soup.find_all("a", href=True):
        href = tag["href"].lower()
        if "about" in href:
            return urljoin(base_url, tag["href"])
    return None


def scrape_page(url: str) -> str:
    headers = {"User-Agent": "researcher-agent/0.1"}
    response = requests.get(url, headers=headers, timeout=SCRAPE_TIMEOUT)
    response.raise_for_status()
    return extract_text_from_html(response.text)


def scrape_node(state: AgentState) -> AgentState:
    url = state.get("company_url")
    log = list(state.get("log", []))
    log_state = {**state, "log": log}
    if not url:
        log = append_log(log_state, "[scrape] Skipping: no URL available.")
        return {"website_content": "", "log": log}
    normalized = normalize_url(url)
    log = append_log(log_state, f"[scrape] Fetching {normalized}")
    log_state["log"] = log
    try:
        primary_html = requests.get(normalized, timeout=SCRAPE_TIMEOUT, headers={"User-Agent": "researcher-agent/0.1"})
        primary_html.raise_for_status()
    except Exception as exc:
        log = append_log({**log_state, "log": log}, f"[scrape] Failed to fetch homepage: {exc}")
        return {"website_content": "", "log": log}

    soup = BeautifulSoup(primary_html.text, "html.parser")
    base_text = extract_text_from_html(primary_html.text)

    about_text = ""
    about_link = find_about_link(soup, normalized)
    if about_link:
        try:
            log = append_log({**log_state, "log": log}, f"[scrape] Fetching About page -> {about_link}")
            about_text = scrape_page(about_link)
        except Exception as exc:
            log = append_log({**log_state, "log": log}, f"[scrape] Failed to fetch About page: {exc}")

    combined = (base_text + "\n\n" + about_text).strip()
    return {"website_content": combined, "log": log}


def format_search_snippets(search_results: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for block in search_results:
        lines.append(f"- Query: {block['query']}")
        for item in block.get("results", []):
            snippet = item.get("content") or item.get("snippet") or ""
            title = item.get("title") or "Untitled result"
            url = item.get("url") or ""
            lines.append(f"  * {title} — {textwrap.shorten(snippet, width=220, placeholder=' ...')} ({url})")
    return "\n".join(lines)


def parse_summary_and_email(raw: str) -> Dict[str, str]:
    content = raw.strip()
    if "EMAIL:" in content:
        summary_part, email_part = content.split("EMAIL:", maxsplit=1)
        summary = summary_part.replace("SUMMARY:", "").strip()
        email = "EMAIL:\n" + email_part.strip()
        return {"summary": summary, "email_draft": email}
    return {"summary": content, "email_draft": content}


def make_llm(provider: str, model: str):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=0.35)
    return ChatOpenAI(model=model, temperature=0.35)


def make_drafting_node(model: str, provider: str):
    llm = make_llm(provider, model)

    def drafting_node(state: AgentState) -> AgentState:
        research_snippets = format_search_snippets(state["search_results"])
        context_block = f"""Research findings:
{research_snippets}

Website content:
{state.get('website_content', '')}
"""
        prompt = f"""Using the research below, produce two sections:
SUMMARY:
- Three crisp bullets describing what the company does and any timely news.

EMAIL:
- A concise cold email with a subject line and 3-5 sentence body that connects our AI automation services to their needs/news.
- Write in a helpful, non-pushy tone. Keep under 180 words.

Company: {state['company']}
{context_block}
"""
        log = append_log(state, f"[draft] Calling LLM model '{model}' via {provider}")
        response = llm.invoke(
            [
                SystemMessage(
                    content="You are a sales researcher who writes accurate, upbeat summaries and tailored outreach emails.",
                ),
                HumanMessage(content=prompt),
            ]
        )
        parsed = parse_summary_and_email(str(response.content))
        log = append_log({**state, "log": log}, "[draft] LLM response received")
        return {"summary": parsed["summary"], "email_draft": parsed["email_draft"], "log": log}

    return drafting_node


def approval_node(state: AgentState) -> AgentState:
    if state.get("approved") is not None:
        return {}
    email = state.get("email_draft") or ""
    interactive = state.get("interactive", True)

    if not interactive:
        log = append_log(state, "[approval] Awaiting human approval (non-interactive mode).")
        return {"approved": False, "email_draft": email, "log": log}

    print("\n===== EMAIL DRAFT FOR APPROVAL =====\n")
    print(email)
    print("\n====================================\n")
    choice = input("Approve and mock-send? [y/N/edit]: ").strip().lower()
    if choice == "edit":
        print("Enter your edited email draft. Finish with Ctrl-D (Linux/macOS) or Ctrl-Z then Enter (Windows).\n")
        edited = sys.stdin.read().strip()
        email = edited or email
        approved = True
    else:
        approved = choice in ("y", "yes")
    log = append_log(state, f"[approval] {'Approved' if approved else 'Not approved'} by user input.")
    return {"email_draft": email, "approved": approved, "log": log}


def mock_send_node(state: AgentState) -> AgentState:
    message = "[send] Mock sending email... ✅" if state.get("approved") else "[send] Not sending (not approved)."
    log = append_log(state, message)
    return {"log": log}


def build_graph(model: str, provider: str):
    builder = StateGraph(AgentState)
    builder.add_node("generate_queries", generate_queries_node)
    builder.add_node("search", search_node)
    builder.add_node("scrape", scrape_node)
    builder.add_node("draft", make_drafting_node(model, provider))
    builder.add_node("approval", approval_node)
    builder.add_node("send", mock_send_node)

    builder.set_entry_point("generate_queries")
    builder.add_edge("generate_queries", "search")
    builder.add_edge("search", "scrape")
    builder.add_edge("scrape", "draft")
    builder.add_edge("draft", "approval")
    builder.add_edge("approval", "send")
    builder.add_edge("send", END)

    return builder.compile()


def run_workflow(
    company: str,
    url: Optional[str],
    model: str,
    provider: str,
    interactive: bool = True,
    verbose: bool = True,
) -> AgentState:
    initial_state: AgentState = {
        "company": company,
        "company_url": url,
        "queries": [],
        "search_results": [],
        "website_content": "",
        "interactive": interactive,
        "verbose": verbose,
        "log": [],
    }
    graph = build_graph(model, provider)
    final_state = graph.invoke(initial_state)
    return final_state


def main() -> None:
    args = parse_args()
    load_env(args.provider)
    final_state = run_workflow(
        company=args.company,
        url=args.url,
        model=args.model,
        provider=args.provider,
        interactive=True,
        verbose=True,
    )
    print("\n===== RUN COMPLETE =====")
    print(f"Company: {args.company}")
    if final_state.get("summary"):
        print("\nSummary:\n", final_state["summary"])
    if final_state.get("email_draft"):
        print("\nEmail draft:\n", final_state["email_draft"])
    print(f"\nApproved: {final_state.get('approved')}")


if __name__ == "__main__":
    main()
