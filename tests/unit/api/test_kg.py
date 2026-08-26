import uuid

import pytest
from fastapi.testclient import TestClient

from talkingdb_pt.main import app
from talkingdb_pt.services.kg.store import registry, upsert_edge, upsert_node

client = TestClient(app)


@pytest.fixture
def namespace():
    return f"test-{uuid.uuid4().hex[:8]}"


def seed_products(namespace):
    bundle = registry.get(namespace)
    upsert_node(bundle, "smartphone", label="Category")
    upsert_node(
        bundle,
        "iphone-15",
        label="Instance",
        surface_texts=["iPhone 15"],
        scalar_props={"src_name": "iPhone 15"},
    )
    upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")
    return bundle


def test_get_kg_data_filters_by_instance_of(namespace):
    seed_products(namespace)

    response = client.post(
        f"/api/namespaces/{namespace}/kg/data",
        json={"filters": [{"field": "instance_of", "value": "smartphone"}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["node_id"] == "iphone-15"


def test_get_kg_data_rejects_zero_limit(namespace):
    seed_products(namespace)

    response = client.post(f"/api/namespaces/{namespace}/kg/data", json={"limit": 0})

    assert response.status_code == 400


def test_get_kg_data_multiple(namespace):
    seed_products(namespace)

    response = client.post(
        f"/api/namespaces/{namespace}/kg/data/filters/multiple",
        json={
            "queries": [{"filters": [{"field": "instance_of", "value": "smartphone"}]}]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert len(body[0]["results"]) == 1


def test_kg_entities_synonyms(namespace):
    seed_products(namespace)

    response = client.get(f"/api/namespaces/{namespace}/kg/entities/synonyms?limit=10")

    assert response.status_code == 200
    body = response.json()
    entry = next(r for r in body if r["node_id"] == "iphone-15")
    assert entry["alternate_names"] == ["iPhone 15"]


def test_kg_entities_properties(namespace):
    seed_products(namespace)

    response = client.post(
        f"/api/namespaces/{namespace}/kg/entities/properties",
        json={"node_id": "iphone-15", "properties": ["src_name"]},
    )

    assert response.status_code == 200
    assert response.json() == {"src_name": "iPhone 15"}


def test_predicates_data_types_endpoint_does_not_exist(namespace):
    # Explicit regression guard: no live Dgraph predicate-type schema
    # exists anymore, so this legacy endpoint is dropped, not re-plumbed.
    response = client.get(f"/api/namespaces/{namespace}/kg/predicates/data-types")

    assert response.status_code == 404
