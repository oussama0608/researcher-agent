import asyncio
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.main import load_env, run_workflow


class Provider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"


class RunPayload(BaseModel):
    company: str
    url: Optional[str] = None
    provider: Provider = Provider.openai
    model: str = "gpt-4o-mini"


app = FastAPI(title="Cold Outreach Researcher Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/run")
async def run_agent(payload: RunPayload) -> dict:
    try:
        # Load API keys for the requested provider before running the workflow.
        load_env(payload.provider.value)
        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(
            None,
            lambda: run_workflow(
                company=payload.company,
                url=payload.url,
                model=payload.model,
                provider=payload.provider.value,
                interactive=False,
                verbose=False,
            ),
        )
        return {
            "summary": state.get("summary"),
            "email_draft": state.get("email_draft"),
            "approved": state.get("approved"),
            "log": state.get("log", []),
        }
    except Exception as exc:  # pragma: no cover - thin exception wrapper
        raise HTTPException(status_code=500, detail=str(exc))
