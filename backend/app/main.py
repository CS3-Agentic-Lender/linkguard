from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="LinkGuard")

RiskLevel = Literal["Safe", "Suspicious", "High risk"]


class ScanRequest(BaseModel):
    url: str


class ScanResponse(BaseModel):
    """The one reply shape the page and the trained model both use."""

    url: str
    risk_level: RiskLevel | None
    score: float | None = Field(ge=0, le=1)
    reasons: list[str] = Field(max_length=3)
    placeholder: bool


@app.post("/scan", response_model=ScanResponse)
def scan(request: ScanRequest) -> ScanResponse | JSONResponse:
    if not request.url.strip():
        return JSONResponse(status_code=400, content={"error": "Paste a link first"})

    # The link is only ever handled as text: it is never opened or fetched.
    # Until the trained model is served, reply with a placeholder and never
    # a made-up risk level or score.
    return ScanResponse(
        url=request.url,
        risk_level=None,
        score=None,
        reasons=[],
        placeholder=True,
    )
