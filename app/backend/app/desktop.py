"""Entry point for the packaged desktop app (see PyInstaller build)."""

from __future__ import annotations

import socket
import threading
import time

import uvicorn
import webview

from app.main import app

HOST = "127.0.0.1"
# Matches the Docker backend's port so an existing Spotify app registration's
# redirect URI (http://127.0.0.1:8000/spotify/callback) works unmodified here too.
PORT = 8000


def _run_server() -> None:
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_for_server(timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)


def main() -> None:
    threading.Thread(target=_run_server, daemon=True).start()
    _wait_for_server()
    webview.create_window("Dashboard of My Life", f"http://{HOST}:{PORT}", width=1280, height=860)
    webview.start()


if __name__ == "__main__":
    main()
