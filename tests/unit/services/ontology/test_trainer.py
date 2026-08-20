import pytest

from talkingdb_pt.services.kg.store import node_label, node_property
from talkingdb_pt.services.ontology import trainer


def register_category_type(conn, namespace="acme"):
    return trainer.add_type_to_ontology(
        conn,
        namespace=namespace,
        type_name="category",
        create_class=True,
        create_instance=False,
        extra_attrs={"has_attributes": {"value_type": "[REF]"}},
        metadata={"class_type": "category"},
    )


def register_smartphone_type(conn, namespace="acme"):
    return trainer.add_type_to_ontology(
        conn,
        namespace=namespace,
        type_name="smartphone",
        create_class=False,
        create_instance=True,
        metadata={"instance_type": "smartphone"},
    )


def test_add_type_to_ontology_returns_kg_type_name(memory_conn):
    kg_type_name = register_category_type(memory_conn)
    assert kg_type_name == "Class_Type_Category"


def test_view_ontology_types_lists_registered_type(memory_conn):
    register_category_type(memory_conn)

    types = trainer.view_ontology_types(memory_conn, "acme")

    assert len(types) == 1
    assert types[0]["kg_type_name"] == "Class_Type_Category"
    assert types[0]["class_type_group"] == "category"


def test_add_node_to_kg_creates_class_node(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)

    node_id = trainer.add_node_to_kg(
        bundle,
        {
            "src_id": "category-electronics",
            "class_type": "category",
            "src_name": "Electronics",
        },
    )

    assert node_id == "category-electronics"
    assert node_label(bundle, "category-electronics") == "Class_Type_Category"
    assert node_property(bundle, "category-electronics", "src_name") == "Electronics"


def test_add_node_to_kg_sets_surface_texts_from_alternate_names(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)

    trainer.add_node_to_kg(
        bundle,
        {
            "src_id": "category-electronics",
            "class_type": "category",
            "alternate_names": ["Electronics", "Consumer Electronics"],
        },
    )

    entity = bundle.tenant.get_entity("category-electronics")
    assert set(entity["surface_texts"]) == {"Electronics", "Consumer Electronics"}


def test_add_node_to_kg_creates_builtin_instance_of_edge(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)
    register_smartphone_type(bundle.entity_conn, bundle.namespace)

    trainer.add_node_to_kg(
        bundle, {"src_id": "smartphone-cat", "class_type": "category"}
    )
    trainer.add_node_to_kg(
        bundle,
        {
            "src_id": "iphone-15",
            "instance_type": "smartphone",
            "instance_of": ["smartphone-cat"],
        },
    )

    from talkingdb_pt.services.kg.store import find_ancestors

    ancestors = find_ancestors(bundle, "iphone-15", predicate="instance_of")
    assert ancestors[1] == [{"node_id": "smartphone-cat"}]


def test_add_node_to_kg_creates_extra_attrs_ref_edge(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)
    trainer.add_node_to_kg(
        bundle, {"src_id": "electronics", "class_type": "category"}
    )
    trainer.add_node_to_kg(
        bundle,
        {"src_id": "color-attr", "class_type": "category", "src_name": "Color"},
    )

    trainer.add_node_to_kg(
        bundle,
        {
            "src_id": "electronics",
            "class_type": "category",
            "has_attributes": ["color-attr"],
        },
    )

    from talkingdb_pt.services.kg.store import nodes_with_edge

    edges = nodes_with_edge(bundle, "has_attributes")
    assert {"source": "electronics", "target": "color-attr"} in edges


def test_add_node_to_kg_unknown_scalar_key_goes_to_extra_json(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)

    trainer.add_node_to_kg(
        bundle,
        {
            "src_id": "electronics",
            "class_type": "category",
            "some_custom_field": "custom-value",
        },
    )

    props = node_property(bundle, "electronics", "extra_json")
    assert props == {"some_custom_field": "custom-value"}


def test_add_node_to_kg_requires_src_id(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)

    with pytest.raises(trainer.OntologyTrainerError):
        trainer.add_node_to_kg(bundle, {"class_type": "category"})


def test_add_node_to_kg_requires_registered_type(bundle):
    with pytest.raises(trainer.OntologyTrainerError):
        trainer.add_node_to_kg(
            bundle, {"src_id": "x", "class_type": "never-registered"}
        )


def test_add_node_to_kg_edge_to_missing_target_raises(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)
    register_smartphone_type(bundle.entity_conn, bundle.namespace)

    with pytest.raises(trainer.OntologyTrainerError):
        trainer.add_node_to_kg(
            bundle,
            {
                "src_id": "iphone-15",
                "instance_type": "smartphone",
                "instance_of": ["does-not-exist"],
            },
        )


def test_add_data_to_kg_writes_batch_and_persists(bundle):
    register_category_type(bundle.entity_conn, bundle.namespace)

    node_ids = trainer.add_data_to_kg(
        bundle,
        [
            {"src_id": "electronics", "class_type": "category"},
            {"src_id": "smartphones", "class_type": "category"},
        ],
    )

    assert node_ids == ["electronics", "smartphones"]
    assert trainer.get_nodes_number_trained(bundle) == 2


def test_get_nodes_number_trained_starts_at_zero(bundle):
    assert trainer.get_nodes_number_trained(bundle) == 0
