from geds_crawler.career_people import extract_observed_classifications


def test_explicit_classifications_are_normalized_without_semantic_guessing():
    assert extract_observed_classifications("Economist - EC-04") == ("EC-04",)
    assert extract_observed_classifications("IT02 / CS2") == ("IT-02", "CS-02")
    assert extract_observed_classifications("Fisheries Management Officer (CO-01)") == ("CO-01",)
    assert extract_observed_classifications("Software Developer") == ()


def test_duplicate_and_unsupported_classifications_are_not_exposed():
    assert extract_observed_classifications("IT-02 / it 02") == ("IT-02",)
    assert extract_observed_classifications("AS-05 Analyst") == ()
    assert extract_observed_classifications(None) == ()
