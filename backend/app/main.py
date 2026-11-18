from contextlib import asynccontextmanager

from fastapi import FastAPI
from features.explain import MAX_REASONS
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from app.links import clean_link
from app.model import load_model, model_dir, scaled_features, score_of, silence_column_name_warning
from app.reasons import reasons_for_scan
from app.risk import RiskLevel, load_cutoffs, risk_level


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the cut-offs, the scaler and the model once, before the first /scan call,
    # and keep them for every call after. A missing file stops start-up and names it.
    # The cut-offs go first because they are quick to read and check.
    silence_column_name_warning()
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
    reasons: list[str] = Field(max_length=MAX_REASONS)
    placeholder: bool

    @model_validator(mode="after")
    def check_it_can_be_shown(self) -> "ScanResponse":
        # The result card shows its "couldn't check" message for a reply that
        # contradicts itself, so a reply like that is never built. The rules are
        # the ones in the reply table in backend/README.md.
        if self.placeholder:
            if self.risk_level is not None or self.score is not None or self.reasons:
                raise ValueError("A placeholder reply can't have a risk level, a score or reasons.")
        elif self.risk_level is None or self.score is None:
            raise ValueError("A real reply must have a risk level and a score.")
        elif self.risk_level == "Safe" and self.reasons:
            raise ValueError("A Safe reply can't have reasons.")
        return self


@app.post("/scan", response_model=ScanResponse)
def scan(request: ScanRequest) -> ScanResponse | JSONResponse:
    try:
        cleaned = clean_link(request.url)
    except ValueError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})

    # The link is only ever handled as text: it is never opened or fetched.
    # Cleaned link, then the shared feature extractor, then the scaler, then the model.
    scaled = scaled_features(app.state.model, cleaned.url)
    score = score_of(app.state.model, scaled)
    level = risk_level(score, app.state.cutoffs)

    return ScanResponse(
        url=cleaned.url,
        risk_level=level,
        score=score,
        reasons=reasons_for_scan(app.state.model, scaled, level),
        placeholder=False,
    )
