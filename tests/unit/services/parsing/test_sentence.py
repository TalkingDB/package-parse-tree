from unittest.mock import AsyncMock, patch

import pytest

from talkingdb_pt.services.kg.store import upsert_edge, upsert_node
from talkingdb_pt.services.parsing.sentence import parse_input


def build_smartphone_ontology(bundle):
    upsert_node(bundle, "smartphone", label="Class_Type_Category", scalar_props={"contains": "instances", "src_name": "Smartphone"})
    upsert_node(bundle, "iphone-15", label="Instance_Type_Smartphone")
    upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")

    upsert_node(bundle, "color", label="Class_Type_Attribute", scalar_props={"contains": "attributes"})
    upsert_node(bundle, "red", label="Instance_Type_Color")
    upsert_edge(bundle, "red", "instance_of", "color")
    upsert_edge(bundle, "smartphone", "has_attributes", "color")


def fake_nel_response(universal_entities=None, regex_entities=None, no_tag_entities=None):
    return {
        "universal_entities": universal_entities or [],
        "regex_entities": regex_entities or [],
        "no_tag_entities": no_tag_entities or [],
    }


@pytest.mark.anyio
async def test_parse_input_builds_category_with_instance_and_attribute(bundle):
    build_smartphone_ontology(bundle)

    nel_response = fake_nel_response(
        universal_entities=[
            {
                "index": [0, 9],
                "surface_text": "iphone 15",
                "corrected_text": "iphone 15",
                "score": 0,
                "entities": [{"entity_id": "iphone-15", "label": "Instance", "surface_text": "iphone 15"}],
            },
            {
                "index": [10, 13],
                "surface_text": "red",
                "corrected_text": "red",
                "score": 0,
                "entities": [{"entity_id": "red", "label": "Instance", "surface_text": "red"}],
            },
        ],
    )

    with patch(
        "talkingdb_pt.services.parsing.sentence.extract_and_link",
        new=AsyncMock(return_value=nel_response),
    ):
        result = await parse_input(bundle, "red iphone 15")

    groups = result["parse_tree_output"].groups
    assert len(groups) == 1
    category = groups[0]
    assert category.name == "smartphone"
    assert len(category.instances) == 1

    instance = category.instances[0]
    assert instance.name == "iphone-15"
    assert len(instance.attributes) == 1
    assert instance.attributes[0].name == "color"
    assert instance.attributes[0].values[0].name == "red"


@pytest.mark.anyio
async def test_parse_input_no_categories_falls_back_to_misc_group(bundle):
    upsert_node(bundle, "color", label="Class_Type_Attribute", scalar_props={"contains": "attributes"})
    upsert_node(bundle, "red", label="Instance_Type_Color")
    upsert_edge(bundle, "red", "instance_of", "color")

    nel_response = fake_nel_response(
        universal_entities=[
            {
                "index": [0, 3],
                "surface_text": "red",
                "corrected_text": "red",
                "score": 0,
                "entities": [{"entity_id": "red", "label": "Instance", "surface_text": "red"}],
            }
        ]
    )

    with patch(
        "talkingdb_pt.services.parsing.sentence.extract_and_link",
        new=AsyncMock(return_value=nel_response),
    ):
        result = await parse_input(bundle, "red")

    groups = result["parse_tree_output"].groups
    assert len(groups) == 1
    assert groups[0].name is None
    assert groups[0].attributes[0].name == "color"


@pytest.mark.anyio
async def test_parse_input_empty_query_produces_no_groups(bundle):
    nel_response = fake_nel_response()

    with patch(
        "talkingdb_pt.services.parsing.sentence.extract_and_link",
        new=AsyncMock(return_value=nel_response),
    ):
        result = await parse_input(bundle, "hello there")

    assert result["parse_tree_output"].groups == []
    assert result["search_weight"] == 0


@pytest.mark.anyio
async def test_parse_input_counts_total_tokens_excluding_stop_words(bundle):
    nel_response = fake_nel_response(
        no_tag_entities=[
            {"index": [0, 2], "surface_text": "hi"},
            {"index": [3, 5], "surface_text": "is"},  # stop word, excluded
        ]
    )

    with patch(
        "talkingdb_pt.services.parsing.sentence.extract_and_link",
        new=AsyncMock(return_value=nel_response),
    ):
        result = await parse_input(bundle, "hi is")

    assert result["total_tokens"] == 1
