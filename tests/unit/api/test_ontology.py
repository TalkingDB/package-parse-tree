import uuid

import pytest
from fastapi.testclient import TestClient

from talkingdb_pt.main import app

client = TestClient(app)


@pytest.fixture
def namespace():
    # Unique per test - the app's registry/entity_conn are real module-level
    # singletons shared across the whole test session (matches
    # package-named-entity-linker's own testing convention), so tests must
    # not collide on namespace.
    return f"test-{uuid.uuid4().hex[:8]}"


def register_category_type(namespace: str):
    return client.post(
        f"/api/namespaces/{namespace}/ontology/types",
        json={
            "type_name": "category",
            "create_class": True,
            "metadata": {"class_type": "category"},
        },
    )


def test_register_ontology_type(namespace):
    response = register_category_type(namespace)

    assert response.status_code == 200
    body = response.json()
    assert body["kg_type_name"] == "Class_Type_Category"
    assert body["status"] == "registered"


def test_list_ontology_types(namespace):
    register_category_type(namespace)

    response = client.get(f"/api/namespaces/{namespace}/ontology/types")

    assert response.status_code == 200
    types = response.json()
    assert len(types) == 1
    assert types[0]["kg_type_name"] == "Class_Type_Category"


def test_write_and_count_ontology_data(namespace):
    register_category_type(namespace)

    write_response = client.post(
        f"/api/namespaces/{namespace}/ontology/data",
        json=[
            {"src_id": "electronics", "class_type": "category", "src_name": "Electronics"},
            {"src_id": "smartphones", "class_type": "category"},
        ],
    )

    assert write_response.status_code == 200
    assert write_response.json() == {"node_ids": ["electronics", "smartphones"]}

    count_response = client.get(f"/api/namespaces/{namespace}/ontology/data")

    assert count_response.status_code == 200
    assert count_response.json() == {
        "namespace": namespace,
        "nodes_trained": 2,
    }


def test_write_ontology_data_unregistered_type_returns_400(namespace):
    response = client.post(
        f"/api/namespaces/{namespace}/ontology/data",
        json=[{"src_id": "x", "class_type": "never-registered"}],
    )

    assert response.status_code == 400


def test_ontology_types_apply_endpoint_does_not_exist(namespace):
    # Explicit regression guard for the plan's scope reduction: there is no
    # SQLite equivalent to Dgraph's schema-then-mutate model, so this legacy
    # endpoint must not exist in the new service.
    response = client.post(f"/api/namespaces/{namespace}/ontology/types/apply")

    assert response.status_code == 404
