from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.parsing.literal import add_literals_to_aft, handle_numerical_surface_texts
from talkingdb_pt.services.parsing.literal_maps import build_literal_maps


def ner_entry(entity_id, location, surface_text=None):
    return {
        "location": location,
        "surface_text": surface_text or entity_id,
        "entity_id": entity_id,
    }


def build_storage_ontology(bundle):
    upsert_node(bundle, "storage", label="Class_Type_Literal_Attribute")
    upsert_node(
        bundle,
        "storage_capacity",
        label="Instance_Type_Storage_Capacity",
        scalar_props={"pt_prec": 1, "range_min": 0, "range_max": 10000},
    )
    upsert_edge(bundle, "storage_capacity", "instance_of", "storage")
    upsert_edge(bundle, "storage_capacity", "default_unit", "gb")
    upsert_node(bundle, "gb", label="Instance", scalar_props={"shorthands": ["GB"], "multiplier": None})
    upsert_edge(bundle, "storage", "has_units", "gb")

    upsert_node(bundle, "unit", label="Class")  # universal "unit" marker
    upsert_edge(bundle, "gb", "instance_of", "unit")

    smartphone_category = "smartphone"
    upsert_node(bundle, smartphone_category, label="Category")
    upsert_edge(bundle, smartphone_category, "has_attributes", "storage_capacity")


def test_handle_numerical_surface_texts_plain_number(bundle):
    build_storage_ontology(bundle)
    maps = build_literal_maps(bundle)

    result = handle_numerical_surface_texts(maps, "500")

    assert result == {"value": 500, "symbol": None, "value_type": "int"}


def test_handle_numerical_surface_texts_detects_symbol(bundle):
    build_storage_ontology(bundle)
    maps = build_literal_maps(bundle)

    result = handle_numerical_surface_texts(maps, "128gb")

    assert result["value"] == 128
    assert result["symbol"] == "gb"


def test_add_literals_to_aft_single_literal_by_range(bundle):
    build_storage_ontology(bundle)

    ner_output = {"number_patterns&&0&&3": ner_entry("number_patterns", [0, 3], "500")}

    aft = add_literals_to_aft(bundle, ner_output)

    assert len(aft) == 1
    row = aft[0]
    assert row["attr_name"] == "storage_capacity"
    assert row["attr_value"] == 500
    assert row["comparator"]["name"] == "eq"
    assert row["attr_name_kg_id"] == "smartphone"


def test_add_literals_to_aft_resolves_via_unit_symbol(bundle):
    build_storage_ontology(bundle)
    # A second element sharing the same numeric range would create
    # ambiguity resolved only by the unit symbol - add a "weight" element
    # with an overlapping range but a different unit to force disambiguation.
    upsert_node(bundle, "weight", label="Class_Type_Literal_Attribute")
    upsert_node(
        bundle, "item_weight", label="Instance_Type_Item_Weight",
        scalar_props={"pt_prec": 1, "range_min": 0, "range_max": 10000},
    )
    upsert_edge(bundle, "item_weight", "instance_of", "weight")
    upsert_edge(bundle, "item_weight", "default_unit", "kg")
    upsert_node(bundle, "kg", label="Instance", scalar_props={"shorthands": ["kg"], "multiplier": None})
    upsert_edge(bundle, "weight", "has_units", "kg")
    upsert_edge(bundle, "kg", "instance_of", "unit")

    ner_output = {"number_patterns&&0&&5": ner_entry("number_patterns", [0, 5], "128gb")}

    aft = add_literals_to_aft(bundle, ner_output)

    assert len(aft) == 1
    assert aft[0]["attr_name"] == "storage_capacity"
    assert aft[0]["attr_value"] == 128


def test_add_literals_to_aft_associates_comparator(bundle):
    build_storage_ontology(bundle)
    upsert_node(bundle, "comparator", label="Class")
    upsert_node(bundle, "ge", label="Instance_Type_Ge")
    upsert_edge(bundle, "ge", "instance_of", "comparator")

    ner_output = {
        "ge&&0&&5": ner_entry("ge", [0, 5], "above"),
        "number_patterns&&6&&9": ner_entry("number_patterns", [6, 9], "500"),
    }

    aft = add_literals_to_aft(bundle, ner_output)

    assert len(aft) == 1
    assert aft[0]["comparator"]["name"] == "ge"
    assert aft[0]["comparator"]["surface_text"] == "above"


def test_add_literals_to_aft_unresolvable_number_with_no_kg_match_produces_no_row(bundle):
    # No ontology registered at all - the number can't be resolved to any
    # literal attribute, so no row should be produced despite parsing fine.
    ner_output = {"number_patterns&&0&&3": ner_entry("number_patterns", [0, 3], "999999")}

    aft = add_literals_to_aft(bundle, ner_output)

    assert aft == []
