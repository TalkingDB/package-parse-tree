from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from talkingdb_pt.main import app

client = TestClient(app)


def test_extract_entities_passes_through_nel_response():
    fake_response = {
        "universal_entities": [],
        "regex_entities": [],
        "no_tag_entities": [{"index": [0, 3], "surface_text": "foo"}],
    }

    with patch(
        "talkingdb_pt.api.extract.extract_and_link",
        new=AsyncMock(return_value=fake_response),
    ) as mocked:
        response = client.post(
            "/api/namespaces/test-ns/extract/entities",
            json={"user_query": "foo bar", "word_correction": True},
        )

    assert response.status_code == 200
    assert response.json() == fake_response
    mocked.assert_awaited_once_with("test-ns", "foo bar", True)


def test_extract_entities_defaults_word_correction_false():
    with patch(
        "talkingdb_pt.api.extract.extract_and_link",
        new=AsyncMock(return_value={}),
    ) as mocked:
        client.post(
            "/api/namespaces/test-ns/extract/entities",
            json={"user_query": "foo"},
        )

    mocked.assert_awaited_once_with("test-ns", "foo", False)
