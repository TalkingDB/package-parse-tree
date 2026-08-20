from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.parsing.attrs_unifier import filter_attributes


def test_filter_attributes_keeps_only_registered_attrs(bundle):
    upsert_node(bundle, "smartphone", label="Category")
    upsert_node(bundle, "color", label="AttributeClass")
    upsert_edge(bundle, "smartphone", "has_attributes", "color")

    attrs = [{"attr_name": "color"}, {"attr_name": "weight"}]

    result = filter_attributes(bundle, "smartphone", attrs)

    assert result == [{"attr_name": "color"}]


def test_filter_attributes_no_registered_attrs_returns_empty(bundle):
    upsert_node(bundle, "smartphone", label="Category")

    result = filter_attributes(bundle, "smartphone", [{"attr_name": "color"}])

    assert result == []
