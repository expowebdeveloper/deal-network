"""Exercise the OAuth endpoints end to end.

Run with the server up:
    uvicorn app.main:app --port 8000
    python oauth_test.py

Runs twice against the same server contract: once as configured (Google disabled),
then the caller restarts with dummy credentials to prove the redirect is built
correctly. Pass `--configured` for the second pass.
"""

from __future__ import annotations

import sys
from urllib.parse import parse_qs, urlparse

import httpx
import jwt

from app.core.config import settings
from app.core.security import create_oauth_state

BASE = "http://127.0.0.1:8000"
# Whether Google is configured is read from the server at runtime, so the same
# test is correct before and after real credentials land in .env.
CONFIGURED = httpx.get(f"{BASE}/health", timeout=10).json()["oauth_providers"] == ["google"]
passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


def frag(response: httpx.Response) -> dict:
    """Parse the fragment the backend sends back to the SPA."""
    return {k: v[0] for k, v in parse_qs(urlparse(response.headers["location"]).fragment).items()}


def main() -> None:
    mode = "GOOGLE CONFIGURED (dummy credentials)" if CONFIGURED else "GOOGLE NOT CONFIGURED"
    print(f"\n=== {mode} ===")

    with httpx.Client(base_url=BASE, timeout=20, follow_redirects=False) as c:
        print("\nDiscovery")
        r = c.get("/health")
        providers = r.json()["oauth_providers"]
        check(
            "GET /health reports provider state",
            r.status_code == 200 and (providers == ["google"] if CONFIGURED else providers == []),
            r.text[:160],
        )
        r = c.get("/auth/providers")
        names = [p["name"] for p in r.json()["providers"]]
        check(
            "GET /auth/providers lists only working providers",
            r.status_code == 200 and (names == ["google"] if CONFIGURED else names == []),
            r.text[:160],
        )

        print("\nStarting the flow")
        r = c.get("/auth/google/login")
        if CONFIGURED:
            check("GET /auth/google/login -> 307", r.status_code == 307, str(r.status_code))
            target = urlparse(r.headers.get("location", ""))
            params = {k: v[0] for k, v in parse_qs(target.query).items()}
            check(
                "redirects to Google's consent screen",
                target.netloc == "accounts.google.com" and target.path == "/o/oauth2/v2/auth",
                r.headers.get("location", "")[:120],
            )
            check("sends client_id", params.get("client_id") == settings.google_client_id,
                  str(params.get("client_id")))
            check("sends the configured redirect_uri",
                  params.get("redirect_uri") == settings.google_redirect_uri,
                  str(params.get("redirect_uri")))
            check("requests openid email profile",
                  params.get("scope") == "openid email profile", str(params.get("scope")))
            check("uses authorization code flow",
                  params.get("response_type") == "code", str(params.get("response_type")))

            state = params.get("state", "")
            claims = jwt.decode(state, settings.jwt_secret_key,
                                algorithms=[settings.jwt_algorithm])
            check("state is a signed JWT bound to the provider",
                  claims.get("provider") == "google" and claims.get("type") == "oauth_state",
                  str(claims))
            check("state expires", "exp" in claims, str(claims))
            tampered = state[:-4] + ("aaaa" if not state.endswith("aaaa") else "bbbb")
        else:
            check("GET /auth/google/login -> 503 while unconfigured",
                  r.status_code == 503, str(r.status_code))
            check("503 explains what is missing",
                  "not configured" in r.text.lower(), r.text[:160])
            tampered = "not-a-token"

        r = c.get("/auth/apple/login")
        check("GET /auth/apple/login -> 503 (Apple unconfigured)",
              r.status_code == 503, str(r.status_code))
        r = c.get("/auth/facebook/login")
        check("GET /auth/{unknown}/login -> 404", r.status_code == 404, str(r.status_code))

        print("\nCallback handling")
        r = c.get("/auth/google/callback", params={"error": "access_denied"})
        check("user denies consent -> redirected to frontend with the error",
              r.status_code == 303 and frag(r).get("error") == "access_denied",
              r.headers.get("location", "")[:140])

        r = c.get("/auth/google/callback")
        check("callback with no code -> error=missing_code",
              r.status_code == 303 and frag(r).get("error") == "missing_code",
              r.headers.get("location", "")[:140])

        r = c.get("/auth/google/callback", params={"code": "abc", "state": tampered})
        check("forged/tampered state is rejected",
              r.status_code == 303 and frag(r).get("error", "").startswith("invalid_state"),
              r.headers.get("location", "")[:140])

        wrong_provider_state = create_oauth_state("apple")
        r = c.get("/auth/google/callback", params={"code": "abc", "state": wrong_provider_state})
        check("state minted for another provider is rejected",
              r.status_code == 303 and frag(r).get("error", "").startswith("invalid_state"),
              r.headers.get("location", "")[:140])

        r = c.get("/auth/google/callback",
                  params={"code": "abc", "state": create_oauth_state("google")})
        if CONFIGURED:
            # State is good, so the code is actually sent to Google, which rejects it.
            check("valid state + bad code -> exchange attempted and failure handled",
                  r.status_code == 303 and frag(r).get("error") == "oauth_exchange_failed",
                  r.headers.get("location", "")[:140])
        else:
            check("valid state but provider disabled -> exchange fails cleanly",
                  r.status_code == 303 and frag(r).get("error") == "oauth_exchange_failed",
                  r.headers.get("location", "")[:140])

        check("redirect always lands on the configured frontend",
              r.headers.get("location", "").startswith(settings.frontend_url),
              r.headers.get("location", "")[:140])
        check("tokens/errors travel in the fragment, not the query",
              "#" in r.headers.get("location", "")
              and "?" not in r.headers.get("location", ""),
              r.headers.get("location", "")[:140])

        print("\nApple callback shape")
        r = c.post("/auth/apple/callback", data={"error": "user_cancelled_authorize"})
        check("Apple posts a form and is handled as POST",
              r.status_code == 303 and frag(r).get("error") == "user_cancelled_authorize",
              r.headers.get("location", "")[:140])
        r = c.get("/auth/apple/callback")
        check("Apple callback rejects GET (405)", r.status_code == 405, str(r.status_code))

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
