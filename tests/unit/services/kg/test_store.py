from talkingdb.models.entity.entity import EntityModel

from talkingdb_pt.services.kg import store as kg_store
from tests.conftest import make_bundle


def test_upsert_node_and_read_label(bundle):
    kg_store.upsert_node(bundle, "smartphone", label="Category")

    assert kg_store.node_label(bundle, "smartphone") == "Category"


def test_node_label_missing_node_returns_none(bundle):
    assert kg_store.node_label(bundle, "does-not-exist") is None


def test_upsert_node_writes_scalar_props(bundle):
    kg_store.upsert_node(
        bundle,
        "storage-capacity",
        label="AttributeClass",
        scalar_props={"src_name": "Storage Capacity", "multiplier": 1000.0},
    )

    assert kg_store.node_property(bundle, "storage-capacity", "src_name") == (
        "Storage Capacity"
    )
    assert kg_store.node_properties(
        bundle, "storage-capacity", ["src_name", "multiplier"]
    ) == {"src_name": "Storage Capacity", "multiplier": 1000.0}


def test_upsert_edge_and_find_ancestors_one_hop(bundle):
    kg_store.upsert_node(bundle, "iphone-15", label="Instance")
    kg_store.upsert_node(bundle, "smartphone", label="Category")
    kg_store.upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")

    ancestors = kg_store.find_ancestors(bundle, "iphone-15", predicate="instance_of")

    assert ancestors[1] == [{"node_id": "smartphone"}]


def test_find_ancestors_multi_hop_with_fields(bundle):
    kg_store.upsert_node(bundle, "iphone-15", label="Instance")
    kg_store.upsert_node(
        bundle, "smartphone", label="Category", scalar_props={"src_name": "Smartphone"}
    )
    kg_store.upsert_node(
        bundle,
        "electronics",
        label="Category",
        scalar_props={"src_name": "Electronics"},
    )
    kg_store.upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")
    kg_store.upsert_edge(bundle, "smartphone", "subclass_of", "electronics")

    ancestors = kg_store.find_ancestors(
        bundle,
        "iphone-15",
        predicate="instance_of",
        max_hops=1,
        fields_by_hop={1: ["src_name"]},
    )

    assert ancestors[1] == [{"node_id": "smartphone", "src_name": "Smartphone"}]

    chain = kg_store.superclass_chain(bundle, "smartphone")
    assert chain == ["electronics"]


def test_find_ancestors_stops_when_no_more_edges(bundle):
    kg_store.upsert_node(bundle, "leaf", label="Instance")

    ancestors = kg_store.find_ancestors(bundle, "leaf", max_hops=5)

    assert ancestors == {}


def test_superclass_chain_handles_cycle_without_infinite_loop(bundle):
    kg_store.upsert_node(bundle, "a", label="Category")
    kg_store.upsert_node(bundle, "b", label="Category")
    kg_store.upsert_edge(bundle, "a", "subclass_of", "b")
    kg_store.upsert_edge(bundle, "b", "subclass_of", "a")

    chain = kg_store.superclass_chain(bundle, "a")

    assert chain == ["b"]


def test_nodes_by_label(bundle):
    kg_store.upsert_node(bundle, "a", label="Category")
    kg_store.upsert_node(bundle, "b", label="Category")
    kg_store.upsert_node(bundle, "c", label="Instance")

    labeled = {n["node_id"] for n in kg_store.nodes_by_label(bundle, "Category")}

    assert labeled == {"a", "b"}


def test_nodes_with_edge_and_source_of_edge(bundle):
    kg_store.upsert_node(bundle, "smartphone", label="Category")
    kg_store.upsert_node(bundle, "color", label="AttributeClass")
    kg_store.upsert_edge(bundle, "smartphone", "has_attributes", "color")

    edges = kg_store.nodes_with_edge(bundle, "has_attributes")
    assert edges == [{"source": "smartphone", "target": "color"}]

    source = kg_store.source_of_edge(bundle, "has_attributes", "color")
    assert source == "smartphone"


def test_source_of_edge_missing_target_returns_none(bundle):
    assert kg_store.source_of_edge(bundle, "has_attributes", "missing") is None


def test_tenant_overrides_universal_node(memory_conn):
    bundle = make_bundle(memory_conn, "acme")

    kg_store.upsert_node(bundle, "smartphone", label="Category", universal=True)
    assert kg_store.node_label(bundle, "smartphone") == "Category"

    kg_store.upsert_node(bundle, "smartphone", label="AcmeSpecificCategory")

    assert kg_store.node_label(bundle, "smartphone") == "AcmeSpecificCategory"


def test_universal_node_visible_to_tenant_without_override(memory_conn):
    bundle = make_bundle(memory_conn, "acme")

    kg_store.upsert_node(bundle, "shared-attr", label="AttributeClass", universal=True)

    assert kg_store.node_label(bundle, "shared-attr") == "AttributeClass"


def test_save_and_reload_round_trip(memory_conn):
    bundle = make_bundle(memory_conn, "acme")
    kg_store.upsert_node(bundle, "smartphone", label="Category")
    kg_store.upsert_node(bundle, "iphone-15", label="Instance")
    kg_store.upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")
    kg_store.save(bundle)

    reloaded_tenant = EntityModel.load(
        conn=memory_conn, entity_id=EntityModel.make_id("ontology::acme")
    )

    assert reloaded_tenant.has_entity("smartphone")
    assert reloaded_tenant.has_entity("iphone-15")

    fact_edges = [
        data
        for _, _, data in reloaded_tenant.graph.edges(data=True)
        if data.get("predicate") == "instance_of"
    ]
    assert len(fact_edges) == 1


def test_save_persists_universal_partition_separately(memory_conn):
    bundle = make_bundle(memory_conn, "acme")
    kg_store.upsert_node(bundle, "shared", label="Category", universal=True)
    kg_store.save(bundle)

    reloaded_universal = EntityModel.load(
        conn=memory_conn, entity_id=EntityModel.make_id("ontology::universal")
    )
    reloaded_tenant = EntityModel.load(
        conn=memory_conn, entity_id=EntityModel.make_id("ontology::acme")
    )

    assert reloaded_universal.has_entity("shared")
    assert not reloaded_tenant.has_entity("shared")


def test_delete_scalar_values_clears_field(bundle):
    kg_store.upsert_node(
        bundle, "attr", label="AttributeClass", scalar_props={"multiplier": 5.0}
    )
    kg_store.delete_scalar_values(bundle, "attr", "multiplier")

    assert kg_store.node_property(bundle, "attr", "multiplier") is None


def test_registry_caches_bundle_per_namespace():
    registry = kg_store.OntologyRegistry()

    from unittest.mock import patch

    with patch(
        "talkingdb_pt.services.kg.store._build_bundle",
        wraps=kg_store._build_bundle,
    ) as build:
        registry.get("acme")
        registry.get("acme")

        assert build.call_count == 1


def test_registry_evict_forces_rebuild():
    registry = kg_store.OntologyRegistry()

    from unittest.mock import patch

    with patch(
        "talkingdb_pt.services.kg.store._build_bundle",
        wraps=kg_store._build_bundle,
    ) as build:
        registry.get("acme")
        registry.evict("acme")
        registry.get("acme")

        assert build.call_count == 2
