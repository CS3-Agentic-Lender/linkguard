from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.links import clean_link
from app.model import load_model, model_dir, phishing_score
from app.risk import RiskLevel, load_cutoffs, risk_level


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the cut-offs, the scaler and the model once, before the first /scan call,
    # and keep them for every call after. A missing file stops start-up and names it.
    # The cut-offs go first because they are quick to read and check.
    app.state.cutoffs = load_cutoffs(model_dir())
    app.state.model = load_model(model_dir())
    yield


app = FastAPI(title="LinkGuard", lifespan=lifespan)


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
    try:
        cleaned = clean_link(request.url)
    except ValueError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})

    # The link is only ever handled as text: it is never opened or fetched.
    # Cleaned link, then the shared feature extractor, then the scaler, then the model.
    score = phishing_score(app.state.model, cleaned.url)

    # The reasons are filled in by the see-why step, so the list stays empty for now.
    return ScanResponse(
        url=cleaned.url,
        risk_level=risk_level(score, app.state.cutoffs),
        score=score,
        reasons=[],
        placeholder=False,
    )
