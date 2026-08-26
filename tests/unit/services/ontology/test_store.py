from talkingdb_pt.services.ontology import store as ontology_store


def test_upsert_and_get_ontology_type(memory_conn):
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="Class_Type_Category",
        type_name="category",
        is_class=True,
        is_instance=False,
        class_type_group="category",
        extra_attrs={"note": "top-level grouping"},
        relationship_triples=[["category", "subclass_of", "category"]],
    )

    result = ontology_store.get_ontology_type(
        memory_conn, "acme", "Class_Type_Category"
    )

    assert result["type_name"] == "category"
    assert result["is_class"] is True
    assert result["is_instance"] is False
    assert result["extra_attrs"] == {"note": "top-level grouping"}
    assert result["relationship_triples"] == [["category", "subclass_of", "category"]]


def test_upsert_ontology_type_overwrites_on_conflict(memory_conn):
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="Class_Type_Category",
        type_name="category",
        is_class=True,
        is_instance=False,
    )
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="Class_Type_Category",
        type_name="renamed-category",
        is_class=True,
        is_instance=True,
    )

    result = ontology_store.get_ontology_type(
        memory_conn, "acme", "Class_Type_Category"
    )

    assert result["type_name"] == "renamed-category"
    assert result["is_instance"] is True


def test_find_ontology_type_falls_back_to_universal(memory_conn):
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace=ontology_store.UNIVERSAL_NAMESPACE,
        kg_type_name="Class_Type_Category",
        type_name="category",
        is_class=True,
        is_instance=False,
        class_type_group="category",
    )

    found = ontology_store.find_ontology_type(
        memory_conn, "acme", group="category", data_type="class_type_group"
    )

    assert found is not None
    assert found["namespace"] == ontology_store.UNIVERSAL_NAMESPACE
    assert found["kg_type_name"] == "Class_Type_Category"


def test_find_ontology_type_namespace_overrides_universal(memory_conn):
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace=ontology_store.UNIVERSAL_NAMESPACE,
        kg_type_name="Class_Type_Category",
        type_name="category",
        is_class=True,
        is_instance=False,
        class_type_group="category",
    )
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="Class_Type_AcmeCategory",
        type_name="acme-category",
        is_class=True,
        is_instance=False,
        class_type_group="category",
    )

    found = ontology_store.find_ontology_type(
        memory_conn, "acme", group="category", data_type="class_type_group"
    )

    assert found["namespace"] == "acme"
    assert found["kg_type_name"] == "Class_Type_AcmeCategory"


def test_find_ontology_type_disambiguates_by_type_name(memory_conn):
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="A",
        type_name="alpha",
        is_class=True,
        is_instance=False,
        class_type_group="shared-group",
    )
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="B",
        type_name="beta",
        is_class=True,
        is_instance=False,
        class_type_group="shared-group",
    )

    found = ontology_store.find_ontology_type(
        memory_conn,
        "acme",
        group="shared-group",
        data_type="class_type_group",
        type_name="beta",
    )

    assert found["kg_type_name"] == "B"


def test_list_ontology_types_includes_universal_and_namespace(memory_conn):
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace=ontology_store.UNIVERSAL_NAMESPACE,
        kg_type_name="U",
        type_name="universal-type",
        is_class=True,
        is_instance=False,
    )
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="acme",
        kg_type_name="T",
        type_name="tenant-type",
        is_class=True,
        is_instance=False,
    )
    ontology_store.upsert_ontology_type(
        memory_conn,
        namespace="other-tenant",
        kg_type_name="O",
        type_name="other-tenant-type",
        is_class=True,
        is_instance=False,
    )

    listed = {
        t["kg_type_name"]
        for t in ontology_store.list_ontology_types(memory_conn, "acme")
    }

    assert listed == {"U", "T"}


def test_upsert_and_get_node_properties(memory_conn):
    ontology_store.upsert_node_properties(
        memory_conn,
        "acme",
        "node-1",
        src_name="Storage Capacity",
        contains="attributes",
        multiplier=1000.0,
        shorthands=["GB", "gb"],
    )

    props = ontology_store.get_node_properties(memory_conn, "acme", "node-1")

    assert props["src_name"] == "Storage Capacity"
    assert props["contains"] == "attributes"
    assert props["multiplier"] == 1000.0
    assert props["shorthands"] == ["GB", "gb"]


def test_upsert_node_properties_merges_partial_updates(memory_conn):
    ontology_store.upsert_node_properties(
        memory_conn, "acme", "node-1", src_name="Storage Capacity"
    )
    ontology_store.upsert_node_properties(
        memory_conn, "acme", "node-1", multiplier=1000.0
    )

    props = ontology_store.get_node_properties(memory_conn, "acme", "node-1")

    assert props["src_name"] == "Storage Capacity"
    assert props["multiplier"] == 1000.0


def test_get_node_properties_falls_back_to_universal(memory_conn):
    ontology_store.upsert_node_properties(
        memory_conn,
        ontology_store.UNIVERSAL_NAMESPACE,
        "node-1",
        src_name="Shared Definition",
    )

    props = ontology_store.get_node_properties(memory_conn, "acme", "node-1")

    assert props["src_name"] == "Shared Definition"


def test_get_node_properties_without_fallback_only_sees_exact_namespace(memory_conn):
    ontology_store.upsert_node_properties(
        memory_conn,
        ontology_store.UNIVERSAL_NAMESPACE,
        "node-1",
        src_name="Shared Definition",
    )

    props = ontology_store.get_node_properties(
        memory_conn, "acme", "node-1", fallback=False
    )

    assert props is None


def test_upsert_node_properties_rejects_unknown_field(memory_conn):
    import pytest

    with pytest.raises(ValueError):
        ontology_store.upsert_node_properties(
            memory_conn, "acme", "node-1", not_a_real_column="x"
        )
