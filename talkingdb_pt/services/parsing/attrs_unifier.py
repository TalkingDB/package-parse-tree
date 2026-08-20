from talkingdb_pt.services.kg.store import OntologyBundle, nodes_with_edge


def filter_attributes(bundle: OntologyBundle, category_id: str, attributes: list) -> list:
    """Keep only the attributes that are actually registered on this
    category via a has_attributes edge - filters out attributes the NL
    parser extracted that don't belong to the resolved category.

    `attributes` is a list of NLAttribute (or any object/mapping exposing
    a `.name`/`["name"]` attribute-name field) - the real call site is
    sentence.parse_input filtering an NLCategory's `.attributes`."""

    valid_attr_ids = {
        edge["target"]
        for edge in nodes_with_edge(bundle, "has_attributes", source_ids=[category_id])
    }

    def attr_name(attr):
        return attr.name if hasattr(attr, "name") else attr.get("name")

    return [attr for attr in attributes if attr_name(attr) in valid_attr_ids]
