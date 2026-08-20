from talkingdb_pt.services.kg.store import OntologyBundle
from talkingdb_pt.services.kg.store import registry as ontology_registry


def get_ontology_bundle(namespace: str) -> OntologyBundle:
    return ontology_registry.get(namespace)
