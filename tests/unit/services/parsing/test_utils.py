from talkingdb_pt.services.parsing.utils import attr_sort_order


def test_attr_sort_order_ascending_for_ge_gt():
    assert attr_sort_order("ge") == "orderasc"
    assert attr_sort_order("gt") == "orderasc"


def test_attr_sort_order_descending_for_le_lt():
    assert attr_sort_order("le") == "orderdesc"
    assert attr_sort_order("lt") == "orderdesc"


def test_attr_sort_order_none_for_reference_comparator():
    assert attr_sort_order({"name": "uid_in"}) is None
