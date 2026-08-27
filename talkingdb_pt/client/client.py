import os
from typing import Any, Optional

import requests
from talkingdb.helpers.client import Config
from talkingdb.models.api.mode import ClientMode


class PTClient:
    """Dual-mode client for package-parse-tree.

    In DIRECT mode (default), calls the same service functions the API
    routers call, in-process - no network, no server needed. In API mode,
    calls a deployed package-parse-tree service over HTTP.

    ``PT_HOST`` is read locally rather than added to base-tdb-helpers'
    shared Config (unlike CE_HOST there), to avoid a cross-repo change for
    a single new client; fold it into the shared Config later if other
    packages want the same env var name convention.
    """

    def __init__(self, config: Optional[Config] = None, headers: Optional[dict] = None):
        config = config or Config()
        self.mode = config.CLIENT_MODE
        self.timeout = config.API_TIMEOUT
        self.endpoint = os.getenv("PT_HOST")
        self.api_key = config.TDB_API_KEY

        self.session: Optional[requests.Session] = None
        if self.mode == ClientMode.API:
            if not self.endpoint:
                raise ValueError("PT_HOST is required in API mode")

            self.session = requests.Session()
            if self.api_key:
                self.session.headers["Authorization"] = f"Bearer {self.api_key}"
            if headers:
                self.session.headers.update(headers)

    # ------------------------------------------------------------ extract
    async def extract_relations(self, namespace: str, user_query: str) -> dict:
        if self.mode == ClientMode.API:
            return self._post(
                f"/api/namespaces/{namespace}/extract/relations",
                {"user_query": user_query},
            )

        from talkingdb_pt.services.kg.store import registry
        from talkingdb_pt.services.parsing.sentence import parse_input

        bundle = registry.get(namespace)
        return await parse_input(bundle, user_query)

    async def extract_entities(
        self, namespace: str, user_query: str, word_correction: bool = False
    ) -> dict:
        if self.mode == ClientMode.API:
            return self._post(
                f"/api/namespaces/{namespace}/extract/entities",
                {"user_query": user_query, "word_correction": word_correction},
            )

        from talkingdb_pt.services.ner.client import extract_and_link

        return await extract_and_link(namespace, user_query, word_correction)

    # ----------------------------------------------------------- ontology
    def register_ontology_type(
        self,
        namespace: str,
        *,
        type_name: str,
        create_class: bool = False,
        create_instance: bool = False,
        extra_attrs: Optional[dict[str, dict[str, Any]]] = None,
        relationship_triples: Optional[list[list[str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        payload = {
            "type_name": type_name,
            "create_class": create_class,
            "create_instance": create_instance,
            "extra_attrs": extra_attrs or {},
            "relationship_triples": relationship_triples or [],
            "metadata": metadata or {},
        }
        if self.mode == ClientMode.API:
            return self._post(f"/api/namespaces/{namespace}/ontology/types", payload)

        from talkingdb_pt.services.kg.store import registry
        from talkingdb_pt.services.ontology.trainer import add_type_to_ontology

        bundle = registry.get(namespace)
        kg_type_name = add_type_to_ontology(
            bundle.entity_conn,
            namespace=namespace,
            type_name=type_name,
            create_class=create_class,
            create_instance=create_instance,
            extra_attrs=extra_attrs or {},
            relationship_triples=relationship_triples or [],
            metadata=metadata or {},
        )
        return {"kg_type_name": kg_type_name, "status": "registered"}

    def list_ontology_types(self, namespace: str) -> list[dict]:
        if self.mode == ClientMode.API:
            return self._get(f"/api/namespaces/{namespace}/ontology/types")

        from talkingdb_pt.services.kg.store import registry
        from talkingdb_pt.services.ontology.trainer import view_ontology_types

        bundle = registry.get(namespace)
        return view_ontology_types(bundle.entity_conn, namespace)

    def upsert_ontology_data(self, namespace: str, nodes: list[dict]) -> list[str]:
        if self.mode == ClientMode.API:
            return self._post(f"/api/namespaces/{namespace}/ontology/data", nodes)[
                "node_ids"
            ]

        from talkingdb_pt.services.kg.store import registry
        from talkingdb_pt.services.ontology.trainer import add_data_to_kg

        bundle = registry.get(namespace)
        return add_data_to_kg(bundle, nodes)

    def count_ontology_data(self, namespace: str) -> int:
        if self.mode == ClientMode.API:
            return self._get(f"/api/namespaces/{namespace}/ontology/data")[
                "nodes_trained"
            ]

        from talkingdb_pt.services.kg.store import registry
        from talkingdb_pt.services.ontology.trainer import get_nodes_number_trained

        bundle = registry.get(namespace)
        return get_nodes_number_trained(bundle)

    # ----------------------------------------------------------------- kg
    def query_kg_data(
        self,
        namespace: str,
        *,
        filters: Optional[list[dict]] = None,
        sorters: Optional[list[dict]] = None,
        limit: int = 20,
        offset: int = 0,
        fields: Optional[list[str]] = None,
    ) -> list[dict]:
        payload = {
            "filters": filters or [],
            "sorters": sorters or [],
            "limit": limit,
            "offset": offset,
            "fields": fields,
        }
        if self.mode == ClientMode.API:
            return self._post(f"/api/namespaces/{namespace}/kg/data", payload)

        from talkingdb_pt.services.kg.query import run_filter_query
        from talkingdb_pt.services.kg.store import registry

        bundle = registry.get(namespace)
        return run_filter_query(
            bundle,
            filters=payload["filters"],
            sorters=payload["sorters"],
            limit=limit,
            offset=offset,
            fields=fields,
        )

    # ------------------------------------------------------------- boundary
    def _post(self, path: str, json_body: Any) -> Any:
        response = self.session.post(
            f"{self.endpoint}{path}", json=json_body, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def _get(self, path: str) -> Any:
        response = self.session.get(f"{self.endpoint}{path}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()
