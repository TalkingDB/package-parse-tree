from talkingdb_pt.services.kg.store import save, upsert_edge, upsert_node
from talkingdb_pt.services.parsing.literal_maps import (
    build_literal_maps,
    get_literal_maps,
)


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
    upsert_node(
        bundle,
        "gb",
        label="Instance",
        surface_texts=["gigabyte"],
        scalar_props={"shorthands": ["GB", "gb"], "multiplier": None},
    )
    upsert_edge(bundle, "storage", "has_units", "gb")


def test_ele_lit_map_groups_literals_under_element(bundle):
    build_storage_ontology(bundle)

    maps = build_literal_maps(bundle)

    assert "storage" in maps.ele_lit_map
    literals = maps.ele_lit_map["storage"]["literals"]
    assert literals["storage_capacity"]["pt_prec"] == 1
    assert literals["storage_capacity"]["default_unit"] == "gb"


def test_unit_ele_map_maps_unit_to_elements_and_aliases(bundle):
    build_storage_ontology(bundle)

    maps = build_literal_maps(bundle)

    assert maps.unit_ele_map["gb"]["elements"] == ["storage"]
    assert "gb" in maps.unit_ele_map["gb"]["aliases"]
    assert "gigabyte" in maps.unit_ele_map["gb"]["aliases"]


def test_lit_range_map_captures_range_and_precision(bundle):
    build_storage_ontology(bundle)

    maps = build_literal_maps(bundle)

    assert maps.lit_range_map["storage_capacity"] == {"range": (0, 10000), "pt_prec": 1}


def test_symbol_map_indexes_shorthands_lowercased(bundle):
    build_storage_ontology(bundle)

    maps = build_literal_maps(bundle)

    assert maps.symbol_map["gb"]["symbol_for"] == "gb"
    assert maps.symbol_map["gb"]["multiplier"] is None


def test_dim_conj_empty_when_no_conjunction_registered(bundle):
    maps = build_literal_maps(bundle)

    assert maps.dim_conj == []


def test_dim_conj_picks_up_registered_conjunction(bundle):
    upsert_node(
        bundle, "x", label="Instance_Type_Dimension_Conjunction", surface_texts=["by"]
    )

    maps = build_literal_maps(bundle)

    assert maps.dim_conj == ["x", "by"]


def test_get_literal_maps_is_cached_until_save(bundle):
    build_storage_ontology(bundle)

    first = get_literal_maps(bundle)
    second = get_literal_maps(bundle)
    assert first is second

    save(bundle)
    third = get_literal_maps(bundle)
    assert third is not first
