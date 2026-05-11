#!/usr/bin/env python3
import json
from argparse import ArgumentParser
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "http://localhost:8000"


def request(method, path, data=None, token=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc


def main():
    global BASE_URL
    parser = ArgumentParser(description="Run a minimal Lifeline backend smoke test.")
    parser.add_argument("base_url", nargs="?", default=None)
    parser.add_argument("--base-url", dest="base_url_option", default=None)
    args = parser.parse_args()
    BASE_URL = (args.base_url_option or args.base_url or BASE_URL).rstrip("/")

    print("Checking health")
    request("GET", "/health")

    print("Creating seeker and volunteer tokens")
    seeker = request("POST", "/v1/auth/anonymous", {"role": "seeker"})["token"]
    volunteer = request("POST", "/v1/auth/anonymous", {"role": "volunteer"})["token"]

    print("Marking volunteer available")
    request("POST", "/v1/volunteer/status", {"available": True}, token=volunteer)

    print("Requesting seeker session")
    session = request("POST", "/v1/session/request", {"client_capabilities": {"platform": "smoke"}}, token=seeker)
    session_id = session["session_id"]

    print("Checking volunteer pending assignment")
    pending = request("GET", "/v1/volunteer/pending", token=volunteer)
    if not pending or pending[0]["session_id"] != session_id:
        raise RuntimeError(f"Expected pending session {session_id}, got {pending}")

    print("Accepting session")
    accepted = request("POST", "/v1/volunteer/accept", {"session_id": session_id}, token=volunteer)
    if accepted["status"] != "ACTIVE":
        raise RuntimeError(f"Expected ACTIVE session, got {accepted}")

    print("Smoke test passed")


if __name__ == "__main__":
    main()
