"""Reference resolvers + the public enum tables for /whop/*.

ONE param per input (tripadvisor QueryOrIdField convention): every `*RefField`
accepts a bare id OR a whop.com / contentrewards.com link. Resolvers are
pure (no I/O) and return a canonical string that whop/api.py turns into the
upstream id — a route-shaped reference costs one extra `resolveStorePageIds`
/ `resolveSlug` call there. They raise ValueError with a user-facing message
(schema_fields.RefField turns it into a 400).

Identifier shapes (whop.com, 2026-11-03):
  * company  biz_<14 alnum>           store page https://whop.com/<route>/
  * product  prod_<13> or pass_<13>   https://whop.com/<company-route>/<product-route>/
  * user     user_<13>                https://whop.com/@<username>/
  * app      app_<14>                 https://whop.com/apps/app_xxx/
  * campaign a UUID (Content Rewards) https://contentrewards.com/c/campaigns/<uuid>
                                      (the old /discover/<uuid> redirects there)

Canonical reference strings handed to api.py:
  company   "biz_…"            or "route:<company-route>"
  product   "prod_…"/"pass_…"  or "route:<company-route>/<product-route>"
  user      "user_…"           or "name:<username>"
  app       "app_…"
  campaign  "<uuid>"
"""
import re
from urllib.parse import urlparse

SITE = "https://whop.com"
CONTENT_REWARDS = "https://contentrewards.com"

_ID_RE = {
    "company": re.compile(r"^biz_[A-Za-z0-9]{8,20}$"),
    "product": re.compile(r"^(prod|pass)_[A-Za-z0-9]{8,20}$"),
    "user": re.compile(r"^user_[A-Za-z0-9]{8,20}$"),
    "app": re.compile(r"^app_[A-Za-z0-9]{8,20}$"),
}
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
# whop.com routes: lowercase slugs, digits and dashes (the site lower-cases
# them); a username may also carry dots and underscores.
_ROUTE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")

# First path segments of whop.com that are NOT company routes.
_RESERVED = {"apps", "checkout", "login", "home", "network", "careers", "releases",
             "blog", "blueprints", "discover", "dashboard", "api", "core", "_web",
             "_static", "trends", "start", "new-business", "membership-invites"}


def _is_link(value):
    return value.startswith(("http://", "https://", "//"))


def _parsed(value, hosts, what):
    url = value if not value.startswith("//") else "https:" + value
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in hosts):
        raise ValueError(f"Must be a {' / '.join(hosts)} {what} link.")
    return [seg for seg in parsed.path.split("/") if seg]


def resolve_company(value):
    """biz_ id, a bare store route ("limitless") or a whop.com store link
    -> "biz_…" or "route:<route>"."""
    value = (value or "").strip()
    if _ID_RE["company"].match(value):
        return value
    if _is_link(value):
        segs = _parsed(value, ["whop.com"], "company")
        if not segs or segs[0].startswith("@") or segs[0].lower() in _RESERVED:
            raise ValueError("Must be a whop.com store link (https://whop.com/<route>/).")
        return "route:" + segs[0].lower()
    low = value.lower()
    if _ROUTE_RE.match(low):
        return "route:" + low
    raise ValueError("Must be a company id (biz_…), a store route (limitless) "
                     "or a whop.com store link (https://whop.com/limitless/).")


def resolve_product(value):
    """prod_/pass_ id or a whop.com product link
    (https://whop.com/<company-route>/<product-route>/) -> "prod_…" or
    "route:<company>/<product>"."""
    value = (value or "").strip()
    if _ID_RE["product"].match(value):
        return value
    if _is_link(value):
        segs = _parsed(value, ["whop.com"], "product")
        if len(segs) >= 2 and not segs[0].startswith("@") and segs[0].lower() not in _RESERVED \
                and segs[1].lower() not in ("products", "reviews"):
            return f"route:{segs[0].lower()}/{segs[1].lower()}"
        raise ValueError("Must be a whop.com product link "
                         "(https://whop.com/<company-route>/<product-route>/).")
    raise ValueError("Must be a product id (prod_…) or a whop.com product link "
                     "(https://whop.com/winnerscircle-e956/forex-signals-d6/).")


def resolve_user(value):
    """user_ id, a username (with or without @) or a whop.com profile link
    -> "user_…" or "name:<username>"."""
    value = (value or "").strip()
    if _ID_RE["user"].match(value):
        return value
    if _is_link(value):
        segs = _parsed(value, ["whop.com"], "profile")
        if segs and segs[0].startswith("@") and len(segs[0]) > 1:
            return "name:" + segs[0][1:]
        raise ValueError("Must be a whop.com profile link (https://whop.com/@username/).")
    name = value[1:] if value.startswith("@") else value
    if _USERNAME_RE.match(name):
        return "name:" + name
    raise ValueError("Must be a user id (user_…), a username (@jack) or a "
                     "whop.com profile link (https://whop.com/@jack/).")


def resolve_app(value):
    """app_ id or a whop.com/apps/app_xxx/ link -> "app_…"."""
    value = (value or "").strip()
    if _ID_RE["app"].match(value):
        return value
    if _is_link(value):
        segs = _parsed(value, ["whop.com"], "app")
        if len(segs) >= 2 and segs[0].lower() == "apps" and _ID_RE["app"].match(segs[1]):
            return segs[1]
        raise ValueError("Must be a whop.com app link (https://whop.com/apps/app_xxx/).")
    raise ValueError("Must be an app id (app_…) or a whop.com app link "
                     "(https://whop.com/apps/app_fqYWzj3RZXe1O0/).")


def resolve_campaign(value):
    """Content Rewards campaign UUID or a contentrewards.com campaign link
    (/c/campaigns/<uuid>, /discover/<uuid>, /c/discover/<uuid>) -> the UUID."""
    value = (value or "").strip()
    if _UUID_RE.match(value):
        return value.lower()
    if _is_link(value):
        segs = _parsed(value, ["contentrewards.com", "whop.com"], "campaign")
        for seg in segs:
            if _UUID_RE.match(seg):
                return seg.lower()
        raise ValueError("Must be a contentrewards.com campaign link "
                         "(https://contentrewards.com/c/campaigns/<uuid>).")
    raise ValueError("Must be a campaign UUID or a contentrewards.com campaign link.")


# ---- links -------------------------------------------------------------------

def company_link(route):
    return f"{SITE}/{route}/" if route else None


def product_link(company_route, product_route):
    if company_route and product_route:
        return f"{SITE}/{company_route}/{product_route}/"
    return None


def user_link(username):
    return f"{SITE}/@{username}/" if username else None


def app_link(app_id):
    return f"{SITE}/apps/{app_id}/" if app_id else None


def campaign_link(campaign_id):
    return f"{CONTENT_REWARDS}/c/campaigns/{campaign_id}" if campaign_id else None


def organization_link(handle):
    return f"{CONTENT_REWARDS}/c/{handle}" if handle else None


# ---- enum tables (data.whop.com introspection, 2026-11-03) --------------------

# publicAccessPasses(filter.order): PublicAccessPassesOrder — the orders the
# old Discover leaderboards offered (/discover/leaderboards/f/<order>/).
PRODUCT_SORTS = (
    "trending", "trending_3_hours", "newest_arrivals", "most_reviews_24_hours",
    "most_reviews_7_days", "most_money_made_24_hours",
    "most_affiliate_earnings_24_hours", "average_review_rating",
    "highest_bounties", "last_24_hours_total_seconds",
    "average_time_spent_24_hours", "global_affiliate_percentage",
)

# leaderboard(leaderboardType): LeaderboardTypes.
LEADERBOARD_TYPES = (
    "usd_gmv", "top_rated", "new_users", "money_earned_last_24_hours",
    "money_earned_last_7_days", "money_earned_last_30_days",
    "affiliate_earnings", "average_time_spent", "total_time_spent",
    "whop_partners_earnings_last_30_days", "whop_partners_gtv_last_30_days",
)

# listApps(order): AppOrder.
APP_SORTS = (
    "total_installs_last_7_days", "total_installs_last_30_days",
    "daily_active_users", "time_spent_last_24_hours", "discoverable_at",
    "created_at", "ai_prompt_count", "ai_average_rating", "total_ai_cost_usd",
    "total_ai_tokens", "last_ai_prompt_at",
)
APP_VIEWS = ("hub", "discover", "dash", "dashboard", "analytics", "skills", "openapi")
APP_TYPES = ("b2c_app", "b2b_app", "company_app", "component", "website")

# companies/list: our sort name -> the Query field that serves it.
COMPANY_LISTS = {
    "popular": "popularBots",
    "verified": "verifiedCompanies",
    "top_affiliate": "affiliateMarketplaceCompanies",
}
# affiliateMarketplaceCompanies(filter.order): AffiliateMarketplaceCompaniesOrder
AFFILIATE_ORDERS = ("earnings", "conversions", "clicks", "score", "created_at")

# publicBounties(filter.order): PublicBountiesOrder
BOUNTY_SORTS = ("total_paid", "created_at")

# Content Rewards discover feed (422 messages list the accepted values,
# 2026-11-03).
CAMPAIGN_SORTS = ("cpm", "featured", "newest", "budget", "payout", "available",
                  "paidout", "creators", "trending", "relevance")
# public value -> the feed's own casing
CAMPAIGN_SORT_TOKENS = {s: ("paidOut" if s == "paidout" else s) for s in CAMPAIGN_SORTS}
CAMPAIGN_PLATFORMS = ("tiktok", "instagram", "youtube", "x", "facebook")
CAMPAIGN_PAYOUT_TYPES = ("cpm", "pool", "retainer")
CAMPAIGN_STATUSES = ("active", "ended", "upcoming", "paused", "completed", "all")
