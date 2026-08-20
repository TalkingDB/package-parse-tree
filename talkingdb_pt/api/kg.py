from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from talkingdb_pt.api.dependencies import get_ontology_bundle
from talkingdb_pt.services.kg.query import (
    list_entity_synonyms,
    run_filter_query,
    run_multiple_filter_queries,
)
from talkingdb_pt.services.kg.store import OntologyBundle, node_properties

router = APIRouter(
    prefix="/api/namespaces/{namespace}/kg",
    tags=["Knowledge Graph"],
)


class KGFilterClause(BaseModel):
    field: str = Field(
        ..., description="Scalar ontology property name, or an edge predicate "
        "(instance_of, subclass_of, has_attributes, has_units, default_unit)."
    )
    op: str = Field("eq", description="eq | ge | gt | le | lt | in")
    value: Any


class KGSorter(BaseModel):
    field: str
    direction: str = Field("asc", description="asc | desc")


class KGDataQuery(BaseModel):
    filters: list[KGFilterClause] = Field(default_factory=list)
    sorters: list[KGSorter] = Field(default_factory=list)
    limit: int = 20
    offset: int = 0
    fields: list[str] | None = Field(
        None, description="Scalar fields to include in each result. Omit for the default set."
    )


class KGDataMultipleQuery(BaseModel):
    queries: list[KGDataQuery] = Field(default_factory=list)


class KGEntityPropertiesRequest(BaseModel):
    node_id: str
    properties: list[str]


def _as_kwargs(query: KGDataQuery) -> dict:
    return {
        "filters": [f.model_dump() for f in query.filters],
        "sorters": [s.model_dump() for s in query.sorters],
        "limit": query.limit,
        "offset": query.offset,
        "fields": query.fields,
    }


@router.post("/data")
async def get_kg_data(
    namespace: str,
    query: KGDataQuery,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> list[dict]:
    try:
        return run_filter_query(bundle, **_as_kwargs(query))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/data/filters/multiple")
async def get_kg_data_multiple(
    namespace: str,
    request: KGDataMultipleQuery,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> list[dict]:
    return run_multiple_filter_queries(bundle, [_as_kwargs(q) for q in request.queries])


@router.get("/entities/synonyms")
async def kg_entities_synonyms(
    namespace: str,
    limit: int,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> list[dict]:
    return list_entity_synonyms(bundle, limit)


@router.post("/entities/properties")
async def kg_entities_properties(
    namespace: str,
    request: KGEntityPropertiesRequest,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> dict:
    return node_properties(bundle, request.node_id, request.properties)
