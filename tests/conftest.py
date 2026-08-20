import sqlite3

import pytest
from talkingdb.models.entity.entity import EntityModel

from talkingdb_pt.services.kg.store import OntologyBundle
from talkingdb_pt.services.ontology import store as ontology_store


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    EntityModel.init_db(conn)
    ontology_store.init_db(conn)

    yield conn

    conn.close()


def make_bundle(conn: sqlite3.Connection, namespace: str) -> OntologyBundle:
    universal = EntityModel.create(EntityModel.make_id("ontology::universal"))
    tenant = (
        universal
        if namespace == ontology_store.UNIVERSAL_NAMESPACE
        else EntityModel.create(EntityModel.make_id(f"ontology::{namespace}"))
    )

    bundle = OntologyBundle(
        namespace=namespace,
        universal=universal,
        tenant=tenant,
        graph=None,  # set by refresh_graph()
        entity_conn=conn,
    )
    bundle.refresh_graph()

    return bundle


@pytest.fixture
def bundle(memory_conn):
    return make_bundle(memory_conn, "acme")
