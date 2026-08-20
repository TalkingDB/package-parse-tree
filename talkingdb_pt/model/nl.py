from typing import Any, List, Optional

from pydantic import BaseModel, Field


class NLEntity(BaseModel):
    loc: Optional[List[int]] = None
    uri: Any = None
    name: Any = None
    src_name: Any = None
    surface_text: Optional[str] = None
    source: str = "kg"


class NLAttributeUnit(BaseModel):
    name: Any = None
    uri: Any = None
    surface_text: Any = None
    loc: Any = None


class NLAttributeComparator(NLEntity):
    pass


class NLAttributeValue(NLEntity):
    comparator: Optional[NLAttributeComparator] = None
    sort_order: Any = None


class NLAttribute(NLEntity):
    unit: Optional[NLAttributeUnit] = None
    values: List[NLAttributeValue] = Field(default_factory=list)


class NLInstance(NLEntity):
    attributes: List[NLAttribute] = Field(default_factory=list)


class NLCategory(NLEntity):
    score: int = 0
    instances: List[NLInstance] = Field(default_factory=list)
    attributes: List[NLAttribute] = Field(default_factory=list)


class ExtractGroups(BaseModel):
    groups: List[NLCategory] = Field(default_factory=list)


class NLOutput(BaseModel):
    parse_tree_output: ExtractGroups
    no_tag_entities: List[dict]
    entities_extracted: dict
    search_weight: int
    total_tokens: int
