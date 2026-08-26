import pytest

from talkingdb_pt.services.kg.query import (
    list_entity_synonyms,
    run_filter_query,
    run_multiple_filter_queries,
)
from talkingdb_pt.services.kg.store import upsert_edge, upsert_node


def build_products(bundle):
    upsert_node(bundle, "smartphone", label="Category")
    upsert_node(bundle, "laptop", label="Category")

    upsert_node(
        bundle,
        "iphone-15",
        label="Instance",
        surface_texts=["iPhone 15", "iPhone15"],
        scalar_props={"src_name": "iPhone 15", "range_min": 500},
    )
    upsert_edge(bundle, "iphone-15", "instance_of", "smartphone")

    upsert_node(
        bundle,
        "pixel-9",
        label="Instance",
        scalar_props={"src_name": "Pixel 9", "range_min": 700},
    )
    upsert_edge(bundle, "pixel-9", "instance_of", "smartphone")

    upsert_node(
        bundle,
        "thinkpad",
        label="Instance",
        scalar_props={"src_name": "ThinkPad", "range_min": 1000},
    )
    upsert_edge(bundle, "thinkpad", "instance_of", "laptop")


def test_run_filter_query_base_excludes_non_instances(bundle):
    build_products(bundle)
    upsert_node(bundle, "not-an-instance", label="Category")  # no instance_of edge

    results = run_filter_query(bundle)

    ids = {r["node_id"] for r in results}
    assert ids == {"iphone-15", "pixel-9", "thinkpad"}


def test_run_filter_query_filters_by_instance_of(bundle):
    build_products(bundle)

    results = run_filter_query(
        bundle, filters=[{"field": "instance_of", "value": "smartphone"}]
    )

    ids = {r["node_id"] for r in results}
    assert ids == {"iphone-15", "pixel-9"}


def test_run_filter_query_filters_by_scalar_comparator(bundle):
    build_products(bundle)

    results = run_filter_query(
        bundle,
        filters=[
            {"field": "instance_of", "value": "smartphone"},
            {"field": "range_min", "op": "ge", "value": 600},
        ],
    )

    ids = {r["node_id"] for r in results}
    assert ids == {"pixel-9"}


def test_run_filter_query_sorts_ascending_and_descending(bundle):
    build_products(bundle)

    asc = run_filter_query(bundle, sorters=[{"field": "range_min", "direction": "asc"}])
    desc = run_filter_query(
        bundle, sorters=[{"field": "range_min", "direction": "desc"}]
    )

    assert [r["node_id"] for r in asc] == ["iphone-15", "pixel-9", "thinkpad"]
    assert [r["node_id"] for r in desc] == ["thinkpad", "pixel-9", "iphone-15"]


def test_run_filter_query_respects_limit_and_offset(bundle):
    build_products(bundle)

    page = run_filter_query(
        bundle, sorters=[{"field": "range_min", "direction": "asc"}], limit=1, offset=1
    )

    assert [r["node_id"] for r in page] == ["pixel-9"]


def test_run_filter_query_projects_requested_fields_only(bundle):
    build_products(bundle)

    results = run_filter_query(
        bundle,
        filters=[{"field": "instance_of", "value": "smartphone"}],
        fields=["src_name"],
    )

    assert all(
        set(r.keys()) == {"node_id", "label", "surface_texts", "src_name"}
        for r in results
    )


def test_run_filter_query_rejects_non_positive_limit(bundle):
    with pytest.raises(ValueError):
        run_filter_query(bundle, limit=0)


def test_run_multiple_filter_queries_returns_per_query_results(bundle):
    build_products(bundle)

    queries = [
        {"filters": [{"field": "instance_of", "value": "smartphone"}]},
        {"filters": [{"field": "instance_of", "value": "laptop"}]},
    ]

    output = run_multiple_filter_queries(bundle, queries)

    assert len(output) == 2
    assert {r["node_id"] for r in output[0]["results"]} == {"iphone-15", "pixel-9"}
    assert {r["node_id"] for r in output[1]["results"]} == {"thinkpad"}
    assert output[0]["filter"] == queries[0]


def test_list_entity_synonyms_returns_surface_texts(bundle):
    build_products(bundle)

    results = list_entity_synonyms(bundle, limit=10)

    entry = next(r for r in results if r["node_id"] == "iphone-15")
    assert set(entry["alternate_names"]) == {"iPhone 15", "iPhone15"}


def test_list_entity_synonyms_respects_limit(bundle):
    build_products(bundle)

    results = list_entity_synonyms(bundle, limit=1)

    assert len(results) == 1
