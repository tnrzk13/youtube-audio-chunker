"""Topic storage for video discovery - tracks user interests and exclusions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

from youtube_audio_chunker.constants import APP_DIR


TOPICS_PATH = APP_DIR / "topics.json"


@dataclass
class Topic:
    id: str
    name: str
    search_query: str
    source_video_ids: list[str]
    created_at: str


@dataclass
class TopicStore:
    topics: list[Topic]
    dismissed_video_ids: list[str]
    video_history: list[str]


def load_topics(path: Path = TOPICS_PATH) -> TopicStore:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return TopicStore(topics=[], dismissed_video_ids=[], video_history=[])

    data = json.loads(path.read_text())
    topics = [Topic(**t) for t in data.get("topics", [])]
    return TopicStore(
        topics=topics,
        dismissed_video_ids=data.get("dismissed_video_ids", []),
        video_history=data.get("video_history", []),
    )


def save_topics(store: TopicStore, path: Path = TOPICS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "topics": [asdict(t) for t in store.topics],
        "dismissed_video_ids": store.dismissed_video_ids,
        "video_history": store.video_history,
    }
    path.write_text(json.dumps(data, indent=2))


def add_topic(
    store: TopicStore,
    name: str,
    search_query: str,
    source_video_ids: list[str],
) -> TopicStore:
    topic = Topic(
        id=str(uuid.uuid4()),
        name=name,
        search_query=search_query,
        source_video_ids=source_video_ids,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    store.topics.append(topic)
    return store


def update_topic(
    store: TopicStore,
    topic_id: str,
    name: str | None = None,
    search_query: str | None = None,
) -> Topic | None:
    for topic in store.topics:
        if topic.id == topic_id:
            if name is not None:
                topic.name = name
            if search_query is not None:
                topic.search_query = search_query
            return topic
    return None


def delete_topic(store: TopicStore, topic_id: str) -> TopicStore:
    store.topics = [t for t in store.topics if t.id != topic_id]
    return store


def dismiss_video(store: TopicStore, video_id: str) -> TopicStore:
    if video_id not in store.dismissed_video_ids:
        store.dismissed_video_ids.append(video_id)
    return store


def record_video_history(store: TopicStore, video_ids: list[str]) -> TopicStore:
    existing = set(store.video_history)
    for vid in video_ids:
        if vid not in existing:
            store.video_history.append(vid)
            existing.add(vid)
    return store


def get_excluded_video_ids(store: TopicStore, library) -> set[str]:
    """Union of video_history + dismissed_video_ids + current library video_ids."""
    excluded = set(store.video_history) | set(store.dismissed_video_ids)
    excluded |= {e.video_id for e in library.queue}
    excluded |= {e.video_id for e in library.downloaded}
    return excluded
