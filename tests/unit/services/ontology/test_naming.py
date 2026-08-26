from talkingdb_pt.services.ontology import naming


def test_class_type_name():
    assert naming.class_type_name("category") == "Class_Type_Category"


def test_instance_type_name():
    assert naming.instance_type_name("smartphone") == "Instance_Type_Smartphone"


def test_create_kg_friendly_entity_name_handles_separators():
    assert (
        naming.create_kg_friendly_entity_name("storage capacity") == "Storage_Capacity"
    )
    assert (
        naming.create_kg_friendly_entity_name("storage_capacity") == "Storage_Capacity"
    )
    assert (
        naming.create_kg_friendly_entity_name("storage-capacity") == "Storage_Capacity"
    )


def test_create_kg_friendly_entity_name_strips_non_word_characters():
    assert naming.create_kg_friendly_entity_name("odd!! name??") == "Odd_Name"
