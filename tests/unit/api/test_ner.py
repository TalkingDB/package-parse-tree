import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from talkingdb_pt.main import app
from talkingdb_pt.services.kg.store import registry, upsert_node

client = TestClient(app)


@pytest.fixture
def namespace():
    return f"test-{uuid.uuid4().hex[:8]}"


def test_train_ner(namespace):
    registry.get(namespace)  # ensure the bundle exists (empty ontology is fine)

    with patch(
        "talkingdb_pt.services.ner.trainer.upsert_entity",
        new=AsyncMock(return_value={}),
    ):
        response = client.post(f"/api/namespaces/{namespace}/ner/train")

    assert response.status_code == 200
    body = response.json()
    assert "entities_trained" in body


def test_create_synonyms(namespace):
    bundle = registry.get(namespace)
    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15"])

    with patch(
        "talkingdb_pt.services.ner.trainer.add_entity_surface_text", new=AsyncMock()
    ):
        response = client.post(
            f"/api/namespaces/{namespace}/ner/synonyms",
            json={"src_id": "iphone-15", "aliases": ["iPhone15"]},
        )

    assert response.status_code == 200
    assert response.json()["alternate_names"] == ["iphone 15", "iphone15"]


def test_create_synonyms_unknown_entity_returns_404(namespace):
    registry.get(namespace)

    response = client.post(
        f"/api/namespaces/{namespace}/ner/synonyms",
        json={"src_id": "does-not-exist", "aliases": ["x"]},
    )

    assert response.status_code == 404


def test_delete_synonyms(namespace):
    bundle = registry.get(namespace)
    upsert_node(
        bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15", "iPhone15"]
    )

    with patch(
        "talkingdb_pt.services.ner.trainer.update_entity_surface_texts", new=AsyncMock()
    ):
        response = client.request(
            "DELETE",
            f"/api/namespaces/{namespace}/ner/synonyms",
            json={"src_id": "iphone-15", "aliases": ["iPhone15"]},
        )

    assert response.status_code == 200
    assert response.json()["alternate_names"] == ["iphone 15"]


def test_get_synonyms_returns_csv(namespace):
    bundle = registry.get(namespace)
    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15"])

    response = client.get(f"/api/namespaces/{namespace}/ner/synonyms")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "iphone-15" in response.text


def test_create_synonyms_many(namespace):
    bundle = registry.get(namespace)
    upsert_node(bundle, "a", label="Instance")
    upsert_node(bundle, "b", label="Instance")

    with patch(
        "talkingdb_pt.services.ner.trainer.add_entity_surface_text", new=AsyncMock()
    ):
        response = client.post(
            f"/api/namespaces/{namespace}/ner/synonyms/many",
            json=[
                {"src_id": "a", "aliases": ["x"]},
                {"src_id": "b", "aliases": ["y"]},
            ],
        )

    assert response.status_code == 200
    assert [r["src_id"] for r in response.json()] == ["a", "b"]


def test_synonyms_cache_endpoint_does_not_exist(namespace):
    # Explicit regression guard: there's no separate Mongo mirror to
    # refresh anymore, so PUT /synonyms/cache is dropped, not re-plumbed.
    response = client.put(f"/api/namespaces/{namespace}/ner/synonyms/cache")

    assert response.status_code == 404
