"""Whop transport: plain curl_cffi with browser-impersonated TLS. No
browser, no cookies, no token. Egress: one sticky exit per thread session
(config.whop_proxy(), knob WHOP_EXIT); a retryable failure drops the
session, so the retry rides a fresh exit.

Where the data lives (2026-11-03). whop.com is a TanStack Start app whose
public marketplace ("Discover") is gone: /discover/*, the leaderboards and
the search page redirect to the landing page or to a *company* of that
route. Every store / product / profile page hydrates itself from the same
anonymous GraphQL gateway, which is what this module calls directly:

  * GRAPHQL  POST https://data.whop.com/graphql  {operationName, query,
    variables}. The operation MUST be named (an unnamed document answers an
    empty 404). No auth: publicCompany / publicAccessPass / publicUser /
    retrieveApp, the catalog (publicAccessPasses with the old leaderboard
    orders, marketplaceCategories, leaderboard), the search
    (discoveryImprovedPipelineV3), reviews, members, apps, bounties.
    Login-only fields (listUsers, listProducts, universalPosts, forum
    feeds) answer a 401 error object; nothing here uses them. Connection
    cursors are graphql-ruby offsets: base64("50") == "NTA".

  * CONTENT REWARDS  GET https://contentrewards.com/api/campaign/campaigns/
    discover?limit<=100&sortBy=…&cursor=… (keyset cursor, opaque + signed)
    and /campaigns/<uuid> + /campaigns/discover/<uuid> for one campaign.
    Whop's clipping marketplace; no auth, CloudFront in front.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  WhopUpstreamError  transport failure / 5xx / GraphQL execution error — retryable
  WhopBlocked        403 / 429 / challenge page                         — retryable
  WhopBadRequest     upstream 400 / 422 (bad filter value)              — never retried
  WhopNotFound       unknown id / route                                 — never retried
"""
import base64
import json
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import egress
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from whop.refs import CONTENT_REWARDS, SITE

IMPERSONATE = "chrome"
GRAPHQL = "https://data.whop.com/graphql"
CR_DISCOVER = CONTENT_REWARDS + "/api/campaign/campaigns/discover"
CR_CAMPAIGN = CONTENT_REWARDS + "/api/campaign/campaigns/"
TIMEOUT = 40

GRAPHQL_HEADERS = {
    "accept": "application/json",
    "accept-language": egress.site_accept_language("whop"),
    "content-type": "application/json",
    "origin": SITE,
    "referer": SITE + "/",
}
CR_HEADERS = {
    "accept": "application/json",
    "accept-language": egress.site_accept_language("whop"),
    "referer": CONTENT_REWARDS + "/c/discover",
}

# Connection page sizes the gateway honours (first > 100 is clamped to 100).
PAGE_100 = 100
PAGE_50 = 50
SEARCH_LIMIT_MAX = 150
CR_PAGE = 100


class WhopUpstreamError(UpstreamError):
    """Transport failure / 5xx / GraphQL execution error — retryable."""


class WhopBlocked(WhopUpstreamError, Blocked):
    """403 / 429 or a challenge page where JSON was expected — retryable."""


class WhopBadRequest(BadRequest):
    """Upstream 400 / 422 — never retried."""


class WhopNotFound(NotFound):
    """Unknown id / route — never retried."""


# ---- sessions ------------------------------------------------------------------

_local = threading.local()


def _session():
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        proxy = config.whop_proxy()
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        _local.session = sess
        _local.proxy = proxy
    return sess


def _drop_session():
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def _retrying(fn):
    last = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn()
        except WhopUpstreamError as e:
            last = e
            _drop_session()
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


def _headers(base):
    """The exit's own language on every request (the session's exit may
    differ from the policy's first tier after a retry)."""
    proxy = getattr(_local, "proxy", None)
    return {**base, "accept-language": egress.accept_language(proxy)}


def _classify(resp, label):
    status = resp.status_code
    if status in (401, 403, 429):
        raise WhopBlocked(f"HTTP {status} for {label}")
    if status in (400, 422):
        raise WhopBadRequest(_error_message(resp) or f"HTTP {status} for {label}")
    if status == 404:
        raise WhopNotFound(f"{label} not found")
    if status != 200:
        raise WhopUpstreamError(f"HTTP {status} for {label}")
    ctype = (resp.headers.get("content-type") or "").lower()
    if "json" not in ctype:
        text = resp.text[:300].lower()
        if "<html" in text:
            raise WhopBlocked(f"challenge page instead of JSON for {label}")
        raise WhopUpstreamError(f"non-JSON response for {label}")
    try:
        return resp.json()
    except Exception:
        raise WhopUpstreamError(f"undecodable JSON for {label}")


def _error_message(resp):
    try:
        body = resp.json()
    except Exception:
        return None
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        fields = err.get("fields") or {}
        parts = [f"{k}: {' '.join(v) if isinstance(v, list) else v}" for k, v in fields.items()]
        return "; ".join(parts) or err.get("message")
    return err if isinstance(err, str) else None


# ---- GraphQL --------------------------------------------------------------------

def offset_cursor(offset):
    """graphql-ruby's default connection cursor: base64 of the 1-based
    offset of the last node already seen ("NTA" == 50)."""
    if not offset:
        return None
    return base64.b64encode(str(int(offset)).encode()).decode().rstrip("=")


def _op_name(query):
    match = re.match(r"\s*(?:query|mutation)\s+([A-Za-z0-9_]+)", query)
    if not match:
        raise ValueError("GraphQL documents must be named")
    return match.group(1)


_NOT_FOUND_RE = re.compile(r"not found|does not exist|no such|could not find", re.I)


def graphql(query, variables=None, label=None):
    """POST one named operation; return its `data`. GraphQL errors map to
    the taxonomy: 404 / "not found" -> WhopNotFound, 401 (login-only field)
    -> WhopUpstreamError (never a block: a fresh exit changes nothing),
    anything else -> WhopUpstreamError."""
    name = _op_name(query)
    label = label or name
    payload = {"operationName": name, "query": query, "variables": variables or {}}

    def once():
        try:
            resp = _session().post(GRAPHQL, json=payload, headers=_headers(GRAPHQL_HEADERS),
                                   timeout=TIMEOUT)
        except Exception as e:
            raise WhopUpstreamError(f"request failed: {type(e).__name__}: {e}")
        body = _classify(resp, label)
        if not isinstance(body, dict):
            raise WhopUpstreamError(f"unexpected GraphQL payload for {label}")
        errors = body.get("errors") or []
        data = body.get("data")
        if errors:
            first = errors[0] if isinstance(errors[0], dict) else {}
            ext = first.get("extensions") or {}
            message = first.get("message") or "GraphQL error"
            status = ext.get("status_code")
            if status == 404 or ext.get("error_type") == "not_found" or _NOT_FOUND_RE.search(message):
                raise WhopNotFound(f"{label} not found")
            if status in (401, 403) or ext.get("error_type") in ("unauthorized", "forbidden"):
                raise WhopUpstreamError(f"{label}: login-only field: {message}")
            if ext.get("code") in ("argumentLiteralsIncompatible", "undefinedField",
                                   "variableNotUsed") or "must be" in message:
                raise WhopBadRequest(message)
            if data is None:
                raise WhopUpstreamError(f"{label}: {message}")
        if data is None:
            raise WhopUpstreamError(f"{label}: empty data")
        return data
    return _retrying(once)


# ---- fragments ---------------------------------------------------------------------

PLAN_FIELDS = """
    id title description formattedPrice formattedPeriodV2 priceTag
    rawInitialPrice rawInitialPriceUsd rawRenewalPrice rawRenewalPriceUsd
    initialPriceDueInCents strikeThroughInitialPrice strikeThroughRenewalPrice
    baseCurrency planType billingPeriod releaseMethod free trialPeriodDays
    expirationDays stock unlimitedStock inStock lowStockWarning
    visibility directLink createdAt allowMultipleQuantity
    splitPayRequiredPayments acceptedPaymentMethods
"""

PRODUCT_CARD = """
    id title route headline shortenedDescription accessPassType businessType
    industryType marketplaceStatus verified whopRanking activeUsersCount
    memberCount publishedReviewsCount reviewsAverage usdGmv last24HoursGmv
    hasFreeAvailablePlan hasPaidAvailablePlan globalAffiliatePercentage
    createdAt discoverableAt
    logo { sourceUrl }
    images { url }
    company { id route title verified }
    defaultPlan { id formattedPrice formattedPeriodV2 rawInitialPrice rawRenewalPrice
                  baseCurrency planType billingPeriod releaseMethod free trialPeriodDays }
"""

COMPANY_CARD = """
    id title route verified creatorPitch businessType industryType memberCount
    publishedReviewsCount reviewsAverage createdAt
    logo { sourceUrl }
    ownerUser { id username name }
"""

REVIEW_FIELDS = """
    id stars title description createdAt joinedAt publishedAt paidForProduct
    upvotes replyCount featured whopReviewed
    userAccount { id username name profilePicture { sourceUrl } }
    accessPass { id route title }
    company { id route title }
    attachments { sourceUrl }
"""

USER_CARD = """
    id username name followersCount verifiedAt profilePicture { sourceUrl }
"""

APP_CARD = """
    id name route description appType status marketplaceStatus verified
    discoverableAt totalInstalls totalInstallsLast7Days
    totalInstallsLast30Days aiPromptCount aiAverageRating aiRatingCount
    stats { dau wau mau timeSpentLast24HoursInSeconds }
    icon { sourceUrl }
    creator { id username name }
    company { id route title }
    accessPass { id route title headline reviewsAverage publishedReviewsCount
                 marketplaceCategory(level: 1) { id name route } }
"""

BOUNTY_FIELDS = """
    id title description bountyType status discoverStatus rewardPerUnitAmount
    rewardUnit currency budgetAmount totalPaid spotsRemaining
    acceptedSubmissionsCount acceptedSubmissionsLimit activeSubmissionsCount
    bountySubmissionsCount awaitingReviewSubmissionsCount deniedSubmissionsCount
    allowTiktok allowYoutube allowInstagram allowX allowedCountryCodes
    requiredCaptureDurationSeconds scheduledFrequency businessGoalType
    viewCount commentCount reactionCount createdAt updatedAt
    experience { id name company { id route title verified } }
    user { id username name }
    accessPasses(first: 5) { nodes { id route title } }
"""

# ---- documents -------------------------------------------------------------------

Q_SEARCH = """
query whopSearch($query: String!, $limit: Int, $page: Int, $companies: Boolean, $filters: String) {
  discoveryImprovedPipelineV3(query: $query, limit: $limit, page: $page,
                              showCompanies: $companies, filters: $filters) {
    found
    accessPasses { %s }
    companies { %s }
  }
}
""" % (PRODUCT_CARD, COMPANY_CARD)

Q_PRODUCTS_LIST = """
query whopProductsList($first: Int, $after: String, $filter: AccessPassFilters) {
  publicAccessPasses(first: $first, after: $after, filter: $filter) {
    totalCount
    pageInfo { hasNextPage endCursor }
    nodes { %s }
  }
}
""" % PRODUCT_CARD

Q_PRODUCT = """
query whopProduct($id: ID!) {
  publicAccessPass(id: $id) {
    id title route headline shortenedDescription description creatorPitch
    accessPassType businessType industryType marketplaceStatus verified labels
    whopRanking activeUsersCount memberCount publishedReviewsCount reviewsAverage
    reviewCounts averageReviewRating usdGmv last24HoursGmv likeCount shareCount
    totalBountyAmount hasFreeAvailablePlan hasPaidAvailablePlan
    isFreeAndJoinableWithoutRequirements globalAffiliateStatus
    globalAffiliatePercentage memberAffiliateStatus memberAffiliatePercentage
    customCta customCtaUrl redirectPurchaseUrl directLink showMemberCount
    showReviewsDtc collectShippingAddress visiblePlansCount
    createdAt firstApprovedAt discoverableAt updatedAt
    logo { sourceUrl }
    bannerImage { sourceUrl }
    galleryImages { sourceUrl }
    images { url }
    marketplaceCategory(level: 1) { id name route }
    subcategory: marketplaceCategory(level: 2) { id name route }
    productTaxCode { name productType }
    company { id route title verified memberCount publishedReviewsCount reviewsAverage
              logo { sourceUrl } }
    ownerUser { %s }
    defaultPlan { %s }
    visiblePlans(first: 50) { totalCount nodes { %s } }
    faq { id question answer }
    productHighlights { nodes { id title content highlightType } }
    experiences { id name description isPublic app { id name } }
    socialLinks { website url title }
    mostRecentReview { %s }
  }
}
""" % (USER_CARD, PLAN_FIELDS, PLAN_FIELDS, REVIEW_FIELDS)

Q_PRODUCT_REVIEWS = """
query whopProductReviews($id: ID!, $first: Int, $after: String, $stars: Int) {
  publicAccessPass(id: $id) {
    id route title
    company { id route title }
    reviews(first: $first, after: $after, stars: $stars, companyWide: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { %s }
    }
  }
}
""" % REVIEW_FIELDS

Q_COMPANY = """
query whopCompany($id: ID!) {
  publicCompany(id: $id) {
    id title route verified creatorPitch businessDescription businessType
    industryType targetAudience memberCount publishedReviewsCount reviewsAverage
    reviewCounts cachedTotalViewsCount usdGmv30Days totalEarningsWithTransfersInUsd
    createdAt updatedAt launched hasGlobalAffiliatesEnabled
    affiliateApplicationRequired purchasesDisabled disabledReason features hubRoute
    logo { sourceUrl }
    bannerImage { sourceUrl }
    ownerUser { id username name bio city country createdAt followersCount verifiedAt
                profilePicture { sourceUrl } }
    socialLinks { website url title }
    publicForumExperience { id name }
    primaryExperience { id name }
    storePageConfig { accentColor layout }
    publicTeamMembers(first: 50) { totalCount nodes { id role user { %s } } }
    visibleAccessPassesV2 { %s visiblePlansCount }
    experienceList(allExperiences: true) {
      experiences { id name description isPublic userCount app { id name }
                    accessPasses { id route title } }
    }
  }
}
""" % (USER_CARD, PRODUCT_CARD)

Q_COMPANY_REVIEWS = """
query whopCompanyReviews($id: ID!, $first: Int, $after: String, $stars: Int) {
  publicCompany(id: $id) {
    id route title
    reviews(first: $first, after: $after, stars: $stars) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { %s }
    }
  }
}
""" % REVIEW_FIELDS

Q_COMPANY_MEMBERS = """
query whopCompanyMembers($id: ID!, $first: Int, $after: String) {
  publicCompany(id: $id) {
    id route title memberCount
    members(first: $first, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { id profile { id username name city country createdAt followersCount
                           verifiedAt profilePicture { sourceUrl } } }
    }
  }
}
"""

Q_COMPANIES_POPULAR = """
query whopCompaniesPopular($first: Int, $after: String) {
  popularBots(first: $first, after: $after) {
    totalCount pageInfo { hasNextPage endCursor } nodes { %s }
  }
}
""" % COMPANY_CARD

Q_COMPANIES_VERIFIED = """
query whopCompaniesVerified($first: Int, $after: String) {
  verifiedCompanies(first: $first, after: $after) {
    totalCount pageInfo { hasNextPage endCursor } nodes { %s }
  }
}
""" % COMPANY_CARD

Q_COMPANIES_AFFILIATE = """
query whopCompaniesAffiliate($first: Int, $after: String, $filter: AffiliateMarketplaceFilters) {
  affiliateMarketplaceCompanies(first: $first, after: $after, filter: $filter) {
    totalCount pageInfo { hasNextPage endCursor }
    nodes { %s affiliateTotalEarned affiliateTotalClicks affiliateTotalConversions
            hasGlobalAffiliatesEnabled }
  }
}
""" % COMPANY_CARD

Q_CATEGORIES = """
query whopCategories($level: Int, $first: Int) {
  marketplaceCategories(first: $first, level: $level, marketplaceCategoryType: regular) {
    totalCount
    nodes { id name route level tagline description liveAccessPassCount livePageCount
            displayOnHomepage parentMarketplaceCategory { id name route } }
  }
}
"""

Q_USER = """
query whopUser($id: ID!) {
  publicUser(id: $id) {
    id username name bio city country countryName createdAt lastSeenAt verifiedAt
    isSuspended followersCount followingCount roles averageResponseTimeInSeconds
    primaryUserReferralCount
    profilePicture { sourceUrl }
    banner { sourceUrl }
    socialLinks(first: 20) { nodes { website url username verified } }
    userStat { moneyEarnedLifetime }
    userPreferences { showEarnings showOwnedWhops showJoinedWhops showLocation }
    ownedWhops(first: 50, sortBy: cached_active_members_count, sortDirection: desc) {
      totalCount nodes { %s totalEarningsWithTransfersInUsd }
    }
    joinedWhops(first: 50, sortBy: last_accessed_at, sortDirection: desc) {
      totalCount nodes { %s }
    }
    reviews(first: 1) { totalCount }
  }
}
""" % (COMPANY_CARD, COMPANY_CARD)

Q_LEADERBOARD = """
query whopLeaderboard($type: LeaderboardTypes!, $limit: Int) {
  leaderboard(leaderboardType: $type, limit: $limit) {
    leaderboardType totalCount
    results {
      currentRank previousRank currentScore previousScore isFakeRank
      accessPass { %s }
      user { %s }
    }
  }
}
""" % (PRODUCT_CARD, USER_CARD)

Q_APPS = """
query whopApps($first: Int, $after: String, $view: AppViewTypes, $type: AppTypes,
               $order: AppOrder, $direction: Direction, $query: String, $category: ID) {
  listApps(first: $first, after: $after, viewType: $view, appType: $type, order: $order,
           direction: $direction, query: $query, marketplaceCategoryRoute: $category) {
    totalCount pageInfo { hasNextPage endCursor }
    nodes { %s }
  }
}
""" % APP_CARD

Q_APP = """
query whopApp($id: ID!) {
  retrieveApp(id: $id) {
    %s
    appStoreDescription aiGeneratedDescription productPageText
    defaultExperienceDescription internalIdentifier hostedUrl baseUrl capabilities
    lastAiPromptAt totalAiTokens usingDefaultIcon
    accessPass { id route title headline shortenedDescription description
                 reviewsAverage publishedReviewsCount reviewCounts memberCount
                 activeUsersCount createdAt
                 marketplaceCategory(level: 1) { id name route }
                 galleryImages { sourceUrl }
                 defaultPlan { %s }
                 company { id route title verified memberCount } }
  }
}
""" % (APP_CARD, PLAN_FIELDS)

Q_BOUNTIES = """
query whopBounties($first: Int, $after: String, $filter: BountyFilters) {
  publicBounties(first: $first, after: $after, filter: $filter) {
    totalCount pageInfo { hasNextPage endCursor }
    nodes { %s }
  }
}
""" % BOUNTY_FIELDS

Q_RESOLVE_SLUG = """
query whopResolveSlug($route: String!) {
  resolveSlug(route: $route) { slug { route resourceId resourceType } }
}
"""

Q_RESOLVE_STORE = """
query whopResolveStore($company: String!, $product: String) {
  resolveStorePageIds(companyOrAccessPassRoute: $company, accessPassRoute: $product) {
    companyId companyRoute accessPassId accessPassRoute
  }
}
"""

Q_STATS = """
query whopStats {
  marketplaceStats { activeSellersV2 activeUsersV2 membershipsSoldV2 totalCompaniesV2
                     totalProcessedV2 totalProductsV2 }
}
"""


# ---- fetchers (raw JSON) -------------------------------------------------------------

def fetch_search(query, page=1, limit=PAGE_50, companies=False, filters=None):
    data = graphql(Q_SEARCH, {
        "query": query, "limit": limit, "page": page, "companies": bool(companies),
        "filters": json.dumps(filters) if filters else None,
    }, label="search")
    return data.get("discoveryImprovedPipelineV3")


def fetch_products_list(page=1, order="trending", category=None, min_price=None,
                        affiliate_only=False, first=PAGE_100):
    flt = {"order": order, "direction": "desc"}
    if category:
        flt["marketplaceCategoryRoutes"] = [category]
    if min_price is not None:
        flt["priceMinimum"] = float(min_price)
    if affiliate_only:
        flt["globalAffiliateStatus"] = "enabled"
    try:
        data = graphql(Q_PRODUCTS_LIST, {"first": first, "after": offset_cursor((page - 1) * first),
                                         "filter": flt}, label="products list")
    except WhopNotFound:
        # the gateway's "Could not find the target marketplace category" is
        # a bad `category` value, not a missing page (the route list is
        # /whop/categories/list)
        if category:
            raise WhopBadRequest(f"unknown category route {category!r}; "
                                 "see /whop/categories/list")
        raise
    return data.get("publicAccessPasses")


def fetch_product(product_id):
    data = graphql(Q_PRODUCT, {"id": product_id}, label=f"product {product_id}")
    node = data.get("publicAccessPass")
    if not node:
        raise WhopNotFound(f"product {product_id} not found")
    return node


def fetch_product_reviews(product_id, page=1, stars=None, first=PAGE_50):
    data = graphql(Q_PRODUCT_REVIEWS, {"id": product_id, "first": first,
                                       "after": offset_cursor((page - 1) * first),
                                       "stars": stars}, label=f"product {product_id} reviews")
    node = data.get("publicAccessPass")
    if not node:
        raise WhopNotFound(f"product {product_id} not found")
    return node


def fetch_company(company_id):
    data = graphql(Q_COMPANY, {"id": company_id}, label=f"company {company_id}")
    node = data.get("publicCompany")
    if not node:
        raise WhopNotFound(f"company {company_id} not found")
    return node


def fetch_company_reviews(company_id, page=1, stars=None, first=PAGE_50):
    data = graphql(Q_COMPANY_REVIEWS, {"id": company_id, "first": first,
                                       "after": offset_cursor((page - 1) * first),
                                       "stars": stars}, label=f"company {company_id} reviews")
    node = data.get("publicCompany")
    if not node:
        raise WhopNotFound(f"company {company_id} not found")
    return node


def fetch_company_members(company_id, page=1, first=PAGE_100):
    data = graphql(Q_COMPANY_MEMBERS, {"id": company_id, "first": first,
                                       "after": offset_cursor((page - 1) * first)},
                   label=f"company {company_id} members")
    node = data.get("publicCompany")
    if not node:
        raise WhopNotFound(f"company {company_id} not found")
    return node


def fetch_companies_list(sort="popular", page=1, query=None, first=PAGE_50):
    after = offset_cursor((page - 1) * first)
    if sort == "verified":
        return graphql(Q_COMPANIES_VERIFIED, {"first": first, "after": after},
                       label="verified companies").get("verifiedCompanies")
    if sort == "top_affiliate":
        flt = {"order": "earnings", "direction": "desc"}
        if query:
            flt["query"] = query
        return graphql(Q_COMPANIES_AFFILIATE, {"first": first, "after": after, "filter": flt},
                       label="affiliate companies").get("affiliateMarketplaceCompanies")
    return graphql(Q_COMPANIES_POPULAR, {"first": first, "after": after},
                   label="popular companies").get("popularBots")


def fetch_categories(level=1, first=200):
    return graphql(Q_CATEGORIES, {"level": level, "first": first},
                   label="categories").get("marketplaceCategories")


def fetch_user(user_ref):
    data = graphql(Q_USER, {"id": user_ref}, label=f"user {user_ref}")
    node = data.get("publicUser")
    if not node:
        raise WhopNotFound(f"user {user_ref} not found")
    return node


def fetch_leaderboard(kind, limit=50):
    return graphql(Q_LEADERBOARD, {"type": kind, "limit": limit},
                   label=f"leaderboard {kind}").get("leaderboard")


def fetch_apps(page=1, order="total_installs_last_7_days", view="hub", app_type="b2c_app",
               query=None, category=None, first=PAGE_50):
    return graphql(Q_APPS, {"first": first, "after": offset_cursor((page - 1) * first),
                            "view": view, "type": app_type, "order": order,
                            "direction": "desc", "query": query, "category": category},
                   label="apps").get("listApps")


def fetch_app(app_id):
    data = graphql(Q_APP, {"id": app_id}, label=f"app {app_id}")
    node = data.get("retrieveApp")
    if not node:
        raise WhopNotFound(f"app {app_id} not found")
    return node


def fetch_bounties(page=1, order="total_paid", first=PAGE_50):
    return graphql(Q_BOUNTIES, {"first": first, "after": offset_cursor((page - 1) * first),
                                "filter": {"order": order, "direction": "desc"}},
                   label="bounties").get("publicBounties")


def resolve_route(route):
    """A whop.com store route -> (resource id, resource type) or None."""
    data = graphql(Q_RESOLVE_SLUG, {"route": route}, label=f"route {route}")
    slug = (data.get("resolveSlug") or {}).get("slug") or {}
    if not slug.get("resourceId"):
        return None
    return slug.get("resourceId"), slug.get("resourceType")


def resolve_store(company_route, product_route=None):
    """(company route, product route) -> the resolveStorePageIds record
    (companyId / accessPassId), or None when the route is unknown."""
    data = graphql(Q_RESOLVE_STORE, {"company": company_route, "product": product_route},
                   label=f"route {company_route}/{product_route or ''}")
    rec = data.get("resolveStorePageIds") or {}
    if not rec.get("companyId"):
        return None
    return rec


def fetch_stats():
    return graphql(Q_STATS, label="marketplace stats").get("marketplaceStats")


# ---- Content Rewards ---------------------------------------------------------------

def _cr_get(url, params, label):
    def once():
        try:
            resp = _session().get(url, params=params, headers=_headers(CR_HEADERS),
                                  timeout=TIMEOUT)
        except Exception as e:
            raise WhopUpstreamError(f"request failed: {type(e).__name__}: {e}")
        body = _classify(resp, label)
        if not isinstance(body, dict):
            raise WhopUpstreamError(f"unexpected payload for {label}")
        if body.get("success") is False:
            err = body.get("error") or {}
            if err.get("code") == "NOT_FOUND":
                raise WhopNotFound(f"{label} not found")
            raise WhopUpstreamError(f"{label}: {err.get('message') or 'error'}")
        return body
    return _retrying(once)


def fetch_campaigns_page(cursor=None, sort="trending", search=None, platform=None,
                         payout_type=None, category=None, status=None, organization_id=None,
                         view="full", limit=CR_PAGE):
    """One discover-feed page: {"data": [...], "pagination": {nextCursor, …}}."""
    params = {"limit": limit, "sortBy": sort, "view": view}
    if cursor:
        params["cursor"] = cursor
    if search:
        params["search"] = search
    if platform:
        params["platform"] = platform
    if payout_type:
        params["payoutType"] = payout_type
    if category:
        params["category"] = category
    if status and status != "active":
        params["status"] = status
    if organization_id:
        params["organizationId"] = organization_id
    return _cr_get(CR_DISCOVER, params, "campaigns")


def fetch_campaign(campaign_id):
    """The two per-campaign records: the discover card (budget, payouts,
    metrics, chart, top clips) and the campaign record (configuration,
    fee, minimum views, status reason). Either 404 -> WhopNotFound."""
    card = _cr_get(CR_DISCOVER + "/" + campaign_id, None, f"campaign {campaign_id}")
    record = _cr_get(CR_CAMPAIGN + campaign_id, None, f"campaign {campaign_id}")
    return {"card": card.get("data"), "record": record.get("data")}
