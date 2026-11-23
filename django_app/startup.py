"""Bounded dependency readiness checks before launching the local web process."""

import os
import sys
import time

import httpx
import django


def wait_for_dependencies(attempts: int = 30, interval_seconds: float = 2.0) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from django.db import connections

    api_base = os.environ.get("RAG_API_BASE_URL", "").rstrip("/")
    token = os.environ.get("RAG_API_TOKEN", "")
    if not api_base or len(token) < 32:
        raise RuntimeError("RAG API readiness configuration is missing; set the private URL and service credential.")

    last_check = "database"
    for attempt in range(attempts):
        try:
            connections["default"].ensure_connection()
            last_check = "RAG API"
            response = httpx.get(
                f"{api_base}/ready",
                headers={"Authorization": f"Bearer {token}"},
                timeout=httpx.Timeout(3.0),
                follow_redirects=False,
            )
            if response.status_code == 200:
                connections.close_all()
                print("Database and authenticated RAG readiness checks passed.", flush=True)
                return
        except Exception:
            connections.close_all()
        if attempt + 1 < attempts:
            if attempt == 0 or (attempt + 1) % 5 == 0:
                print(f"Waiting for {last_check} readiness ({attempt + 1}/{attempts}).", flush=True)
            time.sleep(interval_seconds)

    raise RuntimeError(f"Startup readiness timed out waiting for {last_check}; check service health and private network configuration.")


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("Startup command is not configured.")
    wait_for_dependencies()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
