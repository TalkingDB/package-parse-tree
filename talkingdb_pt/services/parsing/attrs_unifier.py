from talkingdb_pt.services.kg.store import OntologyBundle, nodes_with_edge


def filter_attributes(bundle: OntologyBundle, category_id: str, attributes: list[dict]) -> list[dict]:
    """Keep only the attributes that are actually registered on this
    category via a has_attributes edge - filters out attributes the NL
    parser extracted that don't belong to the resolved category."""

    valid_attr_ids = {
        edge["target"]
        for edge in nodes_with_edge(bundle, "has_attributes", source_ids=[category_id])
    }

    return [attr for attr in attributes if attr.get("attr_name") in valid_attr_ids]
