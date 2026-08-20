from talkingdb_pt.services.parsing.utils import attr_sort_order, return_num


def test_return_num_parses_plain_int():
    assert return_num("128") == [128, "int"]


def test_return_num_parses_int_with_unit_suffix():
    assert return_num("128GB") == [128, "int"]


def test_return_num_parses_float():
    assert return_num("3.5") == [3.5, "float"]


def test_return_num_no_digits_returns_empty_list():
    assert return_num("abc") == []


def test_attr_sort_order_ascending_for_ge_gt():
    assert attr_sort_order("ge") == "orderasc"
    assert attr_sort_order("gt") == "orderasc"


def test_attr_sort_order_descending_for_le_lt():
    assert attr_sort_order("le") == "orderdesc"
    assert attr_sort_order("lt") == "orderdesc"


def test_attr_sort_order_none_for_reference_comparator():
    assert attr_sort_order({"name": "uid_in"}) is None
