import re


def create_kg_friendly_entity_name(name: str) -> str:
    """Split on whitespace/tabs/underscores/dashes, title-case each part,
    strip non-word characters, and join back with underscores."""

    parts = re.split(r"[\s\t_-]+", name)
    joined = "_".join(part.capitalize() for part in parts)
    joined = "".join(re.findall(r"[\w]+", joined))
    return "_".join(part.capitalize() for part in joined.split("_"))


def class_type_name(name: str) -> str:
    return create_kg_friendly_entity_name(f"Class_Type_{name.capitalize()}")


def instance_type_name(name: str) -> str:
    return create_kg_friendly_entity_name(f"Instance_Type_{name.capitalize()}")
