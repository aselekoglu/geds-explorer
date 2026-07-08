from pathlib import Path
import pytest

from geds_crawler.parser import extract_departments
from geds_crawler.catalog import select_departments

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_select_departments_by_canonical_dn():
    html = load_fixture("department_list.html")
    # allowed_names=None ile tüm departmanları çıkartıyoruz
    catalog = extract_departments(html, allowed_names=None)
    
    # 4 departman da çıkmalı
    assert len(catalog) == 4
    
    # ISED ve SSC seçmek istiyoruz DN ile:
    allowed_dns = {"OU=ISED-ISDE,O=GC,C=CA", "ou=ssc-spc,o=gc,c=ca"}
    selected = select_departments(catalog, allowed_dns)
    
    assert len(selected) == 2
    selected_names = {dept.name for dept in selected}
    assert "Innovation Science and Economic Development Canada" in selected_names
    assert "Shared Services Canada" in selected_names


def test_select_departments_empty_dns():
    html = load_fixture("department_list.html")
    catalog = extract_departments(html, allowed_names=None)
    selected = select_departments(catalog, set())
    assert len(selected) == 0
