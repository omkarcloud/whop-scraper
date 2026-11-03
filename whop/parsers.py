"""Raw gateway JSON -> clean dicts for every /whop/* endpoint. Pure
functions, no I/O; every function tolerates a partial record.

Value conventions (shared with the other scraper packages):
  * dates    Whop's unix seconds and Content Rewards' ISO strings both come
             out as ISO-8601 UTC ("2026-11-03T09:28:21Z")
  * money    numbers; Whop prices carry their own `currency` (lower-case ISO
             from the gateway, upper-cased here), Content Rewards cents
             become dollars (every campaign is priced in USD)
  * keys     snake_case; `link` not `url`; booleans as questions
  * absent   null, never "" / "N/A" / a missing key
  * ratings  reviewCounts is the gateway's [5★, 4★, 3★, 2★, 1★] histogram

Fixtures captured 2026-11-03 (whop/fixtures/): raw records from
data.whop.com/graphql (search, catalog pages, products, companies,
reviews, members, categories, users, leaderboards, apps, bounties, slug
resolutions, not-found errors) and contentrewards.com (two feed pages,
filtered / empty feeds, two campaign records, a not-found). See
test_parsers.py for which fixture exercises which parser.
"""
from datetime import datetime, timezone

from whop.refs import (SITE, app_link, campaign_link, company_link, organization_link,
                       product_link, user_link)

CR_CDN = "https://crusercontent.com/"


# ---- value helpers ----------------------------------------------------------------

def _get(obj, *keys, default=None):
    """Nested .get() that survives None / non-dict links."""
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return default if obj is None else obj


def _str(value):
    if value is None:
        return None
    value = " ".join(str(value).split())
    return value or None


def _text(value):
    """Multi-line text: keep the line breaks, trim the edges, "" -> None."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).replace(",", "").strip()
        return float(text) if "." in text else int(text)
    except ValueError:
        return None


def _int(value):
    value = _num(value)
    return int(value) if isinstance(value, (int, float)) else None


def _bool(value):
    return value if isinstance(value, bool) else None


def iso_from_unix(value):
    """Unix seconds (int / numeric string) -> ISO-8601 UTC; None otherwise."""
    value = _num(value)
    if value is None or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def iso_from_ms(value):
    value = _num(value)
    return iso_from_unix(value / 1000) if value else None


def iso_from_text(value):
    """"2026-11-03T09:28:21.000Z" -> "2026-11-03T09:28:21Z"; None otherwise."""
    value = _str(value)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _currency(value):
    value = _str(value)
    return value.upper() if value else None


def _dollars(cents):
    cents = _num(cents)
    return round(cents / 100.0, 2) if cents is not None else None


def _cdn(path):
    """Content Rewards stores bare storage paths; absolute links pass through."""
    path = _str(path)
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return CR_CDN + path.lstrip("/")


def _image(node):
    return _str(_get(node, "sourceUrl"))


def _histogram(counts):
    """[5★, 4★, 3★, 2★, 1★] -> {"5": n, ..., "1": n}; None when absent."""
    if not isinstance(counts, list) or len(counts) < 5:
        return None
    return {str(5 - i): _int(counts[i]) for i in range(5)}


def _rating(node):
    return {
        "average": _num(_get(node, "reviewsAverage")),
        "count": _int(_get(node, "publishedReviewsCount")),
    }


# ---- plans / prices ---------------------------------------------------------------

def parse_plan_card(plan):
    """The defaultPlan of a product card: price, currency, cadence."""
    if not isinstance(plan, dict):
        return None
    return {
        "id": _str(plan.get("id")),
        "text": _str(plan.get("formattedPrice")),
        "currency": _currency(plan.get("baseCurrency")),
        "type": _str(plan.get("planType")),
        "initial_amount": _num(plan.get("rawInitialPrice")),
        "renewal_amount": _num(plan.get("rawRenewalPrice")),
        "billing_period_days": _int(plan.get("billingPeriod")),
        "period_text": _str(plan.get("formattedPeriodV2")),
        "release_method": _str(plan.get("releaseMethod")),
        "is_free": _bool(plan.get("free")),
        "trial_days": _int(plan.get("trialPeriodDays")),
    }


def parse_plan(plan):
    """A full PublicPlan (product details / app details)."""
    if not isinstance(plan, dict):
        return None
    card = parse_plan_card(plan)
    card.update({
        "name": _str(plan.get("title")),
        "description": _text(plan.get("description")),
        "initial_amount_usd": _num(plan.get("rawInitialPriceUsd")),
        "renewal_amount_usd": _num(plan.get("rawRenewalPriceUsd")),
        "due_now_amount": _dollars(plan.get("initialPriceDueInCents")),
        "strike_through_initial_amount": _num(plan.get("strikeThroughInitialPrice")),
        "strike_through_renewal_amount": _num(plan.get("strikeThroughRenewalPrice")),
        "expiration_days": _int(plan.get("expirationDays")),
        "stock": _int(plan.get("stock")),
        "is_unlimited_stock": _bool(plan.get("unlimitedStock")),
        "is_in_stock": _bool(plan.get("inStock")),
        "low_stock_warning": _num(plan.get("lowStockWarning")),
        "split_pay_payments": _int(plan.get("splitPayRequiredPayments")),
        "allows_multiple_quantity": _bool(plan.get("allowMultipleQuantity")),
        "payment_methods": plan.get("acceptedPaymentMethods") if isinstance(plan.get("acceptedPaymentMethods"), list) else [],
        "visibility": _str(plan.get("visibility")),
        "checkout_link": _str(plan.get("directLink")),
        "created_at": iso_from_unix(plan.get("createdAt")),
    })
    return card


# ---- shared cards -----------------------------------------------------------------

def _company_ref(node):
    """The company stub carried by products / reviews / apps."""
    if not isinstance(node, dict) or not node.get("id"):
        return None
    route = _str(node.get("route"))
    out = {"id": _str(node.get("id")), "title": _str(node.get("title")), "route": route,
           "link": company_link(route)}
    if "verified" in node:
        out["is_verified"] = _bool(node.get("verified"))
    if "memberCount" in node:
        out["members"] = _int(node.get("memberCount"))
    if "publishedReviewsCount" in node or "reviewsAverage" in node:
        out["rating"] = _rating(node)
    if "logo" in node:
        out["logo"] = _image(node.get("logo"))
    return out


def parse_user_card(node):
    if not isinstance(node, dict) or not node.get("id"):
        return None
    username = _str(node.get("username"))
    out = {"id": _str(node.get("id")), "username": username, "name": _str(node.get("name")),
           "link": user_link(username)}
    if "followersCount" in node:
        out["followers"] = _int(node.get("followersCount"))
    if "verifiedAt" in node:
        out["is_verified"] = node.get("verifiedAt") is not None
    if "profilePicture" in node:
        out["avatar"] = _image(node.get("profilePicture"))
    return out


def parse_product_card(node):
    """A PublicAccessPass card (search hit, catalog row, leaderboard entry,
    a company's visible product)."""
    if not isinstance(node, dict) or not node.get("id"):
        return None
    company = node.get("company") if isinstance(node.get("company"), dict) else {}
    route = _str(node.get("route"))
    company_route = _str(company.get("route"))
    images = [_str(i.get("url")) for i in node.get("images") or [] if isinstance(i, dict) and i.get("url")]
    return {
        "id": _str(node.get("id")),
        "title": _str(node.get("title")),
        "route": route,
        "link": product_link(company_route, route),
        "headline": _str(node.get("headline")),
        "description": _text(node.get("shortenedDescription")),
        "type": _str(node.get("accessPassType")),
        "business_type": _str(node.get("businessType")),
        "industry_type": _str(node.get("industryType")),
        "marketplace_status": _str(node.get("marketplaceStatus")),
        "is_verified": _bool(node.get("verified")),
        "ranking": _int(node.get("whopRanking")),
        "members": _int(node.get("memberCount")),
        "active_members": _int(node.get("activeUsersCount")),
        "rating": _rating(node),
        "revenue": {
            "usd_gmv": _num(node.get("usdGmv")),
            "last_24_hours_usd": _num(node.get("last24HoursGmv")),
        },
        "has_free_plan": _bool(node.get("hasFreeAvailablePlan")),
        "has_paid_plan": _bool(node.get("hasPaidAvailablePlan")),
        "affiliate_percentage": _num(node.get("globalAffiliatePercentage")),
        "price": parse_plan_card(node.get("defaultPlan")),
        "logo": _image(node.get("logo")),
        "images": images,
        "company": _company_ref(company),
        "created_at": iso_from_unix(node.get("createdAt")),
        "discoverable_at": iso_from_unix(node.get("discoverableAt")),
    }


def parse_company_card(node):
    """A PublicCompany card (search hit, popular / verified / affiliate
    lists, a user's owned / joined whops)."""
    if not isinstance(node, dict) or not node.get("id"):
        return None
    route = _str(node.get("route"))
    out = {
        "id": _str(node.get("id")),
        "title": _str(node.get("title")),
        "route": route,
        "link": company_link(route),
        "pitch": _text(node.get("creatorPitch")),
        "business_type": _str(node.get("businessType")),
        "industry_type": _str(node.get("industryType")),
        "is_verified": _bool(node.get("verified")),
        "members": _int(node.get("memberCount")),
        "rating": _rating(node),
        "logo": _image(node.get("logo")),
        "owner": parse_user_card(node.get("ownerUser")),
        "created_at": iso_from_unix(node.get("createdAt")),
    }
    if "affiliateTotalEarned" in node:
        out["affiliate"] = {
            "total_earned_usd": _num(node.get("affiliateTotalEarned")),
            "total_clicks": _int(node.get("affiliateTotalClicks")),
            "total_conversions": _int(node.get("affiliateTotalConversions")),
            "is_enabled": _bool(node.get("hasGlobalAffiliatesEnabled")),
        }
    if "totalEarningsWithTransfersInUsd" in node:
        out["total_earnings_usd"] = _num(node.get("totalEarningsWithTransfersInUsd"))
    return out


def parse_review(node):
    if not isinstance(node, dict) or not node.get("id"):
        return None
    product = node.get("accessPass") if isinstance(node.get("accessPass"), dict) else {}
    company = node.get("company") if isinstance(node.get("company"), dict) else {}
    return {
        "id": _str(node.get("id")),
        "stars": _int(node.get("stars")),
        "title": _str(node.get("title")),
        "text": _text(node.get("description")),
        "is_verified_purchase": _bool(node.get("paidForProduct")),
        "is_featured": _bool(node.get("featured")),
        "is_whop_reviewed": _bool(node.get("whopReviewed")),
        "upvotes": _int(node.get("upvotes")),
        "replies": _int(node.get("replyCount")),
        "reviewer": parse_user_card(node.get("userAccount")),
        "product": {
            "id": _str(product.get("id")), "title": _str(product.get("title")),
            "route": _str(product.get("route")),
            "link": product_link(_str(company.get("route")), _str(product.get("route"))),
        } if product.get("id") else None,
        "company": _company_ref(company),
        "attachments": [_image(a) for a in node.get("attachments") or [] if _image(a)],
        "joined_at": iso_from_unix(node.get("joinedAt")),
        "published_at": iso_from_unix(node.get("publishedAt")),
        "created_at": iso_from_unix(node.get("createdAt")),
    }


def parse_app_card(node):
    if not isinstance(node, dict) or not node.get("id"):
        return None
    product = node.get("accessPass") if isinstance(node.get("accessPass"), dict) else {}
    category = product.get("marketplaceCategory") if isinstance(product.get("marketplaceCategory"), dict) else {}
    stats = node.get("stats") if isinstance(node.get("stats"), dict) else {}
    return {
        "id": _str(node.get("id")),
        "name": _str(node.get("name")),
        "link": app_link(_str(node.get("id"))),
        "description": _text(node.get("description")),
        "type": _str(node.get("appType")),
        "status": _str(node.get("status")),
        "marketplace_status": _str(node.get("marketplaceStatus")),
        "is_verified": _bool(node.get("verified")),
        "category": {"id": _str(category.get("id")), "name": _str(category.get("name")),
                     "route": _str(category.get("route"))} if category.get("route") else None,
        "installs": {
            "total": _int(node.get("totalInstalls")),
            "last_7_days": _int(node.get("totalInstallsLast7Days")),
            "last_30_days": _int(node.get("totalInstallsLast30Days")),
        },
        "usage": {
            "daily_active_users": _int(stats.get("dau")),
            "weekly_active_users": _int(stats.get("wau")),
            "monthly_active_users": _int(stats.get("mau")),
            "time_spent_last_24_hours_seconds": _int(stats.get("timeSpentLast24HoursInSeconds")),
        },
        "ai": {
            "prompt_count": _int(node.get("aiPromptCount")),
            "average_rating": _num(node.get("aiAverageRating")),
            "rating_count": _int(node.get("aiRatingCount")),
        },
        "rating": _rating(product),
        "icon": _image(node.get("icon")),
        "store_product": {
            "id": _str(product.get("id")), "title": _str(product.get("title")),
            "route": _str(product.get("route")), "headline": _str(product.get("headline")),
        } if product.get("id") else None,
        "creator": parse_user_card(node.get("creator")),
        "company": _company_ref(node.get("company")),
        "discoverable_at": iso_from_unix(node.get("discoverableAt")),
    }


# ---- search / catalog ----------------------------------------------------------------

def parse_search(payload, companies=False):
    """discoveryImprovedPipelineV3 -> (total found, [cards])."""
    payload = payload if isinstance(payload, dict) else {}
    key = "companies" if companies else "accessPasses"
    parse = parse_company_card if companies else parse_product_card
    rows = [parse(n) for n in payload.get(key) or []]
    return _int(payload.get("found")), [r for r in rows if r]


def parse_connection(payload, parse):
    """A graphql-ruby connection {totalCount, pageInfo, nodes} ->
    (total, has_next, [parsed])."""
    payload = payload if isinstance(payload, dict) else {}
    rows = [parse(n) for n in payload.get("nodes") or []]
    return (_int(payload.get("totalCount")), _bool(_get(payload, "pageInfo", "hasNextPage")),
            [r for r in rows if r])


# ---- product details ----------------------------------------------------------------

def parse_product(node):
    node = node if isinstance(node, dict) else {}
    card = parse_product_card(node)
    if card is None:
        return None
    company = node.get("company") if isinstance(node.get("company"), dict) else {}
    category = node.get("marketplaceCategory") if isinstance(node.get("marketplaceCategory"), dict) else {}
    subcategory = node.get("subcategory") if isinstance(node.get("subcategory"), dict) else {}
    tax = node.get("productTaxCode") if isinstance(node.get("productTaxCode"), dict) else {}
    plans = node.get("visiblePlans") if isinstance(node.get("visiblePlans"), dict) else {}
    highlights = _get(node, "productHighlights", "nodes", default=[]) or []
    gallery = [_image(g) for g in node.get("galleryImages") or [] if _image(g)]
    card.update({
        "full_description": _text(node.get("description")),
        "pitch": _text(node.get("creatorPitch")),
        "labels": [l for l in node.get("labels") or [] if isinstance(l, str)],
        "category": {"id": _str(category.get("id")), "name": _str(category.get("name")),
                     "route": _str(category.get("route"))} if category.get("route") else None,
        "subcategory": {"id": _str(subcategory.get("id")), "name": _str(subcategory.get("name")),
                        "route": _str(subcategory.get("route"))} if subcategory.get("route") else None,
        "tax_code": {"name": _str(tax.get("name")), "product_type": _str(tax.get("productType"))}
        if tax else None,
        "rating": {
            **_rating(node),
            "average_all_time": _num(node.get("averageReviewRating")),
            "histogram": _histogram(node.get("reviewCounts")),
        },
        "likes": _int(node.get("likeCount")),
        "shares": _int(node.get("shareCount")),
        "total_bounty_amount_usd": _num(node.get("totalBountyAmount")),
        "is_free_to_join": _bool(node.get("isFreeAndJoinableWithoutRequirements")),
        "affiliate": {
            "status": _str(node.get("globalAffiliateStatus")),
            "percentage": _num(node.get("globalAffiliatePercentage")),
            "member_status": _str(node.get("memberAffiliateStatus")),
            "member_percentage": _num(node.get("memberAffiliatePercentage")),
        },
        "call_to_action": {"type": _str(node.get("customCta")), "link": _str(node.get("customCtaUrl"))},
        "redirect_purchase_link": _str(node.get("redirectPurchaseUrl")),
        "direct_link": _str(node.get("directLink")),
        "shows_member_count": _bool(node.get("showMemberCount")),
        "shows_reviews": _bool(node.get("showReviewsDtc")),
        "collects_shipping_address": _bool(node.get("collectShippingAddress")),
        "banner": _image(node.get("bannerImage")),
        "gallery": gallery or card["images"],
        "plans_count": _int(node.get("visiblePlansCount")) or _int(plans.get("totalCount")),
        "plans": [p for p in (parse_plan(p) for p in plans.get("nodes") or []) if p],
        "faq": [{"question": _str(f.get("question")), "answer": _text(f.get("answer"))}
                for f in node.get("faq") or [] if isinstance(f, dict)],
        "highlights": [{"title": _str(h.get("title")), "content": _text(h.get("content")),
                        "type": _str(h.get("highlightType"))}
                       for h in highlights if isinstance(h, dict)],
        "experiences": [parse_experience(e) for e in node.get("experiences") or [] if isinstance(e, dict)],
        "social_links": parse_social_links(node.get("socialLinks")),
        "owner": parse_user_card(node.get("ownerUser")),
        "latest_review": parse_review(node.get("mostRecentReview")),
        "first_approved_at": iso_from_unix(node.get("firstApprovedAt")),
        "updated_at": iso_from_unix(node.get("updatedAt")),
    })
    # one `company` block with the richer fields the details query asks for
    card["company"] = _company_ref(company)
    del card["affiliate_percentage"]
    return card


def parse_experience(node):
    """An experience = one app installed in a community (chat, forum,
    course, files…)."""
    app = node.get("app") if isinstance(node.get("app"), dict) else {}
    out = {
        "id": _str(node.get("id")),
        "name": _str(node.get("name")),
        "description": _text(node.get("description")),
        "app": {"id": _str(app.get("id")), "name": _str(app.get("name"))} if app.get("id") else None,
        "is_public": _bool(node.get("isPublic")),
    }
    if "userCount" in node:
        out["members"] = _int(node.get("userCount"))
    if "accessPasses" in node:
        out["products"] = [{"id": _str(p.get("id")), "title": _str(p.get("title")),
                            "route": _str(p.get("route"))}
                           for p in node.get("accessPasses") or [] if isinstance(p, dict)]
    return out


def parse_social_links(links):
    out = []
    for link in links or []:
        if not isinstance(link, dict):
            continue
        out.append({"site": _str(link.get("website")), "link": _str(link.get("url")),
                    "title": _str(link.get("title"))})
    return out


# ---- company details --------------------------------------------------------------------

def parse_company(node):
    node = node if isinstance(node, dict) else {}
    card = parse_company_card(node)
    if card is None:
        return None
    owner = node.get("ownerUser") if isinstance(node.get("ownerUser"), dict) else {}
    forum = node.get("publicForumExperience") if isinstance(node.get("publicForumExperience"), dict) else {}
    primary = node.get("primaryExperience") if isinstance(node.get("primaryExperience"), dict) else {}
    store = node.get("storePageConfig") if isinstance(node.get("storePageConfig"), dict) else {}
    team = node.get("publicTeamMembers") if isinstance(node.get("publicTeamMembers"), dict) else {}
    experiences = _get(node, "experienceList", "experiences", default=[]) or []
    products = [parse_product_card(p) for p in node.get("visibleAccessPassesV2") or []]
    products = [p for p in products if p]
    card.update({
        "description": _text(node.get("businessDescription")),
        "target_audience": _text(node.get("targetAudience")),
        "rating": {**_rating(node), "histogram": _histogram(node.get("reviewCounts"))},
        "total_views": _int(node.get("cachedTotalViewsCount")),
        "revenue": {
            "last_30_days_usd": _num(node.get("usdGmv30Days")),
            "total_earnings_usd": _num(node.get("totalEarningsWithTransfersInUsd")),
        },
        "is_launched": _bool(node.get("launched")),
        "are_purchases_disabled": bool(node.get("purchasesDisabled")) if node.get("purchasesDisabled") is not None else False,
        "disabled_reason": _str(node.get("disabledReason")),
        "affiliate": {
            "is_enabled": _bool(node.get("hasGlobalAffiliatesEnabled")),
            "requires_application": _bool(node.get("affiliateApplicationRequired")),
        },
        "features": [f for f in node.get("features") or [] if isinstance(f, str)],
        "banner": _image(node.get("bannerImage")),
        "store_page": {"accent_color": _str(store.get("accentColor")),
                       "layout": _str(store.get("layout"))},
        "owner": {
            **(parse_user_card(owner) or {}),
            "bio": _text(owner.get("bio")),
            "city": _str(owner.get("city")),
            "country": _str(owner.get("country")),
            "created_at": iso_from_unix(owner.get("createdAt")),
        } if owner.get("id") else None,
        "social_links": parse_social_links(node.get("socialLinks")),
        "public_forum": {"id": _str(forum.get("id")), "name": _str(forum.get("name"))}
        if forum.get("id") else None,
        "primary_experience": {"id": _str(primary.get("id")), "name": _str(primary.get("name"))}
        if primary.get("id") else None,
        "team_count": _int(team.get("totalCount")),
        "team": [{"role": _str(t.get("role")), **(parse_user_card(t.get("user")) or {})}
                 for t in team.get("nodes") or [] if isinstance(t, dict) and _get(t, "user", "id")],
        "products_count": len(products),
        "products": products,
        "experiences": [parse_experience(e) for e in experiences if isinstance(e, dict)],
        "updated_at": iso_from_unix(node.get("updatedAt")),
    })
    card.pop("total_earnings_usd", None)   # lives in `revenue` here
    return card


def parse_member(node):
    if not isinstance(node, dict):
        return None
    profile = node.get("profile") if isinstance(node.get("profile"), dict) else {}
    user = parse_user_card(profile)
    if not user:
        return None
    user.update({
        "member_id": _str(node.get("id")),
        "city": _str(profile.get("city")),
        "country": _str(profile.get("country")),
        "joined_whop_at": iso_from_unix(profile.get("createdAt")),
    })
    return user


# ---- categories --------------------------------------------------------------------------

def parse_category(node):
    if not isinstance(node, dict) or not node.get("route"):
        return None
    parent = node.get("parentMarketplaceCategory") if isinstance(node.get("parentMarketplaceCategory"), dict) else {}
    return {
        "id": _str(node.get("id")),
        "name": _str(node.get("name")),
        "route": _str(node.get("route")),
        "level": _int(node.get("level")),
        "tagline": _str(node.get("tagline")),
        "description": _text(node.get("description")),
        "products_count": _int(node.get("liveAccessPassCount")),
        "is_on_homepage": _bool(node.get("displayOnHomepage")),
        "parent": {"id": _str(parent.get("id")), "name": _str(parent.get("name")),
                   "route": _str(parent.get("route"))} if parent.get("route") else None,
    }


# ---- users -------------------------------------------------------------------------------

def parse_user(node):
    node = node if isinstance(node, dict) else {}
    card = parse_user_card(node)
    if card is None:
        return None
    prefs = node.get("userPreferences") if isinstance(node.get("userPreferences"), dict) else {}
    owned = node.get("ownedWhops") if isinstance(node.get("ownedWhops"), dict) else {}
    joined = node.get("joinedWhops") if isinstance(node.get("joinedWhops"), dict) else {}
    social = _get(node, "socialLinks", "nodes", default=[]) or []
    card.update({
        "bio": _text(node.get("bio")),
        "city": _str(node.get("city")),
        "country": _str(node.get("country")),
        "country_name": _str(node.get("countryName")),
        "roles": [r for r in node.get("roles") or [] if isinstance(r, str)],
        "is_suspended": _bool(node.get("isSuspended")),
        "following": _int(node.get("followingCount")),
        "reviews_written": _int(_get(node, "reviews", "totalCount")),
        "referrals": _int(node.get("primaryUserReferralCount")),
        "lifetime_earnings_usd": _num(_get(node, "userStat", "moneyEarnedLifetime")),
        "average_response_time_seconds": _int(node.get("averageResponseTimeInSeconds")),
        "banner": _image(node.get("banner")),
        "social_links": [{"site": _str(s.get("website")), "link": _str(s.get("url")),
                          "username": _str(s.get("username")), "is_verified": _bool(s.get("verified"))}
                         for s in social if isinstance(s, dict)],
        "preferences": {
            "shows_earnings": _bool(prefs.get("showEarnings")),
            "shows_owned_whops": _bool(prefs.get("showOwnedWhops")),
            "shows_joined_whops": _bool(prefs.get("showJoinedWhops")),
            "shows_location": _bool(prefs.get("showLocation")),
        },
        "owned_whops_count": _int(owned.get("totalCount")),
        "owned_whops": [c for c in (parse_company_card(n) for n in owned.get("nodes") or []) if c],
        "joined_whops_count": _int(joined.get("totalCount")),
        "joined_whops": [c for c in (parse_company_card(n) for n in joined.get("nodes") or []) if c],
        "verified_at": iso_from_unix(node.get("verifiedAt")),
        "last_seen_at": iso_from_unix(node.get("lastSeenAt")),
        "created_at": iso_from_unix(node.get("createdAt")),
    })
    return card


# ---- leaderboards -----------------------------------------------------------------------

def parse_leaderboard(payload):
    payload = payload if isinstance(payload, dict) else {}
    rows = []
    for entry in payload.get("results") or []:
        if not isinstance(entry, dict):
            continue
        rows.append({
            "rank": _int(entry.get("currentRank")),
            "previous_rank": _int(entry.get("previousRank")),
            "score": _num(entry.get("currentScore")),
            "previous_score": _num(entry.get("previousScore")),
            "product": parse_product_card(entry.get("accessPass")),
            "user": parse_user_card(entry.get("user")),
        })
    return _str(payload.get("leaderboardType")), _int(payload.get("totalCount")), rows


# ---- apps ---------------------------------------------------------------------------------

def parse_app(node):
    node = node if isinstance(node, dict) else {}
    card = parse_app_card(node)
    if card is None:
        return None
    product = node.get("accessPass") if isinstance(node.get("accessPass"), dict) else {}
    card.update({
        "store_description": _text(node.get("appStoreDescription")),
        "ai_generated_description": _text(node.get("aiGeneratedDescription")),
        "product_page_text": _text(node.get("productPageText")),
        "default_experience_description": _text(node.get("defaultExperienceDescription")),
        "internal_identifier": _str(node.get("internalIdentifier")),
        "hosted_link": _str(node.get("hostedUrl")),
        "base_link": _str(node.get("baseUrl")),
        "capabilities": [c for c in node.get("capabilities") or [] if isinstance(c, str)],
        "uses_default_icon": _bool(node.get("usingDefaultIcon")),
        "rating": {**_rating(product), "histogram": _histogram(product.get("reviewCounts"))},
        "store_product": {
            "id": _str(product.get("id")), "title": _str(product.get("title")),
            "route": _str(product.get("route")), "headline": _str(product.get("headline")),
            "description": _text(product.get("shortenedDescription") or product.get("description")),
            "members": _int(product.get("memberCount")),
            "active_members": _int(product.get("activeUsersCount")),
            "price": parse_plan(product.get("defaultPlan")),
            "gallery": [_image(g) for g in product.get("galleryImages") or [] if _image(g)],
            "company": _company_ref(product.get("company")),
            "created_at": iso_from_unix(product.get("createdAt")),
        } if product.get("id") else None,
    })
    card["ai"]["total_tokens"] = _int(node.get("totalAiTokens"))
    card["ai"]["last_prompt_at"] = iso_from_unix(node.get("lastAiPromptAt"))
    return card


# ---- bounties -----------------------------------------------------------------------------

def parse_bounty(node):
    if not isinstance(node, dict) or not node.get("id"):
        return None
    experience = node.get("experience") if isinstance(node.get("experience"), dict) else {}
    products = _get(node, "accessPasses", "nodes", default=[]) or []
    platforms = [name for name, key in (("tiktok", "allowTiktok"), ("youtube", "allowYoutube"),
                                        ("instagram", "allowInstagram"), ("x", "allowX"))
                 if node.get(key) is True]
    return {
        "id": _str(node.get("id")),
        "title": _str(node.get("title")),
        "description": _text(node.get("description")),
        "type": _str(node.get("bountyType")),
        "status": _str(node.get("status")),
        "discover_status": _str(node.get("discoverStatus")),
        "business_goal": _str(node.get("businessGoalType")),
        "reward": {
            "amount": _num(node.get("rewardPerUnitAmount")),
            "unit": _str(node.get("rewardUnit")),
            "currency": _currency(node.get("currency")),
            "budget": _num(node.get("budgetAmount")),
            "total_paid": _num(node.get("totalPaid")),
        },
        "spots_remaining": _int(node.get("spotsRemaining")),
        "submissions": {
            "total": _int(node.get("bountySubmissionsCount")),
            "accepted": _int(node.get("acceptedSubmissionsCount")),
            "accepted_limit": _int(node.get("acceptedSubmissionsLimit")),
            "active": _int(node.get("activeSubmissionsCount")),
            "awaiting_review": _int(node.get("awaitingReviewSubmissionsCount")),
            "denied": _int(node.get("deniedSubmissionsCount")),
        },
        "platforms": platforms,
        "allowed_countries": [c for c in node.get("allowedCountryCodes") or [] if isinstance(c, str)],
        "required_capture_duration_seconds": _int(node.get("requiredCaptureDurationSeconds")),
        "schedule": _str(node.get("scheduledFrequency")),
        "views": _int(node.get("viewCount")),
        "comments": _int(node.get("commentCount")),
        "reactions": _int(node.get("reactionCount")),
        "experience": {"id": _str(experience.get("id")), "name": _str(experience.get("name"))}
        if experience.get("id") else None,
        "company": _company_ref(experience.get("company")),
        "products": [{"id": _str(p.get("id")), "title": _str(p.get("title")), "route": _str(p.get("route"))}
                     for p in products if isinstance(p, dict)],
        "poster": parse_user_card(node.get("user")),
        "created_at": iso_from_unix(node.get("createdAt")),
        "updated_at": iso_from_unix(node.get("updatedAt")),
    }


# ---- Content Rewards campaigns ---------------------------------------------------------

def _payouts(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "platform": _str(row.get("platform")),
            "type": _str(row.get("payoutType")),
            "rate_per_1k_views_usd": _dollars(row.get("rateCents")) if _str(row.get("payoutType")) == "cpm" else None,
            "min_payout_usd": _dollars(row.get("minPayoutCents")),
            "max_payout_usd": _dollars(row.get("maxPayoutCents")),
        })
    return out


def _chart(points):
    out = []
    for point in points or []:
        if not isinstance(point, dict):
            continue
        day = _str(point.get("bucket"))
        out.append({"date": day[:10] if day else None, "views": _int(point.get("totalViews")),
                    "approved_clips": _int(point.get("approvedSubmissionCount"))})
    return out


def _top_clips(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "rank": _int(row.get("rank")),
            "platform": _str(row.get("platform")),
            "title": _str(row.get("title")),
            "link": _str(row.get("postUrl")),
            "views": _int(row.get("totalViews")),
            "creator": {"id": _str(row.get("userId")), "username": _str(row.get("username")),
                        "avatar": _cdn(row.get("avatarUrl"))},
            "thumbnail": _cdn(row.get("thumbnailUrl")),
            "video": _cdn(row.get("videoUrl")),
        })
    return out


def _top_earners(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "rank": _int(row.get("rank")),
            "creator": {"id": _str(row.get("userId")), "username": _str(row.get("username")),
                        "whop_username": _str(row.get("whopUsername")),
                        "avatar": _cdn(row.get("avatarUrl"))},
            "earned_usd": _dollars(row.get("earnedCents")),
            "views": _int(row.get("totalViews")),
            "approved_clips": _int(row.get("approvedSubmissionCount")),
        })
    return out


def _pool_split(split):
    if not isinstance(split, dict):
        return None
    return {
        "creators": _int(split.get("creatorCount")),
        "top_shares_percent": [round(_num(b) / 100.0, 2) for b in split.get("topShareBps") or [] if _num(b) is not None],
        "others_share_percent": round(_num(split.get("otherShareBps")) / 100.0, 2)
        if _num(split.get("otherShareBps")) is not None else None,
        "is_final": _bool(split.get("final")),
    }


def parse_campaign_card(node, with_metrics_detail=True):
    """One discover-feed row (view=full). `with_metrics_detail=False` keeps
    the list rows light (no chart / top clips / top earners)."""
    if not isinstance(node, dict) or not node.get("id"):
        return None
    metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
    group = node.get("group") if isinstance(node.get("group"), dict) else {}
    budget_total = _dollars(node.get("budgetCents"))
    budget_spent = _dollars(metrics.get("budgetSpentCents"))
    remaining = (round(budget_total - budget_spent, 2)
                 if budget_total is not None and budget_spent is not None else None)
    brief = node.get("briefCounts") if isinstance(node.get("briefCounts"), dict) else {}
    handle = _str(node.get("organizationProfileHandle"))
    payout_type = _str(node.get("payoutType"))
    # pool / retainer campaigns carry 0-cent CPM placeholders: no rate, not a free rate
    rate = (lambda key: _dollars(node.get(key)) if payout_type == "cpm" else None)
    out = {
        "id": _str(node.get("id")),
        "title": _str(node.get("name")),
        "link": campaign_link(_str(node.get("id"))),
        "description": _text(node.get("description")),
        "status": _str(node.get("status")),
        "payout_type": payout_type,
        "platforms": [p for p in node.get("platforms") or [] if isinstance(p, str)],
        "categories": [{"id": _str(c.get("id")), "name": _str(c.get("name"))}
                       for c in node.get("categories") or [] if isinstance(c, dict)],
        "reward": {
            "primary_rate_per_1k_views_usd": rate("primaryPayoutCents"),
            "min_rate_per_1k_views_usd": rate("cpmMinRateCents"),
            "max_rate_per_1k_views_usd": rate("cpmMaxRateCents"),
            "is_geo_priced": _bool(node.get("geoPriced")),
            "payouts": _payouts(node.get("payouts")),
        },
        "budget": {
            "total_usd": budget_total,
            "spent_usd": budget_spent,
            "remaining_usd": remaining,
            "progress_percent": round(_num(metrics.get("budgetProgressBps")) / 100.0, 2)
            if _num(metrics.get("budgetProgressBps")) is not None else None,
            "paid_out_usd": _dollars(metrics.get("paidOutCents")),
        },
        "metrics": {
            "creators": _int(metrics.get("creatorCount")),
            "approved_clips": _int(metrics.get("approvedSubmissionCount")),
            "total_views": _int(metrics.get("totalViews")),
            "updated_at": iso_from_text(metrics.get("metricsUpdatedAt")),
        },
        "requires_application": _bool(node.get("requiresApplication")),
        "is_private": _bool(node.get("private")),
        "retainer_spots": _int(node.get("retainerSpotsTotal")),
        "featured_score": _int(node.get("featuredScore")),
        "brief": {
            "content_rules": _int(brief.get("contentRules")),
            "creator_requirements": _int(brief.get("creatorRequirements")),
            "references": _int(brief.get("references")),
        },
        "banner": _cdn(node.get("banner")),
        "organization": {
            "id": _str(node.get("organizationId")),
            "name": _str(node.get("organizationName")),
            "handle": handle,
            "link": organization_link(handle),
            "is_verified": _bool(node.get("organizationVerified")),
            "logo": _cdn(node.get("organizationLogoUrl")),
            "whop_experience_id": _str(node.get("organizationExperienceId")),
        },
        "group": {
            "id": _str(group.get("id")), "name": _str(group.get("name")),
            "description": _text(group.get("description")),
            "campaign_ids": [c for c in group.get("campaignIds") or [] if isinstance(c, str)],
            "cover": _cdn(group.get("cover")),
        } if group.get("id") else None,
        "launched_at": iso_from_text(node.get("launchDate")),
        "listed_at": iso_from_text(node.get("listedAt")),
        "created_at": iso_from_text(node.get("createdAt")),
        "updated_at": iso_from_text(node.get("updatedAt")),
    }
    if with_metrics_detail:
        out["metrics"]["pool_split"] = _pool_split(metrics.get("poolSplit"))
        out["metrics"]["daily"] = _chart(metrics.get("chartPoints"))
        out["metrics"]["top_clips"] = _top_clips(metrics.get("topClips"))
        out["metrics"]["top_earners"] = _top_earners(metrics.get("topEarners"))
    return out


def parse_campaigns_page(payload, with_metrics_detail=False):
    """A discover-feed page -> (rows, next cursor)."""
    payload = payload if isinstance(payload, dict) else {}
    rows = [parse_campaign_card(c, with_metrics_detail) for c in payload.get("data") or []]
    return [r for r in rows if r], _str(_get(payload, "pagination", "nextCursor"))


def parse_campaign(bundle):
    """The discover card + the campaign record -> one campaign."""
    bundle = bundle if isinstance(bundle, dict) else {}
    card = parse_campaign_card(bundle.get("card"), with_metrics_detail=True)
    record = bundle.get("record") if isinstance(bundle.get("record"), dict) else {}
    if card is None and not record.get("id"):
        return None
    if card is None:
        card = {"id": _str(record.get("id")), "title": _str(record.get("name")),
                "link": campaign_link(_str(record.get("id"))),
                "description": _text(record.get("description")),
                "status": _str(record.get("status")), "metrics": {}, "organization": {}}
    conf = record.get("configuration") if isinstance(record.get("configuration"), dict) else {}
    org = record.get("organization") if isinstance(record.get("organization"), dict) else {}
    content = conf.get("content") if isinstance(conf.get("content"), dict) else {}
    creator = conf.get("creator") if isinstance(conf.get("creator"), dict) else {}
    display = conf.get("display") if isinstance(conf.get("display"), dict) else {}
    requirement = conf.get("requirement") if isinstance(conf.get("requirement"), dict) else {}
    card.update({
        "type": _str(record.get("type")) or card.get("payout_type"),
        "status_reason": _str(record.get("statusReason")),
        "status_changed_at": iso_from_text(record.get("statusChangedAt")),
        "fee_schedule": _str(record.get("feeSchedule")),
        "platform_fee_percent": round(_num(conf.get("fee")) / 100.0, 2)
        if _num(conf.get("fee")) is not None else None,
        "is_shown_on_discover": _bool(record.get("showOnDiscover")),
        "is_shown_before_launch": _bool(record.get("showBeforeLaunch")),
        "content_types": [_str(c.get("name")) for c in content.get("contentTypes") or [] if isinstance(c, dict)],
        "content_categories": [_str(c.get("name")) for c in content.get("contentCategories") or [] if isinstance(c, dict)],
        "creator_types": [_str(c.get("name")) for c in creator.get("creatorTypes") or [] if isinstance(c, dict)],
        "requirements": {
            "needs_pre_approval": _bool(requirement.get("preApproval")),
            "min_clip_views": _int(conf.get("minClipViews")),
            "min_creator_views": _int(conf.get("minCreatorViews")),
            "payout_platforms": [_str(p.get("platform")) for p in conf.get("payoutModel") or [] if isinstance(p, dict)],
        },
        "display": {
            "hides_creator_submissions": _bool(display.get("hiddenCreatorSubmissions")),
            "shows_top_performers": _bool(display.get("topPerformers")),
        },
    })
    if org and isinstance(card.get("organization"), dict):
        card["organization"].setdefault("name", _str(org.get("name")))
        card["organization"].setdefault("handle", _str(org.get("profileHandle")))
        card["organization"].setdefault("is_verified", _bool(org.get("verified")))
        card["organization"].setdefault("logo", _cdn(org.get("logoUrl")))
        if not card["organization"].get("link"):
            card["organization"]["link"] = organization_link(_str(org.get("profileHandle")))
    if card["metrics"].get("pool_split") is None:
        card["metrics"]["pool_split"] = _pool_split(_get(record, "metrics", "poolSplit"))
    return card


def parse_stats(payload):
    payload = payload if isinstance(payload, dict) else {}
    return {
        "active_sellers": _int(payload.get("activeSellersV2")),
        "active_users": _int(payload.get("activeUsersV2")),
        "memberships_sold": _int(payload.get("membershipsSoldV2")),
        "total_companies": _int(payload.get("totalCompaniesV2")),
        "total_products": _int(payload.get("totalProductsV2")),
        "total_processed_usd": _num(payload.get("totalProcessedV2")),
    }
