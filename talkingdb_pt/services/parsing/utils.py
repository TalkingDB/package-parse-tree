def attr_sort_order(comparator: dict) -> str | None:
    """Sort direction implied by a comparator, for numeric range attributes
    (e.g. ">=", "<"). Reference-type comparators like "uid_in" have no
    natural sort order and fall through to None - ported as-is, this is
    the exact legacy behavior (the object-attrs call site always passes
    a dict here, never one of the string names below, so it always
    returns None there; kept generic for reuse by literal attribute
    handling)."""

    if comparator in ("ge", "gt"):
        return "orderasc"
    if comparator in ("le", "lt"):
        return "orderdesc"
    return None
