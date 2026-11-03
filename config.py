"""Configuration for the Whop Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT        port the API listens on (default 8000)
    WHOP_PROXY  proxy URL for every request, e.g. http://user:pass@host:port
                (default: none — direct). Whop's data API and the Content
                Rewards feed answered home, office and cloud server IPs alike
                (40 requests in 10 seconds from one IP, no rate limit), so you
                very likely don't need this.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

WHOP_PROXY = os.environ.get("WHOP_PROXY") or None


def whop_proxy():
    """The proxy for one curl session (None = direct)."""
    return os.environ.get("WHOP_PROXY") or None
