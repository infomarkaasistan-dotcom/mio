"""MIO Core · Business Workspace — çoklu İZOLE işletme (tek sahip). Unified Product Experience.

Her işletme kendi ayrı dizininde (izole state); platform kodu paylaşılır (boot() reuse). Yeni registry değil —
business dizin kaydı. Create/list/get/delete/stats, izolasyon, tip validation, CLI/HTTP/conversational entegrasyon."""

import json

import pytest

from mio_core.platform.workspaces import BusinessWorkspaceManager, BusinessWorkspaceError, BUSINESS_TEMPLATES


@pytest.fixture
def mgr(tmp_path):
    return BusinessWorkspaceManager(str(tmp_path / "home"))


# ---- manager: create + izolasyon ----
def test_create_and_isolation(mgr):
    a = mgr.create("Acme", business_type="marketing_agency")
    b = mgr.create("Shop", business_type="ecommerce")
    assert a["label"] == "Pazarlama Ajansı" and "Marketing" in a["departments"]
    assert a["path"] != b["path"]                     # izole dizinler
    import os
    assert os.path.isdir(a["path"]) and os.path.isdir(b["path"])
    names = [x["name"] for x in mgr.list()]
    assert names == ["Acme", "Shop"]


def test_validation(mgr):
    with pytest.raises(BusinessWorkspaceError):
        mgr.create("", business_type="personal")      # boş ad
    with pytest.raises(BusinessWorkspaceError):
        mgr.create("X", business_type="uydurma")      # geçersiz tip
    mgr.create("Dup")
    with pytest.raises(BusinessWorkspaceError):
        mgr.create("dup")                             # çakışan ad (case-insensitive)


def test_get_delete_objectives(mgr):
    b = mgr.create("Biz", objectives=["büyüme"])
    assert mgr.get(b["id"])["objectives"] == ["büyüme"]
    assert mgr.get("Biz")["id"] == b["id"]            # ada göre de bulunur
    mgr.set_objectives(b["id"], ["kâr", "ölçek"])
    assert mgr.get(b["id"])["objectives"] == ["kâr", "ölçek"]
    import os
    path = b["path"]
    d = mgr.delete(b["id"], purge=True)
    assert d["deleted"] == b["id"] and not os.path.isdir(path)   # purge state'i siler
    assert mgr.get(b["id"]) is None


def test_registry_persists(tmp_path):
    home = str(tmp_path / "home")
    m1 = BusinessWorkspaceManager(home)
    m1.create("Persist", business_type="saas")
    m2 = BusinessWorkspaceManager(home)               # yeni instance, aynı home
    assert [b["name"] for b in m2.list()] == ["Persist"]


def test_stats(mgr):
    mgr.create("A", business_type="saas")
    mgr.create("B", business_type="saas")
    mgr.create("C", business_type="ecommerce")
    s = mgr.stats()
    assert s["businesses"] == 3 and s["by_type"]["saas"] == 2
    assert set(s["templates"]) == set(BUSINESS_TEMPLATES)


# ---- entegrasyon: boot + appservice + CLI + HTTP + conversational ----
def test_via_runtime_and_interfaces(tmp_path):
    from mio_core.runtime import boot
    from mio_core.platform.config import Config
    from mio_core import appservice
    from mio_core.cli import run_command
    from mio_core.http_api import route_request
    cfg = Config(env_file=None, environ={"MIO_HOME": str(tmp_path / "home")})
    mio = boot(workspace=str(tmp_path / "ws"), connect_ollama=False, discover_hw=False, config=cfg)
    try:
        # appservice
        rec = appservice.business_create(mio, "Test İşletme", business_type="factory")
        assert rec["label"] == "Fabrika"
        assert len(appservice.business_list(mio)) == 1
        # CLI
        assert run_command(mio, ["business", "list"])[0] == 0
        code, out = run_command(mio, ["business", "create", "CLI-Biz", "restaurant"])
        assert code == 0 and json.loads(out)["business_type"] == "restaurant"
        # HTTP (aynı DTO)
        st, data = route_request(mio, "GET", "/business", {}, None)
        assert st == 200 and len(data) == 2
        st2, created = route_request(mio, "POST", "/business", {}, {"name": "HTTP-Biz",
                                     "business_type": "personal"})
        assert st2 == 200 and created["name"] == "HTTP-Biz"
        # conversational
        assert appservice.converse(mio, "işletmelerim")["intent"] == "business"
        assert appservice.converse(mio, "yeni sirket kur")["intent"] == "business"
    finally:
        mio.close()
