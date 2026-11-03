"""Cache TTL per /whop/* endpoint (cache.py, keyed on the validated params)."""
from datetime import timedelta

# Search ranking and the catalog orders reshuffle with sales and reviews
# through the day; an hour keeps a browsing client from re-querying.
SEARCH_CACHE = timedelta(hours=1)
LIST_CACHE = timedelta(hours=1)
# Product / company / app records move with new reviews and member counts;
# six hours keeps the page-set (details + reviews) consistent per client.
DETAILS_CACHE = timedelta(hours=6)
REVIEWS_CACHE = timedelta(hours=6)
MEMBERS_CACHE = timedelta(hours=6)
# Profiles change rarely (bio, owned whops).
USER_CACHE = timedelta(hours=12)
# The category tree is editorial; counts drift slowly.
CATEGORIES_CACHE = timedelta(hours=24)
# Leaderboards are recomputed hourly upstream (targetPrefix carries the hour).
LEADERBOARD_CACHE = timedelta(minutes=30)
# Bounty totals and spots move with submissions.
BOUNTIES_CACHE = timedelta(hours=1)
# Content Rewards: budget left and burn move within minutes — the value of
# the feed is its freshness, so only a short cache against bursts.
CAMPAIGNS_CACHE = timedelta(minutes=10)
CAMPAIGN_CACHE = timedelta(minutes=10)
# Route -> id resolutions never change for a live route.
RESOLVE_CACHE = timedelta(days=7)
