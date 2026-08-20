from unittest.mock import AsyncMock, patch

import pytest

from talkingdb_pt.services.kg.store import upsert_node
from talkingdb_pt.services.ner.trainer import (
    EntityNotInOntologyError,
    add_synonyms,
    add_synonyms_batch,
    export_synonyms_csv,
    remove_synonyms,
    train_all_entities,
)


@pytest.mark.anyio
async def test_train_all_entities_counts_and_upserts(bundle):
    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15"])
    upsert_node(bundle, "smartphone", label="Category")

    with patch(
        "talkingdb_pt.services.ner.trainer.upsert_entity", new=AsyncMock(return_value={})
    ) as mocked:
        result = await train_all_entities(bundle)

    assert result == {
        "total_trainable_entities_in_kg": 2,
        "entities_trained": 2,
        "entities_skipped": 0,
    }
    assert mocked.await_count == 2


@pytest.mark.anyio
async def test_train_all_entities_counts_failures_as_skipped(bundle):
    upsert_node(bundle, "iphone-15", label="Instance")

    with patch(
        "talkingdb_pt.services.ner.trainer.upsert_entity",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await train_all_entities(bundle)

    assert result["entities_skipped"] == 1
    assert result["entities_trained"] == 0


@pytest.mark.anyio
async def test_add_synonyms_merges_and_lowercases(bundle):
    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15"])

    with patch(
        "talkingdb_pt.services.ner.trainer.add_entity_surface_text", new=AsyncMock()
    ) as mocked:
        result = await add_synonyms(bundle, "iphone-15", ["iPhone15", "APPLE PHONE"])

    assert result == {
        "src_id": "iphone-15",
        "alternate_names": ["apple phone", "iphone 15", "iphone15"],
    }
    assert mocked.await_count == 2


@pytest.mark.anyio
async def test_add_synonyms_unknown_entity_raises(bundle):
    with pytest.raises(EntityNotInOntologyError):
        await add_synonyms(bundle, "does-not-exist", ["x"])


@pytest.mark.anyio
async def test_remove_synonyms_removes_matching_aliases(bundle):
    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15", "iPhone15"])

    with patch(
        "talkingdb_pt.services.ner.trainer.update_entity_surface_texts", new=AsyncMock()
    ) as mocked:
        result = await remove_synonyms(bundle, "iphone-15", ["iPhone15"])

    assert result == {"src_id": "iphone-15", "alternate_names": ["iphone 15"]}
    mocked.assert_awaited_once_with("acme", "iphone-15", ["iphone 15"])


@pytest.mark.anyio
async def test_remove_synonyms_tolerates_entity_missing_on_nel_side(bundle):
    from talkingdb_pt.services.ner.client import NELEntityNotFound

    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15"])

    with patch(
        "talkingdb_pt.services.ner.trainer.update_entity_surface_texts",
        new=AsyncMock(side_effect=NELEntityNotFound("iphone-15")),
    ):
        result = await remove_synonyms(bundle, "iphone-15", ["iPhone 15"])

    assert result == {"src_id": "iphone-15", "alternate_names": []}


@pytest.mark.anyio
async def test_add_synonyms_batch_processes_each_item(bundle):
    upsert_node(bundle, "a", label="Instance")
    upsert_node(bundle, "b", label="Instance")

    with patch("talkingdb_pt.services.ner.trainer.add_entity_surface_text", new=AsyncMock()):
        results = await add_synonyms_batch(
            bundle, [{"src_id": "a", "aliases": ["x"]}, {"src_id": "b", "aliases": ["y"]}]
        )

    assert [r["src_id"] for r in results] == ["a", "b"]


def test_export_synonyms_csv_lists_namespace_entities(bundle):
    upsert_node(bundle, "iphone-15", label="Instance", surface_texts=["iPhone 15", "iPhone15"])

    csv_text = export_synonyms_csv(bundle)

    assert "entity_id,synonyms" in csv_text
    assert "iphone-15" in csv_text
    assert "iPhone 15" in csv_text
