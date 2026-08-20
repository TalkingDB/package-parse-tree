from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from talkingdb_pt.api.dependencies import get_ontology_bundle
from talkingdb_pt.services.kg.store import OntologyBundle
from talkingdb_pt.services.ner.trainer import (
    EntityNotInOntologyError,
    add_synonyms,
    add_synonyms_batch,
    export_synonyms_csv,
    remove_synonyms,
    train_all_entities,
)

router = APIRouter(
    prefix="/api/namespaces/{namespace}/ner",
    tags=["NER Training"],
)


class SynonymsRequest(BaseModel):
    src_id: str = Field(..., description="node_id (== src_id) of the entity to update.")
    aliases: list[str]


def _not_found(exc: EntityNotInOntologyError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Entity '{exc}' not found")


@router.post("/train")
async def train_ner(namespace: str, bundle: OntologyBundle = Depends(get_ontology_bundle)) -> dict:
    return await train_all_entities(bundle)


@router.post("/synonyms")
async def create_synonyms(
    namespace: str,
    request: SynonymsRequest,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> dict:
    try:
        return await add_synonyms(bundle, request.src_id, request.aliases)
    except EntityNotInOntologyError as exc:
        raise _not_found(exc) from exc


@router.delete("/synonyms")
async def delete_synonyms(
    namespace: str,
    request: SynonymsRequest,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> dict:
    try:
        return await remove_synonyms(bundle, request.src_id, request.aliases)
    except EntityNotInOntologyError as exc:
        raise _not_found(exc) from exc


@router.get("/synonyms")
async def get_synonyms(namespace: str, bundle: OntologyBundle = Depends(get_ontology_bundle)) -> StreamingResponse:
    csv_text = export_synonyms_csv(bundle)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=synonyms_data.csv"},
    )


@router.post("/synonyms/many")
async def create_synonyms_many(
    namespace: str,
    requests: list[SynonymsRequest],
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> list[dict]:
    try:
        return await add_synonyms_batch(bundle, [r.model_dump() for r in requests])
    except EntityNotInOntologyError as exc:
        raise _not_found(exc) from exc
