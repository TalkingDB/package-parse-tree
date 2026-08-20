from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.parsing.category import add_classes_to_ctg, category_query_similarity


def ner_entry(entity_id, location, surface_text=None):
    return {
        "location": location,
        "surface_text": surface_text or entity_id,
        "entity_id": entity_id,
    }


def test_single_category_resolved_for_instance(bundle):
    upsert_node(bundle, "smartphone", label="Category", scalar_props={"contains": "instances"})
    upsert_node(bundle, "iphone-15", label="Instance")
    upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")

    ner_output = {"iphone-15&&0&&2": ner_entry("iphone-15", [0, 2])}

    table = add_classes_to_ctg(bundle, ner_output)

    assert len(table) == 1
    # "instance" carries the resolved entity_id (legacy's kg_name_id role,
    # collapsed into entity_id by this port's node_id==src_id simplification),
    # not the composite ner_output dict key.
    assert table[0]["instance"] == "iphone-15"
    assert table[0]["category"] == "smartphone"
    assert table[0]["category_id"] == "smartphone"


def test_bare_category_mention_without_instance(bundle):
    upsert_node(bundle, "electronics", label="Category", scalar_props={"contains": "instances", "src_name": "Electronics"})

    ner_output = {"electronics&&0&&3": ner_entry("electronics", [0, 3])}

    table = add_classes_to_ctg(bundle, ner_output)

    assert len(table) == 1
    assert table[0]["instance"] == "*"
    assert table[0]["category"] == "electronics"
    assert table[0]["category_src_name"] == "Electronics"


def test_multiple_categories_resolved_by_exact_mention(bundle):
    upsert_node(bundle, "smartphone", label="Category", scalar_props={"contains": "instances"})
    upsert_node(bundle, "gift-item", label="Category", scalar_props={"contains": "instances"})
    upsert_node(bundle, "iphone-15", label="Instance")
    upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")
    upsert_edge(bundle, "iphone-15", "instance_of", "gift-item")

    # Query: "smartphone iphone 15" - category mentioned right before instance
    ner_output = {
        "smartphone&&0&&10": ner_entry("smartphone", [0, 10]),
        "iphone-15&&11&&20": ner_entry("iphone-15", [11, 20]),
    }

    table = add_classes_to_ctg(bundle, ner_output)

    instance_row = next(r for r in table if r["instance"] != "*")
    assert instance_row["category"] == "smartphone"


def test_multiple_categories_resolved_by_common_ancestor(bundle):
    upsert_node(bundle, "electronics", label="Category")
    upsert_node(bundle, "smartphone", label="Category", scalar_props={"contains": "instances"})
    upsert_node(bundle, "gift-item", label="Category", scalar_props={"contains": "instances"})
    upsert_edge(bundle, "smartphone", "subclass_of", "electronics")
    upsert_edge(bundle, "gift-item", "subclass_of", "electronics")
    upsert_node(bundle, "iphone-15", label="Instance")
    upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")
    upsert_edge(bundle, "iphone-15", "instance_of", "gift-item")

    # No nearby category mention this time
    ner_output = {"iphone-15&&0&&9": ner_entry("iphone-15", [0, 9])}

    table = add_classes_to_ctg(bundle, ner_output)

    assert len(table) == 1
    assert table[0]["category"] == "electronics"


def test_unresolvable_entity_is_skipped(bundle):
    ner_output = {"99&&0&&2": ner_entry("99", [0, 2])}

    table = add_classes_to_ctg(bundle, ner_output)

    assert table == []


def test_category_query_similarity_lcs():
    # "smart-phone" -> "smart phone" (dash becomes space) before comparing,
    # so the longest contiguous match against "a smartphone store" is
    # "smart" or "phone" (5 chars) - the space breaks the full-word match.
    assert category_query_similarity("smart-phone", "a smartphone store", 11, 18) == 5
    assert category_query_similarity("shoes", "xyz", 5, 3) == 0
