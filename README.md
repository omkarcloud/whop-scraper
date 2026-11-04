# 🛍️ Whop Scraper

Whop Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Whop data for free.

## ✨ What Can I Get?

- 🛍️ **Full details on 450K+ Whop products** — every plan & price, reviews, members, FAQ & seller
- 🏢 **5.6M+ companies & 42M+ user profiles** — members, rating histograms, teams, socials & lifetime earnings
- 🏆 **Leaderboards, 40 categories & 178 apps** — top earners, trending, most reviewed & App Store installs
- 🎬 **650+ live clipping campaigns & 1,800+ bounties** — pay per 1K views, budget left, top clips & top earners

## 🎥 Example: A Full Whop Product

```json
{
  "id": "prod_BIibz1GGzJXKH",
  "title": "Druski",
  "link": "https://whop.com/druski/druski/",
  "headline": "The Official Druski Clipping Community",
  "description": "Join our exclusive community to clip Druski's funniest moments, earn money per view, and build your social media presence while amplifying Druski's best content",
  "is_verified": true,
  "members": 65226,
  "rating": {
    "average": 4.79,
    "count": 115,
    "histogram": { "5": 91, "4": 24, "3": 0, "2": 0, "1": 0 }
  },
  "price": { "text": "Free", "currency": "USD", "type": "one_time", "is_free": true },
  "category": { "id": "mcat_H8cjiLMEl1Rtr", "name": "Social Media", "route": "social-media" },
  "company": { "id": "biz_pPkKqAxz3iQeOr", "title": "Druski", "link": "https://whop.com/druski/", "is_verified": true, "members": 66758 },
  "plans": [
    { "id": "plan_aDxhjd7snZPT3", "text": "Free", "checkout_link": "https://whop.com/checkout/plan_aDxhjd7snZPT3" }
  ],
  "faq": [
    { "question": "Can I make money if I join?", "answer": "Yes, make clips from Coulda Been Love, post them, submit them back in the clipping community and get paid per 1,000 views" }
  ],
  "experiences": [
    { "id": "exp_4Z8JSnr7b4CcsO", "name": "Content Rewards", "app": { "id": "app_JsryI0fVLVpeYi", "name": "Content Rewards" } },
    { "id": "exp_zhSm3WpdeEpoG1", "name": "Druski Chat", "app": { "id": "app_xml5hbizmZPgUT", "name": "Chat" } }
  ],
  "social_links": [
    { "site": "instagram", "link": "https://www.instagram.com/druski/" },
    { "site": "youtube", "link": "https://www.youtube.com/@druski" }
  ],
  "latest_review": { "stars": 5, "text": "Love it and druski", "published_at": "2026-04-07T17:32:31Z" },
  "created_at": "2025-03-22T17:29:00Z"
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Whop Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/whop-scraper
cd whop-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/products/details?product=https://whop.com/druski/druski/"
```

```json
{
  "id": "prod_BIibz1GGzJXKH",
  "title": "Druski",
  "link": "https://whop.com/druski/druski/",
  "headline": "The Official Druski Clipping Community",
  "is_verified": true,
  "members": 65226,
  "rating": {
    "average": 4.79,
    "count": 115,
    "histogram": { "5": 91, "4": 24, "3": 0, "2": 0, "1": 0 }
  },
  "price": { "text": "Free", "currency": "USD", "is_free": true },
  "category": { "name": "Social Media", "route": "social-media" },
  "company": { "id": "biz_pPkKqAxz3iQeOr", "title": "Druski", "link": "https://whop.com/druski/", "members": 66758 },
  "faq": [
    { "question": "Is this group free?", "answer": "Yes, Druski's community is 100% free!" }
  ],
  "owner": { "username": "druski", "link": "https://whop.com/@druski/" }
}
```

All 17 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

17 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Product Details | `/products/details` | Every plan and price, reviews, members, FAQ, apps and seller |
| Search Products | `/products/search` | 50 products per page with price, rating, members and seller |
| List Top Products | `/products/list` | Ranked catalog: trending, top earners, most reviewed or newest |
| Product Reviews | `/products/reviews` | 50 reviews per page with stars, text and verified purchase |
| Company Details | `/companies/details` | Members, rating histogram, team, socials, every product and app |
| Search Companies | `/companies/search` | 50 companies per page with members, rating and owner |
| Company Reviews | `/companies/reviews` | Every review across a company's products, 50 per page |
| Company Members | `/companies/members` | Public member list with usernames and locations, 100 per page |
| List Top Companies | `/companies/list` | Most popular, verified or top-affiliate companies |
| User Details | `/users/details` | Bio, followers, lifetime earnings, owned and joined whops |
| List Categories | `/categories/list` | Full category tree with live product counts |
| Leaderboards | `/leaderboards/list` | Top products by revenue, rating, new users or earnings |
| List Apps | `/apps/list` | App Store apps ranked by installs, daily users or time spent |
| App Details | `/apps/details` | Installs, active users, time spent, reviews and creator |
| List Bounties | `/bounties/list` | Bounties with reward, budget, total paid and open spots |
| List Campaigns | `/campaigns/list` | Clipping campaigns with pay per 1K views and budget left |
| Campaign Details | `/campaigns/details` | Per-platform pay, daily views, top clips and top earners |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-whop-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-whop-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-whop-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/products/list",
    params={"sort": "most_money_made_24_hours", "category": "trading"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Whop Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://www.omkar.cloud/l/whop-scraper-github-whatsapp)

[![Ask Us by Email about Whop Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](https://www.omkar.cloud/l/whop-scraper-github-email)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/whop-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/whop-scraper)
