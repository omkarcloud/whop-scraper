"""The /whop/* endpoint functions (route_glue's route_table calls them with
the schema's loaded kwargs). Every endpoint caches its own response through
cache.cached_call keyed on the validated params; the route -> id
resolutions (a store link in place of an id) are cached separately for a
week so a client that pastes links pays the extra gateway call once.
"""
import math
import threading

from cache import cached_call
from whop import cache_config as ttl
from whop import fetch, parsers
from whop.fetch import WhopNotFound
from whop.refs import CAMPAIGN_SORT_TOKENS, product_link

SEARCH_PAGE = fetch.PAGE_50
LIST_PAGE = fetch.PAGE_100
REVIEWS_PAGE = fetch.PAGE_50
MEMBERS_PAGE = fetch.PAGE_100
COMPANIES_PAGE = fetch.PAGE_50
APPS_PAGE = fetch.PAGE_50
BOUNTIES_PAGE = fetch.PAGE_50
CAMPAIGNS_PAGE = fetch.CR_PAGE
SEARCH_MAX_PAGE = 3   # the search caps `limit` at 150 and returns no more


def _pagination(page, per_page, total=None, has_next=None, max_pages=None):
    """`max_pages` caps the page count where the site publishes a total it
    will not serve in full (the search reports every match but stops at
    150)."""
    if total is not None:
        pages = max(math.ceil(total / per_page), 1) if per_page else None
        if pages is not None and max_pages is not None:
            pages = min(pages, max_pages)
        return {"page": page, "items_per_page": per_page, "total_pages": pages,
                "total_count": total}
    return {"page": page, "items_per_page": per_page, "has_next": bool(has_next),
            "total_pages": None, "total_count": None}


# ---- reference resolution ------------------------------------------------------------

def _resolve_company_id(ref):
    """"biz_…" or "route:<route>" -> biz_ id (route via resolveSlug)."""
    if not ref.startswith("route:"):
        return ref
    route = ref[len("route:"):]

    def resolve(route):
        found = fetch.resolve_route(route)
        if not found or found[1] != "Company":
            raise WhopNotFound(f"no whop.com company at /{route}/")
        return found[0]
    return cached_call("whop.resolve_company", {"route": route}, resolve, ttl.RESOLVE_CACHE)


def _resolve_product_id(ref):
    """"prod_…" / "pass_…" or "route:<company>/<product>" -> product id."""
    if not ref.startswith("route:"):
        return ref
    company, _, product = ref[len("route:"):].partition("/")

    def resolve(company, product):
        rec = fetch.resolve_store(company, product)
        if not rec or not rec.get("accessPassId"):
            raise WhopNotFound(f"no whop.com product at {product_link(company, product)}")
        return rec["accessPassId"]
    return cached_call("whop.resolve_product", {"company": company, "product": product},
                       resolve, ttl.RESOLVE_CACHE)


def _resolve_user_id(ref):
    """publicUser(id) accepts a username as well as a user_ id."""
    return ref[len("name:"):] if ref.startswith("name:") else ref


# ---- products -----------------------------------------------------------------------------

def _products_search(query, page, business_type, industry_type):
    filters = {}
    if business_type:
        filters["businessType"] = business_type
    if industry_type:
        filters["industryType"] = industry_type
    found, rows = parsers.parse_search(fetch.fetch_search(query, page=page, limit=SEARCH_PAGE,
                                                          companies=False, filters=filters))
    return {"query": query, "results": rows,
            "pagination": _pagination(page, SEARCH_PAGE, total=found, max_pages=SEARCH_MAX_PAGE)}


def products_search(**data):
    return cached_call("whop.products_search", data, _products_search, ttl.SEARCH_CACHE)


def _products_list(sort, category, page, min_price, affiliate_only):
    total, has_next, rows = parsers.parse_connection(
        fetch.fetch_products_list(page=page, order=sort, category=category, min_price=min_price,
                                  affiliate_only=bool(affiliate_only), first=LIST_PAGE),
        parsers.parse_product_card)
    for rank, row in enumerate(rows, start=(page - 1) * LIST_PAGE + 1):
        row["rank"] = rank
    return {"sort": sort, "category": category, "results": rows,
            "pagination": _pagination(page, LIST_PAGE, total=total)}


def products_list(**data):
    return cached_call("whop.products_list", data, _products_list, ttl.LIST_CACHE)


def _product_details(product):
    record = parsers.parse_product(fetch.fetch_product(_resolve_product_id(product)))
    if record is None:
        raise WhopNotFound(f"product {product} not found")
    return record


def product_details(**data):
    return cached_call("whop.product_details", data, _product_details, ttl.DETAILS_CACHE)


def _product_reviews(product, stars, page):
    node = fetch.fetch_product_reviews(_resolve_product_id(product), page=page, stars=stars,
                                       first=REVIEWS_PAGE)
    total, _, rows = parsers.parse_connection(node.get("reviews"), parsers.parse_review)
    company = node.get("company") if isinstance(node.get("company"), dict) else {}
    return {
        "product": {"id": node.get("id"), "title": node.get("title"), "route": node.get("route"),
                    "link": product_link(company.get("route"), node.get("route"))},
        "stars": stars,
        "results": rows,
        "pagination": _pagination(page, REVIEWS_PAGE, total=total),
    }


def product_reviews(**data):
    return cached_call("whop.product_reviews", data, _product_reviews, ttl.REVIEWS_CACHE)


# ---- companies ------------------------------------------------------------------------------

def _companies_search(query, page):
    found, rows = parsers.parse_search(fetch.fetch_search(query, page=page, limit=SEARCH_PAGE,
                                                          companies=True), companies=True)
    return {"query": query, "results": rows,
            "pagination": _pagination(page, SEARCH_PAGE, total=found, max_pages=SEARCH_MAX_PAGE)}


def companies_search(**data):
    return cached_call("whop.companies_search", data, _companies_search, ttl.SEARCH_CACHE)


def _company_details(company):
    record = parsers.parse_company(fetch.fetch_company(_resolve_company_id(company)))
    if record is None:
        raise WhopNotFound(f"company {company} not found")
    return record


def company_details(**data):
    return cached_call("whop.company_details", data, _company_details, ttl.DETAILS_CACHE)


def _company_reviews(company, stars, page):
    node = fetch.fetch_company_reviews(_resolve_company_id(company), page=page, stars=stars,
                                       first=REVIEWS_PAGE)
    total, _, rows = parsers.parse_connection(node.get("reviews"), parsers.parse_review)
    return {
        "company": parsers._company_ref(node),
        "stars": stars,
        "results": rows,
        "pagination": _pagination(page, REVIEWS_PAGE, total=total),
    }


def company_reviews(**data):
    return cached_call("whop.company_reviews", data, _company_reviews, ttl.REVIEWS_CACHE)


def _company_members(company, page):
    node = fetch.fetch_company_members(_resolve_company_id(company), page=page, first=MEMBERS_PAGE)
    total, _, rows = parsers.parse_connection(node.get("members"), parsers.parse_member)
    return {
        "company": {**(parsers._company_ref(node) or {}), "members": node.get("memberCount")},
        "results": rows,
        "pagination": _pagination(page, MEMBERS_PAGE, total=total),
    }


def company_members(**data):
    return cached_call("whop.company_members", data, _company_members, ttl.MEMBERS_CACHE)


def _companies_list(sort, query, page):
    total, has_next, rows = parsers.parse_connection(
        fetch.fetch_companies_list(sort, page=page, query=query, first=COMPANIES_PAGE),
        parsers.parse_company_card)
    for rank, row in enumerate(rows, start=(page - 1) * COMPANIES_PAGE + 1):
        row["rank"] = rank
    return {"sort": sort, "query": query, "results": rows,
            "pagination": _pagination(page, COMPANIES_PAGE, total=total)}


def companies_list(**data):
    return cached_call("whop.companies_list", data, _companies_list, ttl.LIST_CACHE)


# ---- categories / users / leaderboards -----------------------------------------------------

def _categories_list(level):
    total, _, rows = parsers.parse_connection(fetch.fetch_categories(level), parsers.parse_category)
    rows.sort(key=lambda c: (-(c["products_count"] or 0), c["name"] or ""))
    return {"level": level, "count": len(rows), "results": rows}


def categories_list(**data):
    return cached_call("whop.categories_list", data, _categories_list, ttl.CATEGORIES_CACHE)


def _user_details(user):
    record = parsers.parse_user(fetch.fetch_user(_resolve_user_id(user)))
    if record is None:
        raise WhopNotFound(f"user {user} not found")
    return record


def user_details(**data):
    return cached_call("whop.user_details", data, _user_details, ttl.USER_CACHE)


def _leaderboards_list(type, limit):
    kind, total, rows = parsers.parse_leaderboard(fetch.fetch_leaderboard(type, limit=limit))
    return {"type": kind or type, "total_count": total, "count": len(rows), "results": rows}


def leaderboards_list(**data):
    return cached_call("whop.leaderboards_list", data, _leaderboards_list, ttl.LEADERBOARD_CACHE)


# ---- apps -------------------------------------------------------------------------------------

def _apps_list(sort, view, type, category, query, page):
    total, _, rows = parsers.parse_connection(
        fetch.fetch_apps(page=page, order=sort, view=view, app_type=type, query=query,
                         category=category, first=APPS_PAGE),
        parsers.parse_app_card)
    for rank, row in enumerate(rows, start=(page - 1) * APPS_PAGE + 1):
        row["rank"] = rank
    return {"sort": sort, "view": view, "type": type, "category": category, "query": query,
            "results": rows, "pagination": _pagination(page, APPS_PAGE, total=total)}


def apps_list(**data):
    return cached_call("whop.apps_list", data, _apps_list, ttl.LIST_CACHE)


def _app_details(app):
    record = parsers.parse_app(fetch.fetch_app(app))
    if record is None:
        raise WhopNotFound(f"app {app} not found")
    return record


def app_details(**data):
    return cached_call("whop.app_details", data, _app_details, ttl.DETAILS_CACHE)


# ---- bounties ---------------------------------------------------------------------------------

def _bounties_list(sort, page):
    total, _, rows = parsers.parse_connection(
        fetch.fetch_bounties(page=page, order=sort, first=BOUNTIES_PAGE), parsers.parse_bounty)
    return {"sort": sort, "results": rows, "pagination": _pagination(page, BOUNTIES_PAGE, total=total)}


def bounties_list(**data):
    return cached_call("whop.bounties_list", data, _bounties_list, ttl.BOUNTIES_CACHE)


# ---- Content Rewards campaigns -----------------------------------------------------------------

# The feed paginates with an opaque, signed keyset cursor, so page N needs
# the cursor page N-1 returned. Each (filters) chain keeps its cursors here
# so a client walking pages pays one feed call per page, not N; a cold
# process walks the prefix once (view=summary keeps those hops light).
_cursor_chains = {}
_cursor_lock = threading.Lock()


def _chain_key(**filters):
    return tuple(sorted((k, v) for k, v in filters.items() if v is not None))


def _campaign_cursor(page, **filters):
    """The cursor that opens `page` (None for page 1), walking the prefix
    pages when the chain does not have it yet. Returns (cursor, exhausted)."""
    if page == 1:
        return None, False
    key = _chain_key(**filters)
    with _cursor_lock:
        chain = _cursor_chains.setdefault(key, {1: None})
    known = max(p for p in chain if p <= page)
    cursor = chain[known]
    if cursor is False:
        # the chain already learnt that page `known` (<= page) does not
        # exist; without this a request for exactly that page would send
        # cursor=False, i.e. no cursor, and serve page 1 again
        return None, True
    for hop in range(known, page):
        if hop in chain and chain[hop] is False:
            return None, True
        payload = fetch.fetch_campaigns_page(cursor=cursor, view="summary", **filters)
        _, nxt = parsers.parse_campaigns_page(payload)
        with _cursor_lock:
            chain[hop + 1] = nxt if nxt else False
        if not nxt:
            return None, True
        cursor = nxt
    return cursor, False


def _campaigns_list(sort, search, platform, payout_type, category, organization_id, page):
    filters = dict(sort=CAMPAIGN_SORT_TOKENS.get(sort, sort), search=search, platform=platform,
                   payout_type=payout_type, category=category, organization_id=organization_id)
    cursor, exhausted = _campaign_cursor(page, **filters)
    if exhausted:
        rows, nxt = [], None
    else:
        payload = fetch.fetch_campaigns_page(cursor=cursor, view="full", **filters)
        rows, nxt = parsers.parse_campaigns_page(payload, with_metrics_detail=False)
        with _cursor_lock:
            _cursor_chains.setdefault(_chain_key(**filters), {1: None})[page + 1] = nxt if nxt else False
    return {
        "sort": sort, "search": search, "platform": platform, "payout_type": payout_type,
        "category": category, "organization_id": organization_id,
        "results": rows,
        # the feed publishes no total; has_next follows its nextCursor
        "pagination": _pagination(page, CAMPAIGNS_PAGE, has_next=bool(nxt) and bool(rows)),
    }


def campaigns_list(**data):
    return cached_call("whop.campaigns_list", data, _campaigns_list, ttl.CAMPAIGNS_CACHE)


def _campaign_details(campaign):
    record = parsers.parse_campaign(fetch.fetch_campaign(campaign))
    if record is None:
        raise WhopNotFound(f"campaign {campaign} not found")
    return record


def campaign_details(**data):
    return cached_call("whop.campaign_details", data, _campaign_details, ttl.CAMPAIGN_CACHE)
