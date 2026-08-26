from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.parsing.object_attrs import add_object_attrs_to_aft


def ner_entry(entity_id, location, surface_text=None):
    return {
        "location": location,
        "surface_text": surface_text or entity_id,
        "entity_id": entity_id,
    }


def test_single_attr_class_resolved_for_value(bundle):
    upsert_node(
        bundle, "color", label="AttributeClass", scalar_props={"contains": "attributes"}
    )
    upsert_node(bundle, "red", label="AttributeValue")
    upsert_edge(bundle, "red", "instance_of", "color")
    upsert_node(bundle, "smartphone", label="Category")
    upsert_edge(bundle, "smartphone", "has_attributes", "color")

    ner_output = {"red&&0&&3": ner_entry("red", [0, 3])}

    aft = add_object_attrs_to_aft(bundle, ner_output)

    assert len(aft) == 1
    row = aft[0]
    assert row["attr_name"] == "color"
    assert row["attr_value"] == "red"
    assert row["attr_value_surface_text"] == "red"
    assert row["attr_name_kg_id"] == "smartphone"
    assert row["sort_order"] is None


def test_no_attr_class_produces_no_rows(bundle):
    upsert_node(bundle, "smartphone", label="Category")

    ner_output = {"smartphone&&0&&10": ner_entry("smartphone", [0, 10])}

    aft = add_object_attrs_to_aft(bundle, ner_output)

    assert aft == []


def test_unresolvable_entity_produces_no_rows(bundle):
    ner_output = {"99&&0&&2": ner_entry("99", [0, 2])}

    aft = add_object_attrs_to_aft(bundle, ner_output)

    assert aft == []


def test_multiple_attr_classes_without_exact_mention_includes_all(bundle):
    upsert_node(
        bundle, "color", label="AttributeClass", scalar_props={"contains": "attributes"}
    )
    upsert_node(
        bundle,
        "finish",
        label="AttributeClass",
        scalar_props={"contains": "attributes"},
    )
    upsert_node(bundle, "matte", label="AttributeValue")
    upsert_edge(bundle, "matte", "instance_of", "color")
    upsert_edge(bundle, "matte", "instance_of", "finish")

    ner_output = {"matte&&0&&5": ner_entry("matte", [0, 5])}

    aft = add_object_attrs_to_aft(bundle, ner_output)

    assert {row["attr_name"] for row in aft} == {"color", "finish"}
