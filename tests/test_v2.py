from deepalpha.account_pool import AccountPoolManager
from deepalpha.cleaner_v2 import clean_tweets
from deepalpha.intel_router_v2 import decide


def test_fast_router_classifies_oil_query() -> None:
    decision = decide("油价会涨吗？")

    assert decision.asset == "oil"
    assert decision.top_accounts
    assert decision.crawl_tasks


def test_cleaner_keeps_high_quality_market_items() -> None:
    tweets = [
        {
            "username": "@Reuters",
            "content": "BREAKING: OPEC+ agrees to cut production by 2.2 million barrels per day",
            "likes": 5000,
            "is_verified": True,
        },
        {
            "username": "@random",
            "content": "lol oil moon soon!!!",
            "likes": 1,
            "is_verified": False,
        },
    ]

    cleaned = clean_tweets(tweets, verbose=False)

    assert cleaned
    assert cleaned[0].username == "@Reuters"


def test_account_pool_stats_shape() -> None:
    stats = AccountPoolManager().get_pool_stats()

    assert "total" in stats
    assert "by_status" in stats
