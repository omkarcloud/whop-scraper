"""Marshmallow request schemas for every /whop/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair):

    product    prod_… / pass_… id OR a whop.com product link
               (https://whop.com/<company-route>/<product-route>/)
    company    biz_… id, a store route ("limitless") OR a whop.com store link
    user       user_… id, a username (@jack) OR a whop.com profile link
    app        app_… id OR a whop.com/apps/app_xxx/ link
    campaign   a Content Rewards campaign UUID OR a contentrewards.com link

Choice values are the gateway's own enums (whop/refs.py, introspected
2026-11-03) so the public docs name what the site names.
"""
from marshmallow import validate

from schema_fields import (BaseSchema, ChoiceField, Flag, LimitField, PageField, Price,
                           PositiveInt, QueryField, RefField, StrippedString)
from whop import refs
from whop.api import SEARCH_MAX_PAGE


class ProductRefField(RefField):
    resolver = staticmethod(refs.resolve_product)


class CompanyRefField(RefField):
    resolver = staticmethod(refs.resolve_company)


class UserRefField(RefField):
    resolver = staticmethod(refs.resolve_user)


class AppRefField(RefField):
    resolver = staticmethod(refs.resolve_app)


class CampaignRefField(RefField):
    resolver = staticmethod(refs.resolve_campaign)


def _slug(description, max_length=60):
    return StrippedString(required=False, load_default=None, metadata={"description": description},
                          validate=validate.Length(max=max_length))


# ---- products -----------------------------------------------------------------------------

class ProductsSearchSchema(BaseSchema):
    query = QueryField(metadata={"description": "keyword to search products and communities for (trading, fitness, discord…)"})
    page = PageField(max_page=SEARCH_MAX_PAGE, metadata={"description": "1-based page of 50 results; the site serves at most 150 per keyword"})
    business_type = _slug("business type to keep (education, software, services, community, other…), as the site labels it")
    industry_type = _slug("industry type to keep (forex_trading, amazon_fba, ai_agents…), as the site labels it")


class ProductsListSchema(BaseSchema):
    sort = ChoiceField(list(refs.PRODUCT_SORTS), load_default="trending", metadata={
        "description": "catalog order: " + ", ".join(refs.PRODUCT_SORTS) + " (the old Discover leaderboards)"})
    category = _slug("category route from /whop/categories/list to browse (trading, ai, ecommerce…); all categories when empty")
    page = PageField(max_page=1000, metadata={"description": "1-based page of 100 products"})
    min_price = Price(metadata={"description": "only products whose price is at least this amount (USD)"})
    affiliate_only = Flag(metadata={"description": "true keeps only products with an affiliate program"})


class ProductSchema(BaseSchema):
    product = ProductRefField(metadata={
        "description": "product id (prod_… / pass_…) or a whop.com product link (https://whop.com/<company>/<product>/)"})


class ProductReviewsSchema(BaseSchema):
    product = ProductRefField(metadata={
        "description": "product id (prod_… / pass_…) or a whop.com product link"})
    stars = PositiveInt(max_value=5, metadata={"description": "only reviews with this star rating (1-5)"})
    page = PageField(max_page=1000, metadata={"description": "1-based page of 50 reviews"})


# ---- companies -------------------------------------------------------------------------------

class CompaniesSearchSchema(BaseSchema):
    query = QueryField(metadata={"description": "keyword to search companies / communities for"})
    page = PageField(max_page=SEARCH_MAX_PAGE, metadata={"description": "1-based page of 50 results; the site serves at most 150 per keyword"})


class CompanySchema(BaseSchema):
    company = CompanyRefField(metadata={
        "description": "company id (biz_…), store route (limitless) or a whop.com store link (https://whop.com/limitless/)"})


class CompanyReviewsSchema(BaseSchema):
    company = CompanyRefField(metadata={
        "description": "company id (biz_…), store route or a whop.com store link"})
    stars = PositiveInt(max_value=5, metadata={"description": "only reviews with this star rating (1-5)"})
    page = PageField(max_page=1000, metadata={"description": "1-based page of 50 reviews"})


class CompanyMembersSchema(BaseSchema):
    company = CompanyRefField(metadata={
        "description": "company id (biz_…), store route or a whop.com store link"})
    page = PageField(max_page=1000, metadata={"description": "1-based page of 100 members"})


class CompaniesListSchema(BaseSchema):
    sort = ChoiceField(list(refs.COMPANY_LISTS), load_default="popular", metadata={
        "description": "popular (the site's most-joined communities), verified (verified badge) or top_affiliate (highest affiliate payouts)"})
    query = StrippedString(required=False, load_default=None, metadata={
        "description": "keyword filter; only the top_affiliate list supports it"}, validate=validate.Length(max=100))
    page = PageField(max_page=1000, metadata={"description": "1-based page of 50 companies"})


# ---- categories / users / leaderboards -------------------------------------------------------

class CategoriesListSchema(BaseSchema):
    level = ChoiceField({"1": 1, "2": 2}, load_default=1, metadata={
        "description": "1 = top-level categories (default), 2 = subcategories with their parent"})


class UserSchema(BaseSchema):
    user = UserRefField(metadata={
        "description": "user id (user_…), username (@jack) or a whop.com profile link (https://whop.com/@jack/)"})


class LeaderboardsListSchema(BaseSchema):
    type = ChoiceField(list(refs.LEADERBOARD_TYPES), load_default="usd_gmv", metadata={
        "description": "leaderboard: " + ", ".join(refs.LEADERBOARD_TYPES)})
    limit = LimitField(default=50, max_size=100, metadata={"description": "number of ranked entries (max 100)"})


# ---- apps ---------------------------------------------------------------------------------------

class AppsListSchema(BaseSchema):
    sort = ChoiceField(list(refs.APP_SORTS), load_default="total_installs_last_7_days", metadata={
        "description": "App Store order: " + ", ".join(refs.APP_SORTS)})
    view = ChoiceField(list(refs.APP_VIEWS), load_default="hub", metadata={
        "description": "store section: hub (every app, default), discover (featured), dash, dashboard, analytics, skills, openapi"})
    type = ChoiceField(list(refs.APP_TYPES), load_default="b2c_app", metadata={
        "description": "app type: b2c_app (consumer apps, default), b2b_app, company_app, component, website"})
    category = _slug("App Store category route (ai, trading, community, education…)")
    query = StrippedString(required=False, load_default=None, metadata={
        "description": "keyword filter on app names"}, validate=validate.Length(max=100))
    page = PageField(max_page=100, metadata={"description": "1-based page of 50 apps"})


class AppSchema(BaseSchema):
    app = AppRefField(metadata={
        "description": "app id (app_…) or a whop.com app link (https://whop.com/apps/app_xxx/)"})


# ---- bounties / campaigns ---------------------------------------------------------------------

class BountiesListSchema(BaseSchema):
    sort = ChoiceField(list(refs.BOUNTY_SORTS), load_default="total_paid", metadata={
        "description": "total_paid (most paid out first, default) or created_at (newest first)"})
    page = PageField(max_page=1000, metadata={"description": "1-based page of 50 bounties"})


class CampaignsListSchema(BaseSchema):
    sort = ChoiceField(list(refs.CAMPAIGN_SORTS), load_default="trending", metadata={
        "description": "feed order: " + ", ".join(refs.CAMPAIGN_SORTS) + " (relevance needs `search`)"})
    search = StrippedString(required=False, load_default=None, metadata={
        "description": "keyword to search campaign titles, brands and briefs for"}, validate=validate.Length(max=100))
    platform = ChoiceField(list(refs.CAMPAIGN_PLATFORMS), metadata={
        "description": "only campaigns paying on this platform: " + ", ".join(refs.CAMPAIGN_PLATFORMS)})
    payout_type = ChoiceField(list(refs.CAMPAIGN_PAYOUT_TYPES), metadata={
        "description": "cpm (paid per 1K views), pool (budget split by share of views) or retainer"})
    category = _slug("campaign category slug as shown on the site (gaming, music, entertainment, personal-brand, podcast, streamer…)")
    organization_id = StrippedString(required=False, load_default=None, metadata={
        "description": "only campaigns of this Content Rewards organization (the `organization.id` UUID of a campaign)"},
        validate=validate.Length(max=64))
    page = PageField(max_page=50, metadata={
        "description": "1-based page of 100 campaigns (the feed is cursor-paged upstream: a cold page walks the pages before it)"})


class CampaignSchema(BaseSchema):
    campaign = CampaignRefField(metadata={
        "description": "campaign UUID or a contentrewards.com campaign link (https://contentrewards.com/c/campaigns/<uuid>)"})
