from talkingdb_pt.model.nl import NLAttribute
from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.parsing.attrs_unifier import filter_attributes


def test_filter_attributes_keeps_only_registered_attrs(bundle):
    upsert_node(bundle, "smartphone", label="Category")
    upsert_node(bundle, "color", label="AttributeClass")
    upsert_edge(bundle, "smartphone", "has_attributes", "color")

    attrs = [NLAttribute(name="color"), NLAttribute(name="weight")]

    result = filter_attributes(bundle, "smartphone", attrs)

    assert [a.name for a in result] == ["color"]


def test_filter_attributes_no_registered_attrs_returns_empty(bundle):
    upsert_node(bundle, "smartphone", label="Category")

    result = filter_attributes(bundle, "smartphone", [NLAttribute(name="color")])

    assert result == []


def test_filter_attributes_works_with_plain_dicts_too(bundle):
    upsert_node(bundle, "smartphone", label="Category")
    upsert_node(bundle, "color", label="AttributeClass")
    upsert_edge(bundle, "smartphone", "has_attributes", "color")

    result = filter_attributes(
        bundle, "smartphone", [{"name": "color"}, {"name": "weight"}]
    )

    assert result == [{"name": "color"}]
