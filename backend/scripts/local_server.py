"""Start the backend for real, with uvicorn on a free port on 127.0.0.1, and stop it after.

The end-to-end tests and the timing run both use this, so they start the server the same way.
"""

import socket
import threading
import time
from contextlib import contextmanager

import uvicorn

START_TIMEOUT_SECONDS = 30
STOP_TIMEOUT_SECONDS = 10
POLL_SECONDS = 0.05


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def running_backend(app):
    """The backend's base URL while it runs. It is stopped on the way out, even after an error.

    Raises RuntimeError if it doesn't start, for example because a model file is missing.
    """
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            server.should_exit = True
            raise RuntimeError("The backend didn't start. Check the model files and cutoffs.json in the model folder.")
        time.sleep(POLL_SECONDS)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=STOP_TIMEOUT_SECONDS)
