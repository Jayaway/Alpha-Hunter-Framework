# -*- coding: utf-8 -*-
"""
Event clustering for cleaned DeepAlpha tweets.

This module does not replace x_intel_rules.py, cleaner_v2.py, or
signal_judge.py. It only groups already-cleaned tweets into event clusters.

Example:
  python3 event_cluster.py
  python3 event_cluster.py --input data/intel/sample.jsonl --window-hours 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


DEFAULT_WINDOW_HOURS = 3
DEFAULT_SIMILARITY_THRESHOLD = 0.46
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+.-]{1,}|[\u4e00-\u9fff]{2,}")


@dataclass
class ClusterTweet:
    tweet_id: str | None
    timestamp: datetime | None
    source: str | None
    content: str
    entities: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventCluster:
    tweets: list[ClusterTweet] = field(default_factory=list)
    entities: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    first_seen_time: datetime | None = None
    last_seen_time: datetime | None = None

    def add(self, tweet: ClusterTweet) -> None:
        self.tweets.append(tweet)
        self.entities.update(tweet.entities)
        self.keywords.update(tweet.keywords)
        if tweet.source:
            self.sources.add(tweet.source)
        if tweet.timestamp:
            if self.first_seen_time is None or tweet.timestamp < self.first_seen_time:
                self.first_seen_time = tweet.timestamp
            if self.last_seen_time is None or tweet.timestamp > self.last_seen_time:
                self.last_seen_time = tweet.timestamp


def cluster_events(
    tweets: list[dict[str, Any]],
    window_hours: int | float = DEFAULT_WINDOW_HOURS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Group cleaned tweets into event clusters.

    Input should be a list of already-cleaned tweet dictionaries. This function
    does not judge market direction and does not maintain separate oil rules.
    """
    normalized = [tweet for tweet in (normalize_tweet(raw) for raw in tweets) if tweet]
    normalized.sort(key=lambda item: item.timestamp or datetime.min.replace(tzinfo=timezone.utc))

    clusters: list[EventCluster] = []
    for tweet in normalized:
        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            score = event_similarity(tweet, cluster, window_hours=window_hours)
            if score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster is not None and best_score >= similarity_threshold:
            best_cluster.add(tweet)
        else:
            cluster = EventCluster()
            cluster.add(tweet)
            clusters.append(cluster)

    clusters.sort(
        key=lambda cluster: (
            cluster.last_seen_time or datetime.min.replace(tzinfo=timezone.utc),
            len(cluster.tweets),
        ),
        reverse=True,
    )
    return [cluster_to_event(cluster) for cluster in clusters]


def normalize_tweet(raw: dict[str, Any]) -> ClusterTweet | None:
    content = first_value(raw, ("content", "text", "full_text", "body"))
    if not content:
        return None

    timestamp = parse_datetime(first_value(raw, ("timestamp", "created_at", "collected_at", "saved_at", "time")))
    source = normalize_source(first_value(raw, ("handle", "account", "username", "user", "source")))
    tweet_id = to_str(first_value(raw, ("tweet_id", "id", "rest_id")))
    content_text = str(content)

    entities, keywords = extract_oil_terms(content_text)
    if source:
        source_key = source.lower()
        source_info = oil_source_index()
        if source_key in source_info:
            entities.add(source)

    return ClusterTweet(
        tweet_id=tweet_id,
        timestamp=timestamp,
        source=source,
        content=content_text,
        entities=entities,
        keywords=keywords,
        raw=raw,
    )


def event_similarity(tweet: ClusterTweet, cluster: EventCluster, window_hours: int | float) -> float:
    if not within_time_window(tweet, cluster, window_hours):
        return 0.0

    entity_score = jaccard(tweet.entities, cluster.entities)
    keyword_score = jaccard(tweet.keywords, cluster.keywords)
    text_score = max_text_similarity(tweet.content, [item.content for item in cluster.tweets[-5:]])
    different_source_bonus = 0.08 if tweet.source and tweet.source not in cluster.sources else 0.0

    score = (
        entity_score * 0.34
        + keyword_score * 0.30
        + text_score * 0.28
        + different_source_bonus
    )

    if tweet.entities and cluster.entities and tweet.entities & cluster.entities:
        score += 0.08
    if tweet.keywords and cluster.keywords and tweet.keywords & cluster.keywords:
        score += 0.08

    return min(score, 1.0)


def within_time_window(tweet: ClusterTweet, cluster: EventCluster, window_hours: int | float) -> bool:
    if tweet.timestamp is None:
        return True
    if cluster.first_seen_time is None and cluster.last_seen_time is None:
        return True

    window = timedelta(hours=float(window_hours))
    if cluster.first_seen_time and abs(tweet.timestamp - cluster.first_seen_time) <= window:
        return True
    if cluster.last_seen_time and abs(tweet.timestamp - cluster.last_seen_time) <= window:
        return True
    return False


def cluster_to_event(cluster: EventCluster) -> dict[str, Any]:
    main_keywords = rank_terms(cluster.keywords, [tweet.content for tweet in cluster.tweets])[:8]
    event_title = build_event_title(cluster, main_keywords)
    first_seen = cluster.first_seen_time.isoformat() if cluster.first_seen_time else None
    last_seen = cluster.last_seen_time.isoformat() if cluster.last_seen_time else None
    event_id = build_event_id(event_title, first_seen, sorted(cluster.sources))

    return {
        "event_id": event_id,
        "event_title": event_title,
        "related_tweets": [tweet.raw for tweet in cluster.tweets],
        "first_seen_time": first_seen,
        "last_seen_time": last_seen,
        "sources": sorted(cluster.sources),
        "source_count": len(cluster.sources),
        "main_keywords": main_keywords,
    }


def build_event_title(cluster: EventCluster, main_keywords: list[str]) -> str:
    if main_keywords:
        return " / ".join(main_keywords[:4])

    longest = max((tweet.content for tweet in cluster.tweets), key=len, default="unknown event")
    compact = re.sub(r"\s+", " ", longest).strip()
    return compact[:90] or "unknown event"


def build_event_id(title: str, first_seen: str | None, sources: list[str]) -> str:
    seed = json.dumps(
        {"title": title, "first_seen": first_seen, "sources": sources},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def extract_oil_terms(content: str) -> tuple[set[str], set[str]]:
    lower = content.lower()
    entities: set[str] = set()
    keywords: set[str] = set()

    for rule in oil_keyword_rules():
        if len(rule) < 2:
            continue
        first, second = str(rule[0]), str(rule[1])
        first_hit = first.lower() in lower
        second_hit = second.lower() in lower

        if first_hit:
            add_oil_term(first, entities, keywords)
        if second_hit:
            add_oil_term(second, entities, keywords)
        if first_hit and second_hit:
            keywords.add(f"{first} {second}")

    for token in TOKEN_RE.findall(content):
        token_lower = token.lower()
        if token_lower in fallback_oil_terms():
            add_oil_term(token, entities, keywords)

    return entities, keywords


def add_oil_term(term: str, entities: set[str], keywords: set[str]) -> None:
    normalized = canonical_term(term)
    if not normalized:
        return
    if normalized.lower() in oil_entity_terms():
        entities.add(normalized)
    else:
        keywords.add(normalized)


def oil_keyword_rules() -> list[tuple]:
    from x_intel_rules import get_keyword_rules_by_domain

    return get_keyword_rules_by_domain("oil")


def oil_source_index() -> dict[str, str]:
    from x_intel_rules import get_accounts_by_group, get_accounts_by_level

    index = {}
    for level in ("S", "A", "B", "C"):
        for account in get_accounts_by_level(level):
            index[normalize_source(account).lower()] = level
    for account in get_accounts_by_group("oil"):
        index.setdefault(normalize_source(account).lower(), "oil")
    return index


def oil_entity_terms() -> set[str]:
    terms = {
        "opec", "opec+", "saudi", "saudi arabia", "russia", "iran", "venezuela",
        "eia", "api", "wti", "brent", "strait", "hormuz", "red sea", "houthi",
        "tanker", "pipeline", "refinery",
    }
    for rule in oil_keyword_rules():
        if len(rule) >= 2:
            for value in (rule[0], rule[1]):
                text = str(value).lower()
                if text[:1].isupper():
                    terms.add(text)
    return terms


def canonical_term(term: str) -> str:
    text = str(term).strip()
    if not text:
        return ""
    lower = text.lower()
    canonical = {
        "opec": "OPEC",
        "opec+": "OPEC+",
        "wti": "WTI",
        "brent": "Brent",
        "eia": "EIA",
        "api": "API",
        "iran": "Iran",
        "hormuz": "Hormuz",
        "red sea": "Red Sea",
        "saudi": "Saudi",
        "russia": "Russia",
        "tanker": "tanker",
        "tankers": "tanker",
        "oil": "oil",
        "crude": "crude",
    }
    return canonical.get(lower, lower)


def fallback_oil_terms() -> set[str]:
    return {
        "oil", "crude", "brent", "wti", "opec", "opec+", "hormuz", "iran",
        "sanction", "sanctions", "tanker", "tankers", "inventory", "eia",
        "api", "saudi", "russia", "pipeline", "refinery", "shutdown", "attack",
        "attacks", "quota", "production", "supply", "demand", "red", "sea",
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len({item.lower() for item in left} & {item.lower() for item in right})
    union = len({item.lower() for item in left} | {item.lower() for item in right})
    return intersection / union if union else 0.0


def max_text_similarity(content: str, candidates: list[str]) -> float:
    if not candidates:
        return 0.0
    content_norm = normalize_text(content)
    if not content_norm:
        return 0.0
    return max(SequenceMatcher(None, content_norm, normalize_text(candidate)).ratio() for candidate in candidates)


def normalize_text(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.lower()))


def rank_terms(terms: set[str], contents: list[str]) -> list[str]:
    joined = "\n".join(contents).lower()
    deduped = {}
    for term in terms:
        deduped.setdefault(term.lower(), term)
    return sorted(
        deduped.values(),
        key=lambda term: (joined.count(term.lower()), len(term)),
        reverse=True,
    )


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return ensure_aware(datetime.fromisoformat(text))
    except ValueError:
        return None


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_source(value: Any) -> str | None:
    text = to_str(value)
    if not text:
        return None
    if not text.startswith("@"):
        text = f"@{text}"
    return text


def first_value(raw: dict[str, Any], fields: Iterable[str]) -> Any:
    for field_name in fields:
        value = raw.get(field_name)
        if value is not None and str(value) != "nan":
            return value
    return None


def to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict):
                records.append(value)
    return records


def sample_cleaned_tweets() -> list[dict[str, Any]]:
    base = datetime.now(timezone.utc).replace(microsecond=0)
    return [
        {
            "tweet_id": "1",
            "timestamp": (base - timedelta(minutes=80)).isoformat(),
            "handle": "@Reuters",
            "content": "Iran says any Hormuz disruption would affect oil tankers and crude supply.",
        },
        {
            "tweet_id": "2",
            "timestamp": (base - timedelta(minutes=60)).isoformat(),
            "handle": "@JavierBlas",
            "content": "Oil traders watch Strait of Hormuz after Iran warning on tanker traffic.",
        },
        {
            "tweet_id": "3",
            "timestamp": (base - timedelta(minutes=35)).isoformat(),
            "handle": "@TankersTrackers",
            "content": "Tanker flows near Hormuz remain the key crude oil supply risk today.",
        },
        {
            "tweet_id": "4",
            "timestamp": (base - timedelta(minutes=25)).isoformat(),
            "handle": "@DeItaone",
            "content": "OPEC meeting headlines point to discussion of production quota compliance.",
        },
        {
            "tweet_id": "5",
            "timestamp": (base - timedelta(minutes=5)).isoformat(),
            "handle": "@JKempEnergy",
            "content": "EIA inventory data shows a crude stock draw, separate from OPEC quota news.",
        },
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cluster cleaned tweets into oil-related events")
    parser.add_argument("--input", help="Optional JSONL file with cleaned tweet dictionaries")
    parser.add_argument("--window-hours", type=float, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    parser.add_argument("--json", action="store_true", help="Print full event JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    tweets = load_jsonl(args.input) if args.input else sample_cleaned_tweets()
    events = cluster_events(
        tweets,
        window_hours=args.window_hours,
        similarity_threshold=args.similarity_threshold,
    )

    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return

    print(f"events={len(events)} tweets={len(tweets)} window_hours={args.window_hours}")
    for event in events:
        print(
            f"- {event['event_id']} | {event['event_title']} | "
            f"tweets={len(event['related_tweets'])} sources={event['source_count']} "
            f"first={event['first_seen_time']} last={event['last_seen_time']}"
        )


if __name__ == "__main__":
    main()
