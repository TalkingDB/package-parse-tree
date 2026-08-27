import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from talkingdb.models.api.mode import ClientMode

from talkingdb_pt.client import PTClient


def direct_config():
    return SimpleNamespace(
        CLIENT_MODE=ClientMode.DIRECT, API_TIMEOUT=30, TDB_API_KEY=None
    )


def api_config(api_key=None):
    return SimpleNamespace(
        CLIENT_MODE=ClientMode.API, API_TIMEOUT=30, TDB_API_KEY=api_key
    )


@pytest.fixture
def namespace():
    # Unique per test - DIRECT mode goes through the app's real module-level
    # registry/entity_conn, matching tests/unit/api's own convention.
    return f"client-test-{uuid.uuid4().hex[:8]}"


@pytest.mark.anyio
class TestDirectMode:
    async def test_extract_entities_calls_ner_client_directly(self, namespace):
        fake_response = {
            "universal_entities": [],
            "regex_entities": [],
            "no_tag_entities": [],
        }

        with patch(
            "talkingdb_pt.services.ner.client.extract_and_link",
            new=AsyncMock(return_value=fake_response),
        ) as mocked:
            result = await PTClient(config=direct_config()).extract_entities(
                namespace, "foo bar", word_correction=True
            )

        assert result == fake_response
        mocked.assert_awaited_once_with(namespace, "foo bar", True)

    async def test_extract_relations_parses_against_real_registry(self, namespace):
        # sentence.py imports extract_and_link at module load time, so the
        # patch target must be its own namespace, not ner.client's (matches
        # tests/unit/api/test_extract.py's own patch target for this path).
        with patch(
            "talkingdb_pt.services.parsing.sentence.extract_and_link",
            new=AsyncMock(
                return_value={
                    "universal_entities": [],
                    "regex_entities": [],
                    "no_tag_entities": [],
                }
            ),
        ):
            result = await PTClient(config=direct_config()).extract_relations(
                namespace, "hello"
            )

        assert result["parse_tree_output"].groups == []
        assert result["total_tokens"] == 0

    def test_ontology_type_roundtrip(self, namespace):
        client = PTClient(config=direct_config())

        registered = client.register_ontology_type(
            namespace,
            type_name="category",
            create_class=True,
            metadata={"class_type": "category"},
        )
        assert registered["kg_type_name"] == "Class_Type_Category"
        assert registered["status"] == "registered"

        types = client.list_ontology_types(namespace)
        assert any(t["kg_type_name"] == "Class_Type_Category" for t in types)

    def test_ontology_data_roundtrip(self, namespace):
        client = PTClient(config=direct_config())
        client.register_ontology_type(
            namespace,
            type_name="category",
            create_class=True,
            metadata={"class_type": "category"},
        )

        node_ids = client.upsert_ontology_data(
            namespace,
            [{"class_type": "category", "src_id": "shoes", "src_name": "Shoes"}],
        )
        assert len(node_ids) == 1
        assert client.count_ontology_data(namespace) >= 1

    def test_query_kg_data_returns_upserted_node(self, namespace):
        # kg/data only returns nodes with an instance_of edge (excludes bare
        # class nodes) - register the type for both class and instance use,
        # then create a class node and an instance pointing at it.
        client = PTClient(config=direct_config())
        client.register_ontology_type(
            namespace,
            type_name="category",
            create_class=True,
            create_instance=True,
            metadata={"class_type": "category", "instance_type": "category"},
        )
        client.upsert_ontology_data(
            namespace,
            [{"class_type": "category", "src_id": "shoes", "src_name": "Shoes"}],
        )
        client.upsert_ontology_data(
            namespace,
            [
                {
                    "instance_type": "category",
                    "src_id": "running-shoes",
                    "src_name": "Running Shoes",
                    "instance_of": ["shoes"],
                }
            ],
        )

        results = client.query_kg_data(
            namespace, filters=[{"field": "instance_of", "value": "shoes"}]
        )
        assert any(r.get("src_name") == "Running Shoes" for r in results)


class TestApiMode:
    def test_requires_pt_host(self):
        with pytest.raises(ValueError, match="PT_HOST"):
            PTClient(config=api_config())

    def test_extract_relations_posts_to_configured_host(self, monkeypatch):
        monkeypatch.setenv("PT_HOST", "http://pt.internal")
        client = PTClient(config=api_config(api_key="secret"))

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"parse_tree_output": {"groups": []}}
        client.session.post = MagicMock(return_value=fake_response)

        import asyncio

        result = asyncio.run(client.extract_relations("acme", "hello"))

        assert result == {"parse_tree_output": {"groups": []}}
        client.session.post.assert_called_once_with(
            "http://pt.internal/api/namespaces/acme/extract/relations",
            json={"user_query": "hello"},
            timeout=30,
        )
        assert client.session.headers["Authorization"] == "Bearer secret"

    def test_query_kg_data_posts_filters(self, monkeypatch):
        monkeypatch.setenv("PT_HOST", "http://pt.internal")
        client = PTClient(config=api_config())

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = [{"src_name": "Shoes"}]
        client.session.post = MagicMock(return_value=fake_response)

        result = client.query_kg_data("acme", limit=5)

        assert result == [{"src_name": "Shoes"}]
        client.session.post.assert_called_once_with(
            "http://pt.internal/api/namespaces/acme/kg/data",
            json={
                "filters": [],
                "sorters": [],
                "limit": 5,
                "offset": 0,
                "fields": None,
            },
            timeout=30,
        )
