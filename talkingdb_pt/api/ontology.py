from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from talkingdb_pt.api.dependencies import get_ontology_bundle
from talkingdb_pt.services.kg.store import OntologyBundle
from talkingdb_pt.services.ontology.trainer import (
    OntologyTrainerError,
    add_data_to_kg,
    add_type_to_ontology,
    get_nodes_number_trained,
    view_ontology_types,
)

router = APIRouter(
    prefix="/api/namespaces/{namespace}/ontology",
    tags=["Ontology"],
)


class OntologyTypeRequest(BaseModel):
    type_name: str = Field(..., description="Human-readable name for this type.")
    create_class: bool = Field(
        False, description="Whether this registers a class (grouping) type."
    )
    create_instance: bool = Field(
        False, description="Whether this registers an instance type."
    )
    extra_attrs: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Additional attribute definitions beyond the built-in ones. "
            "Give an attribute value_type='REF' (single-valued) or "
            "'[REF]' (multi-valued) to declare it as a graph edge rather "
            "than a scalar property - e.g. "
            '{"has_attributes": {"value_type": "[REF]"}}.'
        ),
    )
    relationship_triples: list[list[str]] = Field(
        default_factory=list,
        description=(
            "[predicate, target_type_name] pairs describing this type's "
            "schema-level relationships to other types. Descriptive only - "
            "not enforced at write time."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "metadata.class_type / metadata.instance_type group this type "
            "for lookup by group name at write time (see /data)."
        ),
    )


class OntologyTypeResponse(BaseModel):
    kg_type_name: str
    status: str = "registered"


class OntologyDataWriteResponse(BaseModel):
    node_ids: list[str]


class OntologyDataCountResponse(BaseModel):
    namespace: str
    nodes_trained: int


@router.post("/types", response_model=OntologyTypeResponse)
async def register_ontology_type(
    namespace: str,
    request: OntologyTypeRequest,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> OntologyTypeResponse:
    kg_type_name = add_type_to_ontology(
        bundle.entity_conn,
        namespace=namespace,
        type_name=request.type_name,
        create_class=request.create_class,
        create_instance=request.create_instance,
        extra_attrs=request.extra_attrs,
        relationship_triples=request.relationship_triples,
        metadata=request.metadata,
    )

    return OntologyTypeResponse(kg_type_name=kg_type_name)


@router.get("/types")
async def list_ontology_types(
    namespace: str,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> list[dict]:
    return view_ontology_types(bundle.entity_conn, namespace)


@router.post("/data", response_model=OntologyDataWriteResponse)
async def write_ontology_data(
    namespace: str,
    nodes: list[dict],
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> OntologyDataWriteResponse:
    try:
        node_ids = add_data_to_kg(bundle, nodes)
    except OntologyTrainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return OntologyDataWriteResponse(node_ids=node_ids)


@router.get("/data", response_model=OntologyDataCountResponse)
async def count_ontology_data(
    namespace: str,
    bundle: OntologyBundle = Depends(get_ontology_bundle),
) -> OntologyDataCountResponse:
    return OntologyDataCountResponse(
        namespace=namespace,
        nodes_trained=get_nodes_number_trained(bundle),
    )
