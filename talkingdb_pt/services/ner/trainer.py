import csv
import io

from talkingdb_pt.services.kg.store import (
    OntologyBundle,
    node_label,
    node_property,
    save,
    upsert_node,
)
from talkingdb_pt.services.ner.client import (
    NELEntityNotFound,
    add_entity_surface_text,
    get_entity,
    update_entity_surface_texts,
    upsert_entity,
)


class EntityNotInOntologyError(Exception):
    """Raised when a synonym operation targets a node_id that isn't in the ontology."""


def _current_surface_texts(bundle: OntologyBundle, node_id: str) -> list[str]:
    if not bundle.graph.has_node(node_id):
        raise EntityNotInOntologyError(node_id)
    return list(bundle.graph.nodes[node_id].get("surface_texts", []))


async def train_all_entities(bundle: OntologyBundle) -> dict:
    """Push every ontology entity's surface texts into NEL so it can link
    user queries back to these node_ids. Replaces the legacy train_ner,
    which pushed to the retired standalone nl-ner service instead.

    Iterates the composed (universal + namespace) graph, matching the
    legacy ns_list = ["universal", namespace] union."""

    trained = 0
    skipped = 0
    total = 0

    for node_id, attrs in bundle.graph.nodes(data=True):
        total += 1
        shorthands = node_property(bundle, node_id, "shorthands") or []
        aliases = sorted({*attrs.get("surface_texts", []), *shorthands, node_id})

        try:
            await upsert_entity(bundle.namespace, node_id, attrs.get("label", ""), aliases)
            trained += 1
        except Exception:  # noqa: BLE001 - one bad entity must not abort the whole sync
            skipped += 1

    return {
        "total_trainable_entities_in_kg": total,
        "entities_trained": trained,
        "entities_skipped": skipped,
    }


async def add_synonyms(bundle: OntologyBundle, src_id: str, aliases: list[str]) -> dict:
    """node_id == src_id in this port, so there's no Mongo lookup needed to
    resolve one to the other (the legacy version's first step)."""

    current = _current_surface_texts(bundle, src_id)
    merged = sorted({*(a.lower() for a in current), *(a.lower() for a in aliases)})

    upsert_node(bundle, src_id, label=node_label(bundle, src_id), surface_texts=merged)
    save(bundle)

    for alias in aliases:
        await add_entity_surface_text(bundle.namespace, src_id, alias.lower())

    return {"src_id": src_id, "alternate_names": merged}


async def remove_synonyms(bundle: OntologyBundle, src_id: str, aliases: list[str]) -> dict:
    current = _current_surface_texts(bundle, src_id)
    to_remove = {a.lower() for a in aliases}
    updated = sorted({a.lower() for a in current if a.lower() not in to_remove})

    upsert_node(bundle, src_id, label=node_label(bundle, src_id), surface_texts=updated)
    save(bundle)

    try:
        await update_entity_surface_texts(bundle.namespace, src_id, updated)
    except NELEntityNotFound:
        pass  # nothing to reconcile on the NEL side if it was never trained

    return {"src_id": src_id, "alternate_names": updated}


async def add_synonyms_batch(bundle: OntologyBundle, items: list[dict]) -> list[dict]:
    return [await add_synonyms(bundle, item["src_id"], item["aliases"]) for item in items]


def export_synonyms_csv(bundle: OntologyBundle) -> str:
    """CSV export of this namespace's entities and their surface texts.
    Namespace-scoped only (not universal), matching the legacy
    get_synonyms(namespace). Uses the stdlib csv module instead of the
    legacy's pandas dependency - pandas is unnecessary weight for writing
    two columns."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["entity_id", "synonyms"])

    for entity in bundle.tenant.iter_entities():
        writer.writerow([entity["id"], ", ".join(entity["surface_texts"])])

    return buffer.getvalue()
