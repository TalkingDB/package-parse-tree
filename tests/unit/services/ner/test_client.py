from talkingdb_pt.services.ner.client import build_ner_ids, filter_overlapping_regex


def test_filter_overlapping_regex_drops_overlapping_match():
    universal = [{"index": [0, 5], "surface_text": "apple"}]
    regex = [
        {"index": [2, 4], "surface_text": "pl", "rule": "some-rule"},
        {"index": [10, 12], "surface_text": "99", "rule": "number-rule"},
    ]

    result = filter_overlapping_regex(universal, regex)

    assert [e["rule"] for e in result] == ["number-rule"]


def test_filter_overlapping_regex_keeps_non_overlapping():
    universal = [{"index": [0, 5], "surface_text": "apple"}]
    regex = [{"index": [6, 8], "surface_text": "is", "rule": "some-rule"}]

    result = filter_overlapping_regex(universal, regex)

    assert result == regex


def test_build_ner_ids_from_universal_entities():
    response = {
        "universal_entities": [
            {
                "index": [0, 5],
                "surface_text": "apple",
                "corrected_text": "apple",
                "score": 0,
                "entities": [{"entity_id": "fruit-apple", "label": "Fruit", "surface_text": "apple"}],
            }
        ],
        "regex_entities": [],
        "no_tag_entities": [],
    }

    ner_ids = build_ner_ids(response)

    assert ner_ids == {
        "fruit-apple&&0&&5": {
            "location": [0, 5],
            "surface_text": "apple",
            "entity_id": "fruit-apple",
        }
    }


def test_build_ner_ids_fans_out_multiple_entities_per_span():
    response = {
        "universal_entities": [
            {
                "index": [0, 5],
                "surface_text": "apple",
                "corrected_text": "apple",
                "score": 0,
                "entities": [
                    {"entity_id": "fruit-apple", "label": "Fruit", "surface_text": "apple"},
                    {"entity_id": "company-apple", "label": "Company", "surface_text": "apple"},
                ],
            }
        ],
        "regex_entities": [],
        "no_tag_entities": [],
    }

    ner_ids = build_ner_ids(response)

    assert set(ner_ids.keys()) == {"fruit-apple&&0&&5", "company-apple&&0&&5"}


def test_build_ner_ids_includes_non_overlapping_regex():
    response = {
        "universal_entities": [],
        "regex_entities": [
            {"index": [0, 2], "surface_text": "99", "rule": "number-rule", "regex": r"\d+", "meronyms": []}
        ],
        "no_tag_entities": [],
    }

    ner_ids = build_ner_ids(response)

    assert ner_ids == {
        "number-rule&&0&&2": {
            "location": [0, 2],
            "surface_text": "99",
            "entity_id": "number-rule",
        }
    }


def test_build_ner_ids_excludes_overlapping_regex():
    response = {
        "universal_entities": [
            {
                "index": [0, 5],
                "surface_text": "apple",
                "corrected_text": "apple",
                "score": 0,
                "entities": [{"entity_id": "fruit-apple", "label": "Fruit", "surface_text": "apple"}],
            }
        ],
        "regex_entities": [
            {"index": [1, 3], "surface_text": "pp", "rule": "some-rule", "regex": ".", "meronyms": []}
        ],
        "no_tag_entities": [],
    }

    ner_ids = build_ner_ids(response)

    assert "some-rule&&1&&3" not in ner_ids
