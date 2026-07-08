from geds_crawler.urls import canonical_dn, geds_url, parse_geds_link


def test_parse_geds_link_extracts_pgid_and_canonical_dn_from_relative_url():
    parsed = parse_geds_link("/en/GEDS?pgid=014&dn=T1U9U1NDLVNQQyxPPUdDLEM9Q0E%3D")

    assert parsed is not None
    assert parsed.pgid == "014"
    assert parsed.dn == "OU=SSC-SPC,O=GC,C=CA"
    assert parsed.url == "https://geds-sage.gc.ca/en/GEDS?pgid=014&dn=T1U9U1NDLVNQQyxPPUdDLEM9Q0E%3D"


def test_parse_geds_link_keeps_geds_path_for_query_relative_live_links():
    parsed = parse_geds_link("?pgid=014&dn=T1U9U1NDLVNQQyxPPUdDLEM9Q0E=")

    assert parsed is not None
    assert parsed.pgid == "014"
    assert parsed.url == "https://geds-sage.gc.ca/en/GEDS?pgid=014&dn=T1U9U1NDLVNQQyxPPUdDLEM9Q0E="


def test_canonical_dn_accepts_encoded_or_decoded_dn():
    encoded = "T1U9U1NDLVNQQyxPPUdDLEM9Q0E%3D"

    assert canonical_dn(encoded) == "OU=SSC-SPC,O=GC,C=CA"
    assert canonical_dn("OU=SSC-SPC,O=GC,C=CA") == "OU=SSC-SPC,O=GC,C=CA"


def test_geds_url_encodes_dn_for_official_source_link():
    url = geds_url("015", "CN=Jane Doe,OU=SSC-SPC,O=GC,C=CA")

    assert url.startswith("https://geds-sage.gc.ca/en/GEDS?pgid=015&dn=")
    assert "CN%3DJane+Doe" not in url
