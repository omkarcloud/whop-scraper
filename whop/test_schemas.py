"""Offline tests for the /whop/* request schemas.

    python -m pytest whop/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whop import schemas  # noqa: E402


def _error(schema, data):
    with pytest.raises(ValidationError) as exc:
        schema().load(data)
    return exc.value.normalized_messages()


def test_products_search():
    assert schemas.ProductsSearchSchema().load({"query": " trading "}) == {
        "query": "trading", "page": 1, "business_type": None, "industry_type": None}
    loaded = schemas.ProductsSearchSchema().load({"query": "x", "page": "3", "business_type": "education"})
    assert loaded["page"] == 3 and loaded["business_type"] == "education"
    assert "query" in _error(schemas.ProductsSearchSchema, {})
    assert "page" in _error(schemas.ProductsSearchSchema, {"query": "x", "page": "4"})
    assert "nope" in _error(schemas.ProductsSearchSchema, {"query": "x", "nope": "1"})


def test_products_list():
    assert schemas.ProductsListSchema().load({}) == {
        "sort": "trending", "category": None, "page": 1, "min_price": None, "affiliate_only": None}
    loaded = schemas.ProductsListSchema().load({"sort": "Most_Reviews_7_Days", "category": "trading",
                                                "page": "2", "min_price": "10", "affiliate_only": "yes"})
    assert loaded == {"sort": "most_reviews_7_days", "category": "trading", "page": 2,
                      "min_price": 10.0, "affiliate_only": True}
    msgs = _error(schemas.ProductsListSchema, {"sort": "popular"})
    assert "sort" in msgs and "trending" in msgs["sort"][0]
    assert "min_price" in _error(schemas.ProductsListSchema, {"min_price": "-1"})
    assert "affiliate_only" in _error(schemas.ProductsListSchema, {"affiliate_only": "maybe"})


def test_product_ref():
    assert schemas.ProductSchema().load({"product": "prod_UzIpfrCaGvdqD"}) == {"product": "prod_UzIpfrCaGvdqD"}
    assert schemas.ProductSchema().load({"product": "https://whop.com/winnerscircle-e956/forex-signals-d6/"}) == {
        "product": "route:winnerscircle-e956/forex-signals-d6"}
    msgs = _error(schemas.ProductSchema, {"product": "elite-options"})
    assert "product link" in msgs["product"][0]
    assert "product" in _error(schemas.ProductSchema, {})
    assert "url" in _error(schemas.ProductSchema, {"product": "prod_x1234567890", "url": "x"})


def test_product_reviews():
    loaded = schemas.ProductReviewsSchema().load({"product": "pass_F8vWKiJ2ZDrSA", "stars": "5", "page": "2"})
    assert loaded == {"product": "pass_F8vWKiJ2ZDrSA", "stars": 5, "page": 2}
    assert "stars" in _error(schemas.ProductReviewsSchema, {"product": "pass_F8vWKiJ2ZDrSA", "stars": "6"})
    assert "stars" in _error(schemas.ProductReviewsSchema, {"product": "pass_F8vWKiJ2ZDrSA", "stars": "0"})


def test_company_refs():
    assert schemas.CompanySchema().load({"company": "biz_eYoV4GW80c495B"}) == {"company": "biz_eYoV4GW80c495B"}
    assert schemas.CompanySchema().load({"company": "Limitless"}) == {"company": "route:limitless"}
    assert schemas.CompanySchema().load({"company": "https://whop.com/robsreview/products"}) == {
        "company": "route:robsreview"}
    assert "store link" in _error(schemas.CompanySchema, {"company": "https://whop.com/@jack/"})["company"][0]
    loaded = schemas.CompanyReviewsSchema().load({"company": "emoney", "stars": "1"})
    assert loaded == {"company": "route:emoney", "stars": 1, "page": 1}
    assert schemas.CompanyMembersSchema().load({"company": "emoney", "page": "4"}) == {
        "company": "route:emoney", "page": 4}


def test_companies_search_and_list():
    assert schemas.CompaniesSearchSchema().load({"query": "fba"}) == {"query": "fba", "page": 1}
    assert schemas.CompaniesListSchema().load({}) == {"sort": "popular", "query": None, "page": 1}
    loaded = schemas.CompaniesListSchema().load({"sort": "TOP_AFFILIATE", "query": "trading"})
    assert loaded["sort"] == "top_affiliate" and loaded["query"] == "trading"
    assert "sort" in _error(schemas.CompaniesListSchema, {"sort": "newest"})


def test_categories_users_leaderboards():
    assert schemas.CategoriesListSchema().load({}) == {"level": 1}
    assert schemas.CategoriesListSchema().load({"level": "2"}) == {"level": 2}
    assert "level" in _error(schemas.CategoriesListSchema, {"level": "3"})
    assert schemas.UserSchema().load({"user": "@jack"}) == {"user": "name:jack"}
    assert schemas.UserSchema().load({"user": "https://whop.com/@jack/"}) == {"user": "name:jack"}
    assert schemas.UserSchema().load({"user": "user_lNmRfQ3CbAazB"}) == {"user": "user_lNmRfQ3CbAazB"}
    assert "profile link" in _error(schemas.UserSchema, {"user": "https://whop.com/jack/"})["user"][0]
    assert schemas.LeaderboardsListSchema().load({}) == {"type": "usd_gmv", "limit": 50}
    assert schemas.LeaderboardsListSchema().load({"type": "Top_Rated", "limit": "100"}) == {
        "type": "top_rated", "limit": 100}
    assert "limit" in _error(schemas.LeaderboardsListSchema, {"limit": "101"})
    assert "type" in _error(schemas.LeaderboardsListSchema, {"type": "richest"})


def test_apps():
    assert schemas.AppsListSchema().load({}) == {
        "sort": "total_installs_last_7_days", "view": "hub", "type": "b2c_app",
        "category": None, "query": None, "page": 1}
    loaded = schemas.AppsListSchema().load({"sort": "daily_active_users", "type": "b2b_app", "category": "ai"})
    assert loaded["sort"] == "daily_active_users" and loaded["type"] == "b2b_app" and loaded["category"] == "ai"
    assert "view" in _error(schemas.AppsListSchema, {"view": "store"})
    assert schemas.AppSchema().load({"app": "https://whop.com/apps/app_fqYWzj3RZXe1O0/"}) == {
        "app": "app_fqYWzj3RZXe1O0"}
    assert "app" in _error(schemas.AppSchema, {"app": "forums"})


def test_bounties_and_campaigns():
    assert schemas.BountiesListSchema().load({}) == {"sort": "total_paid", "page": 1}
    assert "sort" in _error(schemas.BountiesListSchema, {"sort": "cpm"})
    assert schemas.CampaignsListSchema().load({}) == {
        "sort": "trending", "search": None, "platform": None, "payout_type": None,
        "category": None, "organization_id": None, "page": 1}
    loaded = schemas.CampaignsListSchema().load({"sort": "CPM", "platform": "TikTok", "payout_type": "pool",
                                                 "category": "gaming", "search": "fortnite", "page": "2"})
    assert loaded == {"sort": "cpm", "search": "fortnite", "platform": "tiktok", "payout_type": "pool",
                      "category": "gaming", "organization_id": None, "page": 2}
    assert "platform" in _error(schemas.CampaignsListSchema, {"platform": "twitch"})
    assert "payout_type" in _error(schemas.CampaignsListSchema, {"payout_type": "fixed"})
    assert "page" in _error(schemas.CampaignsListSchema, {"page": "51"})
    uuid = "4479e5e2-9a00-489e-8b0c-345834f37cc7"
    assert schemas.CampaignSchema().load({"campaign": f"https://contentrewards.com/c/campaigns/{uuid}"}) == {
        "campaign": uuid}
    assert "campaign" in _error(schemas.CampaignSchema, {"campaign": "lacy"})
