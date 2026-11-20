import httpx
import pytest

from app.main import app
from app.model import MODEL_FILE
from scripts.local_server import running_backend


def test_the_backend_is_stopped_even_after_an_error(fixture_model_dir):
    with pytest.raises(ZeroDivisionError):
        with running_backend(app) as server:
            assert httpx.get(f"{server}/docs").status_code == 200
            1 / 0

    # Nothing answers any more. Windows can report that as a timeout rather than a
    # refused connection, so either counts.
    with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
        httpx.get(f"{server}/docs", timeout=2)


# uvicorn ends its own thread when start-up fails, which pytest reports as a warning.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_a_backend_that_cannot_start_says_so(fixture_model_dir):
    (fixture_model_dir / MODEL_FILE).unlink()

    with pytest.raises(RuntimeError, match="didn't start"):
        with running_backend(app):
            pass
