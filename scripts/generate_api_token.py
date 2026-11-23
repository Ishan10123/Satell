"""Print a fresh 256-bit URL-safe bearer token for the local API."""

import secrets

if __name__ == "__main__":
    print(secrets.token_urlsafe(32))
