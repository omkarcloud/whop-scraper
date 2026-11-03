"""Offline tests for the Whop parsers, reference resolvers and value
helpers.

    python -m pytest whop/test_parsers.py -q

Fixtures are raw data.whop.com/graphql and contentrewards.com responses
captured 2026-11-03 through whop/fetch.py (whop/fixtures/): a rich product
(Elite Options Pro), a sparse one (Forex Signals, no reviews), a legacy
pass_ id, a rich company (eMoney, 2.9K reviews), a sparse company, review /
member / catalog / app / bounty / leaderboard pages, user profiles, the
category tree, two Content Rewards feed pages, filtered / empty feeds, two
campaign records, and the gateway's not-found replies. No network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whop import parsers as P, refs  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


# ---- refs ------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("biz_eYoV4GW80c495B", "biz_eYoV4GW80c495B"),
    ("limitless", "route:limitless"),
    ("LIMITLESS", "route:limitless"),
    ("https://whop.com/limitless/", "route:limitless"),
    ("https://whop.com/winnerscircle-e956/forex-signals-d6/", "route:winnerscircle-e956"),
    ("https://whop.com/robsreview/reviews", "route:robsreview"),
    ("//whop.com/robsreview?x=1", "route:robsreview"),
])
def test_resolve_company(value, expected):
    assert refs.resolve_company(value) == expected


@pytest.mark.parametrize("value", ["", "https://example.com/limitless/", "https://whop.com/@jack/",
                                   "https://whop.com/apps/app_x/", "https://whop.com/", "a b"])
def test_resolve_company_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_company(value)


@pytest.mark.parametrize("value,expected", [
    ("prod_UzIpfrCaGvdqD", "prod_UzIpfrCaGvdqD"),
    ("pass_F8vWKiJ2ZDrSA", "pass_F8vWKiJ2ZDrSA"),
    ("https://whop.com/winnerscircle-e956/forex-signals-d6/", "route:winnerscircle-e956/forex-signals-d6"),
    ("https://whop.com/Robsreview/flips-nation-leads-monthly?ref=1", "route:robsreview/flips-nation-leads-monthly"),
])
def test_resolve_product(value, expected):
    assert refs.resolve_product(value) == expected


@pytest.mark.parametrize("value", ["", "elite-options", "https://whop.com/limitless/",
                                   "https://whop.com/limitless/products", "https://example.com/a/b/"])
def test_resolve_product_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_product(value)


@pytest.mark.parametrize("value,expected", [
    ("user_lNmRfQ3CbAazB", "user_lNmRfQ3CbAazB"),
    ("jack", "name:jack"),
    ("@jack", "name:jack"),
    ("https://whop.com/@jordyplum/", "name:jordyplum"),
])
def test_resolve_user(value, expected):
    assert refs.resolve_user(value) == expected


@pytest.mark.parametrize("value", ["", "@", "https://whop.com/jack/", "has space"])
def test_resolve_user_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_user(value)


def test_resolve_app_and_campaign():
    assert refs.resolve_app("app_fqYWzj3RZXe1O0") == "app_fqYWzj3RZXe1O0"
    assert refs.resolve_app("https://whop.com/apps/app_fqYWzj3RZXe1O0/") == "app_fqYWzj3RZXe1O0"
    with pytest.raises(ValueError):
        refs.resolve_app("https://whop.com/limitless/")
    with pytest.raises(ValueError):
        refs.resolve_app("forums")
    uuid = "4479e5e2-9a00-489e-8b0c-345834f37cc7"
    assert refs.resolve_campaign(uuid.upper()) == uuid
    assert refs.resolve_campaign(f"https://contentrewards.com/c/campaigns/{uuid}") == uuid
    assert refs.resolve_campaign(f"https://contentrewards.com/discover/{uuid}?x=1") == uuid
    with pytest.raises(ValueError):
        refs.resolve_campaign("https://contentrewards.com/c/discover")
    with pytest.raises(ValueError):
        refs.resolve_campaign("not-a-uuid")


def test_links():
    assert refs.product_link("a", "b") == "https://whop.com/a/b/"
    assert refs.product_link("a", None) is None
    assert refs.user_link("jack") == "https://whop.com/@jack/"
    assert refs.campaign_link("x") == "https://contentrewards.com/c/campaigns/x"


# ---- value helpers -------------------------------------------------------------------------------

def test_time_helpers():
    from datetime import datetime, timezone
    assert P.iso_from_unix(1780578347) == datetime.fromtimestamp(1780578347, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert P.iso_from_unix(1780578347).endswith("Z") and P.iso_from_unix("1780578347") == P.iso_from_unix(1780578347)
    assert P.iso_from_unix(None) is None and P.iso_from_unix(0) is None and P.iso_from_unix("x") is None
    assert P.iso_from_text("2026-11-03T09:28:21.000Z") == "2026-11-03T09:28:21Z"
    assert P.iso_from_text("") is None and P.iso_from_text("nope") is None


def test_cents_cdn_histogram():
    assert P._dollars(18900) == 189.0 and P._dollars(None) is None
    assert P._cdn("users/a/avatar/b.webp") == "https://crusercontent.com/users/a/avatar/b.webp"
    assert P._cdn("https://x/y.png") == "https://x/y.png" and P._cdn("") is None
    assert P._histogram([552, 33, 6, 3, 11]) == {"5": 552, "4": 33, "3": 6, "2": 3, "1": 11}
    assert P._histogram([1]) is None and P._histogram(None) is None


# ---- search / catalog ---------------------------------------------------------------------------

def test_parse_search_products():
    found, rows = P.parse_search(fixture("search_trading_products.json"))
    assert found == 247 and len(rows) == 50
    first = rows[0]
    assert first["id"] == "prod_UzIpfrCaGvdqD"
    assert first["link"] == "https://whop.com/elite-options/elite-options/"
    assert first["rating"] == {"average": 4.88, "count": 1453}
    assert first["price"]["text"] == "$189.00 / month" and first["price"]["currency"] == "USD"
    assert first["price"]["renewal_amount"] == 189.0 and first["price"]["billing_period_days"] == 30
    assert first["company"]["link"] == "https://whop.com/elite-options/"
    assert first["created_at"] == "2024-09-17T02:28:42Z"
    assert all(r["images"] is not None for r in rows)


def test_parse_search_companies_and_empty():
    found, rows = P.parse_search(fixture("search_trading_companies.json"), companies=True)
    assert found == 226 and len(rows) == 50
    assert rows[0]["title"] == "Elite Options Trader" and rows[0]["members"] == 25142
    assert rows[0]["rating"]["count"] == 1453 and rows[0]["link"] == "https://whop.com/elite-options/"
    assert P.parse_search(fixture("search_nomatch.json")) == (0, [])
    assert P.parse_search(None) == (None, [])


def test_parse_products_list_page():
    total, has_next, rows = P.parse_connection(fixture("products_list_trading_money_p2.json"),
                                               P.parse_product_card)
    assert total > 20000 and has_next is True and len(rows) == 100
    assert all(r["link"] and r["company"] for r in rows)
    assert P.parse_connection({}, P.parse_product_card) == (None, None, [])


# ---- product details ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def elite():
    return P.parse_product(fixture("product_elite_options.json"))


def test_parse_product_rich(elite):
    assert elite["id"] == "prod_UzIpfrCaGvdqD"
    assert elite["category"] == {"id": "mcat_lkjDDW8wBZzQU", "name": "Trading", "route": "trading"}
    assert elite["rating"]["histogram"]["5"] == 552 and elite["rating"]["average_all_time"] == 4.84
    assert elite["plans_count"] == 2 and len(elite["plans"]) == 2
    plan = elite["plans"][1]
    assert plan["text"] == "$1,999.00 / year" and plan["renewal_amount"] == 1999.0
    assert plan["checkout_link"].startswith("https://whop.com/checkout/plan_")
    assert plan["payment_methods"] == ["multi_psp"] and plan["is_unlimited_stock"] is True
    assert elite["faq"] and elite["faq"][0]["question"] == "Do you offer a trial?"
    assert elite["experiences"][0]["app"]["name"] == "Files"
    assert elite["social_links"][0]["site"] == "instagram"
    assert elite["affiliate"] == {"status": "enabled", "percentage": 10.0,
                                  "member_status": "disabled", "member_percentage": 0.0}
    assert elite["redirect_purchase_link"].startswith("https://calendly.com/")
    assert elite["latest_review"]["stars"] == 5
    assert elite["tax_code"] == {"name": "Non Taxable", "product_type": "digital"}
    assert "affiliate_percentage" not in elite
    assert elite["owner"]["username"]


def test_parse_product_sparse_and_pass():
    sparse = P.parse_product(fixture("product_forex_signals.json"))
    assert sparse["title"] == "Forex Signals" and sparse["rating"]["count"] == 0
    assert sparse["price"]["text"] == "$32.00 / month" and sparse["faq"] == []
    assert sparse["latest_review"] is None and sparse["highlights"] == []
    legacy = P.parse_product(fixture("product_pass_flips_leads.json"))
    assert legacy["id"] == "pass_F8vWKiJ2ZDrSA" and legacy["link"] == \
        "https://whop.com/robsreview/flips-nation-leads-monthly/"
    assert P.parse_product(None) is None and P.parse_product({"title": "x"}) is None


def test_parse_product_reviews():
    node = fixture("product_reviews_elite_options_p1.json")
    total, has_next, rows = P.parse_connection(node["reviews"], P.parse_review)
    assert total == 440 and has_next is True and len(rows) == 50
    review = rows[0]
    assert review["stars"] in (1, 2, 3, 4, 5) and review["reviewer"]["username"]
    assert review["product"]["route"] == "elite-options"
    assert review["created_at"] and review["is_verified_purchase"] in (True, False)
    empty = fixture("product_reviews_forex_signals.json")
    assert P.parse_connection(empty["reviews"], P.parse_review) == (0, False, [])


# ---- companies ---------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def emoney():
    return P.parse_company(fixture("company_emoney.json"))


def test_parse_company_rich(emoney):
    assert emoney["id"] == "biz_1ZH7VJrbsBzY1D" and emoney["link"] == "https://whop.com/emoney/"
    assert emoney["is_verified"] is True and emoney["members"] == 537546
    assert emoney["rating"]["average"] == 4.77 and emoney["rating"]["histogram"]["1"] == 74
    assert emoney["total_views"] == 719761
    assert emoney["owner"]["username"] == "nickresell" and emoney["owner"]["followers"] == 2597
    assert emoney["team_count"] == 40 and emoney["team"][0]["role"] == "owner"
    assert emoney["products_count"] == len(emoney["products"]) >= 1
    assert emoney["products"][0]["price"]["text"]
    assert emoney["experiences"][0]["app"]["name"] == "Forums" and emoney["experiences"][0]["is_public"] is True
    assert emoney["social_links"] == [{"site": "x", "link": "https://x.com/eMoney_HQ", "title": None}]
    assert emoney["public_forum"]["id"].startswith("exp_")
    assert emoney["store_page"] == {"accent_color": "magenta", "layout": "featured"}
    assert "total_earnings_usd" not in emoney and emoney["revenue"]["total_earnings_usd"] is None
    assert emoney["created_at"] == "2022-08-15T20:57:01Z"


def test_parse_company_sparse():
    sparse = P.parse_company(fixture("company_winnerscircle.json"))
    assert sparse["route"] == "winnerscircle-e956" and sparse["rating"] == {
        "average": None, "count": 0, "histogram": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}}
    assert sparse["owner"]["city"] == "Auckland" and sparse["owner"]["country"] == "NZ"
    assert sparse["products"][0]["route"] == "forex-signals-d6"
    assert P.parse_company({}) is None


def test_parse_company_reviews_and_members():
    node = fixture("company_reviews_emoney_p1.json")
    total, has_next, rows = P.parse_connection(node["reviews"], P.parse_review)
    assert total == 2919 and has_next is True and len(rows) == 50
    assert rows[0]["company"]["route"] == "emoney" and rows[0]["product"]["title"] == "VIP Membership"
    past = fixture("company_reviews_emoney_p3_1star.json")
    assert P.parse_connection(past["reviews"], P.parse_review)[2] == []
    members = fixture("company_members_flips_nation_p1.json")
    total, has_next, rows = P.parse_connection(members["members"], P.parse_member)
    assert total == 338 and has_next is True and len(rows) == 100
    assert rows[0]["member_id"].startswith("mber_") and rows[0]["username"] == "evan686"
    assert rows[0]["joined_whop_at"] and rows[0]["link"] == "https://whop.com/@evan686/"
    last = fixture("company_members_flips_nation_p4.json")
    assert P.parse_connection(last["members"], P.parse_member)[1] is False


def test_parse_company_lists():
    total, has_next, rows = P.parse_connection(fixture("companies_popular_p1.json"), P.parse_company_card)
    assert total == 100 and len(rows) == 50 and rows[0]["title"] == "Whop AI"
    assert P.parse_connection(fixture("companies_popular_p3.json"), P.parse_company_card) == (100, False, [])
    total, has_next, rows = P.parse_connection(fixture("companies_affiliate_trading_p1.json"),
                                               P.parse_company_card)
    assert rows[0]["affiliate"]["total_earned_usd"] > 100000 and rows[0]["affiliate"]["is_enabled"] is True
    assert "affiliate" not in P.parse_connection(fixture("companies_verified_p1.json"),
                                                 P.parse_company_card)[2][0]


# ---- categories / users / leaderboards --------------------------------------------------------

def test_parse_categories():
    total, _, rows = P.parse_connection(fixture("categories_level1.json"), P.parse_category)
    assert total == 40 and len(rows) == 40
    trading = next(c for c in rows if c["route"] == "trading")
    assert trading["products_count"] > 10000 and trading["parent"] is None and trading["level"] == 1
    total, _, rows = P.parse_connection(fixture("categories_level2.json"), P.parse_category)
    forex = next(c for c in rows if c["route"] == "forex")
    assert forex["parent"]["route"] == "trading" and forex["level"] == 2


def test_parse_user():
    jack = P.parse_user(fixture("user_jack.json"))
    assert jack["username"] == "jack" and jack["link"] == "https://whop.com/@jack/"
    assert jack["is_verified"] is True and jack["verified_at"] == P.iso_from_unix(1772002193)
    assert jack["country"] == "PE" and jack["country_name"] == "Peru"
    assert jack["lifetime_earnings_usd"] == 30918.83 and jack["roles"] == ["admin", "developer", "global_mode"]
    assert jack["owned_whops_count"] == 162 and jack["owned_whops"][0]["title"] == "Whop"
    assert jack["preferences"]["shows_joined_whops"] is False and jack["joined_whops"] == []
    assert jack["reviews_written"] == 4
    flips = P.parse_user(fixture("user_flipsnation.json"))
    assert flips["id"] == "user_lNmRfQ3CbAazB" and flips["owned_whops"][0]["route"] == "robsreview"
    assert flips["joined_whops"][0]["members"] is not None
    assert P.parse_user({}) is None


def test_parse_leaderboard():
    kind, total, rows = P.parse_leaderboard(fixture("leaderboard_top_rated.json"))
    assert kind == "top_rated" and total == 23 and rows[0]["rank"] == 1
    assert rows[0]["score"] == 11.0 and rows[0]["product"]["route"] == "quantby-membership"
    assert rows[0]["user"] is None
    kind, total, rows = P.parse_leaderboard(fixture("leaderboard_affiliate_earnings.json"))
    assert kind == "affiliate_earnings" and rows
    assert P.parse_leaderboard(None) == (None, None, [])


# ---- apps / bounties -----------------------------------------------------------------------------

def test_parse_apps():
    total, has_next, rows = P.parse_connection(fixture("apps_hub_installs7d_p1.json"), P.parse_app_card)
    assert total == 179 and has_next is True and len(rows) == 50
    forums = rows[0]
    assert forums["name"] == "Forums" and forums["installs"]["last_7_days"] > 1000
    assert forums["creator"]["username"] == "jack" and forums["category"]["route"] == "community"
    assert forums["link"] == "https://whop.com/apps/app_dYfm2IdXhDMquv/"
    app = P.parse_app(fixture("app_community_onboarding.json"))
    assert app["id"] == "app_fqYWzj3RZXe1O0" and app["store_description"].startswith("Most communities")
    assert app["rating"]["histogram"]["5"] == 3 and app["store_product"]["price"]["is_free"] is True
    assert app["store_product"]["company"]["route"] and app["usage"]["time_spent_last_24_hours_seconds"] == 4210
    assert P.parse_app(None) is None


def test_parse_bounties():
    total, has_next, rows = P.parse_connection(fixture("bounties_total_paid_p1.json"), P.parse_bounty)
    assert total == 1864 and has_next is True and len(rows) == 50
    top = rows[0]
    assert top["reward"] == {"amount": 1.0, "unit": "per_submission", "currency": "EUR",
                             "budget": None, "total_paid": 186913.14}
    assert top["submissions"]["accepted"] == 553 and top["platforms"] == []
    assert top["company"]["route"] == "keo-affiliates-clipping" and top["created_at"]
    total, _, rows = P.parse_connection(fixture("bounties_created_at_p2.json"), P.parse_bounty)
    assert len(rows) == 50


# ---- Content Rewards -----------------------------------------------------------------------------

def test_parse_campaigns_page():
    rows, nxt = P.parse_campaigns_page(fixture("campaigns_trending_p1.json"))
    # the feed's `count` says 100 but a grouped campaign expands to its
    # siblings, so a page may carry a few more rows than its limit
    assert 100 <= len(rows) <= 110 and nxt and len(nxt) > 40
    assert len({r["id"] for r in rows}) == len(rows)
    row = rows[0]
    assert row["link"] == f"https://contentrewards.com/c/campaigns/{row['id']}"
    assert row["budget"]["total_usd"] is not None and row["budget"]["remaining_usd"] is not None
    assert row["organization"]["link"].startswith("https://contentrewards.com/c/")
    assert row["banner"].startswith("https://crusercontent.com/")
    assert "daily" not in row["metrics"] and "top_clips" not in row["metrics"]
    cpm = next(r for r in rows if r["payout_type"] == "cpm")
    assert cpm["reward"]["primary_rate_per_1k_views_usd"] > 0
    assert cpm["reward"]["payouts"][0]["rate_per_1k_views_usd"] is not None
    pool = next((r for r in rows if r["payout_type"] == "pool"), None)
    if pool:
        assert pool["reward"]["primary_rate_per_1k_views_usd"] is None
    assert P.parse_campaigns_page(fixture("campaigns_empty_category.json")) == ([], None)
    page2, _ = P.parse_campaigns_page(fixture("campaigns_trending_p2.json"))
    # the trending feed re-ranks between two cursor hops, so a handful of
    # rows may straddle the page boundary; a wholesale repeat would mean
    # the cursor was ignored
    assert len({r["id"] for r in page2} & {r["id"] for r in rows}) < 10
    gaming, _ = P.parse_campaigns_page(fixture("campaigns_search_gaming_tiktok.json"))
    assert gaming and all("tiktok" in r["platforms"] for r in gaming)


def test_parse_campaign_details():
    lacy = P.parse_campaign(fixture("campaign_lacy.json"))
    assert lacy["id"] == "4479e5e2-9a00-489e-8b0c-345834f37cc7" and lacy["type"] == "pool"
    assert lacy["budget"]["total_usd"] == 25000.0 and lacy["platform_fee_percent"] == 8.0
    assert lacy["requirements"]["min_creator_views"] == 1000000
    assert lacy["requirements"]["payout_platforms"] == ["tiktok", "instagram", "youtube"]
    assert lacy["content_types"] == ["Clipping"] and lacy["creator_types"] == ["Clipper"]
    assert lacy["metrics"]["pool_split"]["top_shares_percent"][0] > 10
    assert len(lacy["metrics"]["daily"]) > 20 and lacy["metrics"]["top_clips"][0]["rank"] == 1
    assert lacy["metrics"]["top_clips"][0]["link"].startswith("https://www.youtube.com/")
    assert lacy["organization"]["handle"] == "reach" and lacy["organization"]["is_verified"] is True
    assert lacy["group"]["campaign_ids"] and lacy["status_reason"] == "funded"
    assert lacy["reward"]["primary_rate_per_1k_views_usd"] is None
    weeknd = P.parse_campaign(fixture("campaign_weeknd.json"))
    assert weeknd["payout_type"] == "cpm" and weeknd["reward"]["primary_rate_per_1k_views_usd"] == 1.5
    assert weeknd["reward"]["payouts"][0]["max_payout_usd"] == 150.0
    assert weeknd["metrics"]["top_earners"] == [] or weeknd["metrics"]["top_earners"][0]["earned_usd"] is not None
    assert P.parse_campaign({}) is None
    assert P.parse_campaign({"card": None, "record": {"id": "x", "name": "n"}})["title"] == "n"


def test_parse_stats():
    stats = P.parse_stats(fixture("stats.json"))
    assert stats["total_products"] > 400000 and stats["total_processed_usd"] > 1e9


def test_not_found_fixtures_are_errors():
    for name in ("product_not_found.json", "company_not_found.json", "user_not_found.json",
                 "app_not_found.json", "campaign_not_found.json", "resolve_route_unknown.json"):
        assert fixture(name)["__error__"] == "WhopNotFound"
    assert fixture("products_list_bad_category.json")["__error__"] == "WhopBadRequest"


def test_campaign_cursor_exact_exhausted_page_is_empty(monkeypatch):
    """A page the chain already knows does not exist (its marker is False)
    must report exhausted, not fall back to cursor=None (= page 1 again)."""
    from whop import api
    monkeypatch.setattr(api, "_cursor_chains", {})
    calls = []

    def fake_feed(cursor=None, view="summary", **filters):
        calls.append(cursor)
        return {"data": [{"id": "x"}], "pagination": {"nextCursor": None}}   # one page only
    monkeypatch.setattr(api.fetch, "fetch_campaigns_page", fake_feed)
    assert api._campaign_cursor(2, sort="trending") == (None, True)        # walks page 1, learns 2 is past the end
    assert calls == [None]
    assert api._campaign_cursor(2, sort="trending") == (None, True)        # the exact marker page: still exhausted
    assert api._campaign_cursor(3, sort="trending") == (None, True)
    assert calls == [None]                                                 # and no refetch of page 1
