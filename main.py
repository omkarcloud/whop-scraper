"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. Params go through the same schemas the API uses, so defaults
are filled in and an id or a whop.com link both work.
"""
import json
import os

from whop import api, schemas

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


def run(schema_cls, fn, **params):
    return fn(**schema_cls().load(params))


if __name__ == "__main__":
    # a product id or any whop.com product link — every plan and price, reviews, members, FAQ
    save("product_druski.json",
         run(schemas.ProductSchema, api.product_details, product="https://whop.com/druski/druski/"))

    # 50 products per page, searched by keyword
    save("search_ai_automation.json",
         run(schemas.ProductsSearchSchema, api.products_search, query="ai automation"))

    # Content Rewards clipping campaigns — pay per 1K views, budget left, platforms
    save("campaigns_trending.json",
         run(schemas.CampaignsListSchema, api.campaigns_list, sort="trending"))
