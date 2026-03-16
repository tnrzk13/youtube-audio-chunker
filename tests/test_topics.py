import json

import pytest

from youtube_audio_chunker.topics import (
    Topic,
    TopicStore,
    load_topics,
    save_topics,
    add_topic,
    update_topic,
    delete_topic,
    dismiss_video,
    record_video_history,
    get_excluded_video_ids,
)
from youtube_audio_chunker.library import Library, QueueEntry, DownloadedEpisode


@pytest.fixture
def topics_path(tmp_app_dir):
    return tmp_app_dir / "topics.json"


@pytest.fixture
def empty_store():
    return TopicStore(topics=[], dismissed_video_ids=[], video_history=[])


class TestLoadTopics:
    def test_returns_empty_store_when_file_missing(self, topics_path):
        store = load_topics(topics_path)
        assert store.topics == []
        assert store.dismissed_video_ids == []
        assert store.video_history == []

    def test_loads_existing_store(self, topics_path):
        data = {
            "topics": [
                {
                    "id": "t1",
                    "name": "predictive history",
                    "search_query": "predictive history documentary",
                    "source_video_ids": ["abc"],
                    "created_at": "2026-03-01T00:00:00+00:00",
                }
            ],
            "dismissed_video_ids": ["xyz"],
            "video_history": ["abc", "def"],
        }
        topics_path.write_text(json.dumps(data))

        store = load_topics(topics_path)
        assert len(store.topics) == 1
        assert store.topics[0].name == "predictive history"
        assert store.dismissed_video_ids == ["xyz"]
        assert store.video_history == ["abc", "def"]

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "topics.json"
        store = load_topics(nested)
        assert store.topics == []
        assert nested.parent.exists()


class TestSaveTopics:
    def test_roundtrip(self, topics_path):
        store = TopicStore(
            topics=[
                Topic(
                    id="t1",
                    name="history",
                    search_query="history documentary",
                    source_video_ids=["v1"],
                    created_at="2026-03-01T00:00:00+00:00",
                )
            ],
            dismissed_video_ids=["d1"],
            video_history=["v1", "v2"],
        )
        save_topics(store, topics_path)

        loaded = load_topics(topics_path)
        assert len(loaded.topics) == 1
        assert loaded.topics[0].id == "t1"
        assert loaded.dismissed_video_ids == ["d1"]
        assert loaded.video_history == ["v1", "v2"]


class TestAddTopic:
    def test_adds_topic_with_generated_id(self, empty_store):
        store = add_topic(empty_store, "ai safety", "ai safety research", ["v1"])
        assert len(store.topics) == 1
        assert store.topics[0].name == "ai safety"
        assert store.topics[0].search_query == "ai safety research"
        assert store.topics[0].source_video_ids == ["v1"]
        assert store.topics[0].id  # has an id
        assert store.topics[0].created_at  # has a timestamp

    def test_adds_multiple_topics(self, empty_store):
        add_topic(empty_store, "topic1", "q1", [])
        add_topic(empty_store, "topic2", "q2", [])
        assert len(empty_store.topics) == 2
        assert empty_store.topics[0].id != empty_store.topics[1].id


class TestUpdateTopic:
    def test_updates_name(self, empty_store):
        add_topic(empty_store, "old name", "old query", [])
        topic_id = empty_store.topics[0].id
        update_topic(empty_store, topic_id, name="new name")
        assert empty_store.topics[0].name == "new name"
        assert empty_store.topics[0].search_query == "old query"

    def test_updates_search_query(self, empty_store):
        add_topic(empty_store, "name", "old query", [])
        topic_id = empty_store.topics[0].id
        update_topic(empty_store, topic_id, search_query="new query")
        assert empty_store.topics[0].search_query == "new query"
        assert empty_store.topics[0].name == "name"

    def test_returns_none_for_unknown_id(self, empty_store):
        result = update_topic(empty_store, "nonexistent", name="x")
        assert result is None


class TestDeleteTopic:
    def test_removes_topic(self, empty_store):
        add_topic(empty_store, "topic", "query", [])
        topic_id = empty_store.topics[0].id
        delete_topic(empty_store, topic_id)
        assert len(empty_store.topics) == 0

    def test_noop_for_unknown_id(self, empty_store):
        add_topic(empty_store, "topic", "query", [])
        delete_topic(empty_store, "nonexistent")
        assert len(empty_store.topics) == 1


class TestDismissVideo:
    def test_adds_to_dismissed(self, empty_store):
        dismiss_video(empty_store, "vid1")
        assert "vid1" in empty_store.dismissed_video_ids

    def test_no_duplicates(self, empty_store):
        dismiss_video(empty_store, "vid1")
        dismiss_video(empty_store, "vid1")
        assert empty_store.dismissed_video_ids.count("vid1") == 1


class TestRecordVideoHistory:
    def test_appends_video_ids(self, empty_store):
        record_video_history(empty_store, ["v1", "v2"])
        assert "v1" in empty_store.video_history
        assert "v2" in empty_store.video_history

    def test_no_duplicates(self, empty_store):
        record_video_history(empty_store, ["v1"])
        record_video_history(empty_store, ["v1", "v2"])
        assert empty_store.video_history.count("v1") == 1
        assert "v2" in empty_store.video_history


class TestGetExcludedVideoIds:
    def test_combines_all_sources(self):
        store = TopicStore(
            topics=[],
            dismissed_video_ids=["dismissed1"],
            video_history=["history1"],
        )
        library = Library(
            queue=[QueueEntry(video_id="queued1", url="u", title="t", added_at="t")],
            downloaded=[
                DownloadedEpisode(
                    video_id="downloaded1", url="u", title="t", folder_name="f",
                    chunk_count=1, total_size_bytes=100,
                    downloaded_at="t", synced_at=None,
                )
            ],
        )
        excluded = get_excluded_video_ids(store, library)
        assert excluded == {"dismissed1", "history1", "queued1", "downloaded1"}

    def test_empty_sources(self, empty_store):
        library = Library(queue=[], downloaded=[])
        excluded = get_excluded_video_ids(empty_store, library)
        assert excluded == set()
