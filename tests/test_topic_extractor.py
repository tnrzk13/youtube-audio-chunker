import json
from unittest.mock import MagicMock, patch

import pytest

from youtube_audio_chunker.topic_extractor import extract_topics_from_titles


SAMPLE_TOPICS = [
    {"name": "predictive history", "search_query": "predictive history documentary"},
    {"name": "ai safety", "search_query": "ai safety research lectures"},
]


class TestExtractTopicsAnthropic:
    def test_extracts_topics_from_claude_response(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(SAMPLE_TOPICS))]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("youtube_audio_chunker.topic_extractor.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client

            result = extract_topics_from_titles(
                ["The History That Predicts the Future", "AI Safety Research 2026"],
                api_key="test-key",
            )

        assert len(result) == 2
        assert result[0]["name"] == "predictive history"
        assert result[1]["search_query"] == "ai safety research lectures"

        mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-haiku-4-5-20251001"

    def test_uses_custom_model(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(SAMPLE_TOPICS))]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("youtube_audio_chunker.topic_extractor.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client

            extract_topics_from_titles(
                ["Some Title"],
                api_key="test-key",
                model="claude-sonnet-4-6",
            )

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    def test_returns_empty_list_on_empty_titles(self):
        result = extract_topics_from_titles([], api_key="test-key")
        assert result == []

    def test_handles_malformed_response(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("youtube_audio_chunker.topic_extractor.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client

            result = extract_topics_from_titles(
                ["Some Video Title"],
                api_key="test-key",
            )

        assert result == []

    def test_handles_api_error(self):
        with patch("youtube_audio_chunker.topic_extractor.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.side_effect = Exception("API error")

            result = extract_topics_from_titles(
                ["Some Video Title"],
                api_key="test-key",
            )

        assert result == []


class TestExtractTopicsOpenAI:
    def test_extracts_topics_from_openai_response(self):
        mock_message = MagicMock()
        mock_message.content = json.dumps(SAMPLE_TOPICS)

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("youtube_audio_chunker.topic_extractor.openai") as mock_openai:
            mock_openai.OpenAI.return_value = mock_client

            result = extract_topics_from_titles(
                ["The History That Predicts the Future", "AI Safety Research 2026"],
                api_key="test-openai-key",
                provider="openai",
            )

        assert len(result) == 2
        assert result[0]["name"] == "predictive history"

        mock_openai.OpenAI.assert_called_once_with(api_key="test-openai-key")
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o-mini"

    def test_uses_custom_model(self):
        mock_message = MagicMock()
        mock_message.content = json.dumps(SAMPLE_TOPICS)
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("youtube_audio_chunker.topic_extractor.openai") as mock_openai:
            mock_openai.OpenAI.return_value = mock_client

            extract_topics_from_titles(
                ["Some Title"],
                api_key="test-key",
                provider="openai",
                model="gpt-4o",
            )

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"

    def test_handles_openai_api_error(self):
        with patch("youtube_audio_chunker.topic_extractor.openai") as mock_openai:
            mock_openai.OpenAI.side_effect = Exception("OpenAI error")

            result = extract_topics_from_titles(
                ["Some Video Title"],
                api_key="test-key",
                provider="openai",
            )

        assert result == []
