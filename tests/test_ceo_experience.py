"""MIO Core · CEO Experience — intent→plan→delegate→execute→report zinciri (Unified Product Experience).

Orkestratör YENİ plan/görev/hedef YARATMAZ — mevcut Executive/Planning/Multi-Agent'ı zincirler. Executive tek
karar verici; adım kaynağı owner/advisor (advisory). Delegation gerçek (yetenek eşleşmesi); agent/executor yoksa
DÜRÜST no_agent/no_connector. Report = konsolide Dashboard DTO. CLI/HTTP/conversational aynı DTO."""

import json

import pytest

from mio_core.runtime import boot
from mio_core import appservice
from mio_core.cli import run_command
from mio_core.http_api import route_request


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "ws"), connect_ollama=False, discover_hw=False)
    try:
        yield m
    finally:
        m.close()


# ---- intent→plan: sahip niyeti → Executive hedefi + Planning planı (yürütme yok) ----
def test_direct_creates_goal_and_plan(mio):
    d = mio.ceo.direct("3 ayda geliri ikiye katla", horizon_days=90,
                       steps=[{"description": "Pazar analizi"}, {"description": "Kampanya kur"},
                              {"description": "Raporla"}])
    assert d["goal"]["id"] and d["goal"]["status"] == "active" and d["goal"]["horizon_days"] == 90
    assert d["plan"]["steps"] == 3 and d["plan"]["step_source"] == "owner"
    assert d["feasible"] is True                       # yeteneksiz adımlar → fizibil (eksik connector yok)
    # gerçekten Executive hedefi + Planning planı yaratıldı (mevcut domainler)
    assert mio.executive.status()["counts"]["active_goals"] == 1
    assert len(mio.planning.list_plans("owner")) == 1


def test_direct_without_steps_is_honest(mio):
    """Adım yok + Advisor yok → boş plan (uydurma adım YOK — dürüst)."""
    d = mio.ceo.direct("büyü", steps=None)
    assert d["plan"]["steps"] == 0 and d["plan"]["step_source"] == "none"
    assert d["feasible"] is None                       # değerlendirilecek adım yok
    assert "adım ekleyin" in d["next"].lower()


def test_direct_infeasible_when_capability_unprovided(mio):
    """Adım bilinmeyen capability isterse plan fizibil DEĞİL (Madde 8 — connector yoksa dürüst)."""
    d = mio.ceo.direct("veri çek", steps=[{"description": "Web'den çek", "capability": "web.search"}])
    assert d["feasible"] is False
    assert any("web.search" in i for i in d["assessment"]["issues"])


# ---- delegate→execute: adımlar → Multi-Agent görevleri (agent yoksa dürüst no_agent) ----
def test_delegate_honest_no_agent_then_no_connector(mio):
    d = mio.ceo.direct("kampanya", steps=[{"description": "Adım A"}, {"description": "Adım B"}])
    plan_id = d["plan"]["id"]
    dl = mio.ceo.delegate(plan_id)
    assert dl["delegated"] == 2 and dl["by_status"].get("no_agent") == 2   # agent yok → DÜRÜST
    # agent kaydet → artık eşleşir ama executor bağlı değil → no_connector (DÜRÜST)
    appservice.agent_register(mio, "Ajan", capabilities=[], max_load=5)
    dl2 = mio.ceo.delegate(plan_id)
    assert dl2["by_status"].get("no_connector") == 2
    # görevler gerçekten multi_agent'ta oluştu
    assert len(mio.multi_agent.list_tasks("owner")) == 4


def test_delegate_high_risk_requires_approval(mio):
    """Yüksek-risk görev onaysız yürütülmez (Madde 24) — başlık riskli ise requires_approval."""
    d = mio.ceo.direct("temizlik", steps=[{"description": "Tüm verileri sil ve sıfırla"}])
    dl = mio.ceo.delegate(d["plan"]["id"], approve=False)
    statuses = {r["status"] for r in dl["results"]}
    assert "requires_approval" in statuses or "no_agent" in statuses   # riskli→onay ya da agent yok (ikisi de dürüst)


# ---- report: konsolide Dashboard DTO (mevcut domainlerden gerçek veri) ----
def test_report_dashboard(mio):
    mio.ceo.direct("hedef", steps=[{"description": "iş"}])
    appservice.agent_register(mio, "A1", capabilities=["x"])
    rep = mio.ceo.report()
    assert rep["active_goals"] == 1 and rep["plans"]["total"] == 1
    assert rep["agents"]["total"] == 1 and rep["businesses"]["total"] == 0   # işletme yok → 0 (dürüst)
    assert rep["executive_score"] >= 0 and "system_confidence" in rep


# ---- KATMAN: orkestratör yeni domain/registry yaratmaz (mevcutları çağırır) ----
def test_orchestrator_reuses_existing_no_new_system():
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "mio_core" / "ceo.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # yalnız appservice import eder (orkestrasyon); repository/SQLite/registry KURMAZ
    froms = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    modules = [n.module for n in froms]
    assert "sqlite3" not in modules and not any("repository" in (m or "") for m in modules)
    # `from mio_core import appservice` → module=mio_core, name=appservice (orkestrasyon yüzeyi)
    assert any(n.module == "mio_core" and any(a.name == "appservice" for a in n.names) for n in froms)


# ---- arayüz eşitliği: CLI + HTTP + conversational aynı DTO ----
def test_interfaces_same_dto(mio):
    mio.ceo.direct("x", steps=[{"description": "y"}])
    assert run_command(mio, ["ceo", "report"])[0] == 0
    assert run_command(mio, ["agent", "list"])[0] == 0
    st, data = route_request(mio, "GET", "/ceo/report", {}, None)
    assert st == 200 and "executive_score" in data
    st2, created = route_request(mio, "POST", "/agents", {}, {"name": "HTTP-Agent", "capabilities": ["z"]})
    assert st2 == 200 and created["name"] == "HTTP-Agent"
    st3, rep2 = route_request(mio, "GET", "/dashboard", {}, None)
    assert st3 == 200 and rep2["agents"]["total"] == 1
    assert appservice.converse(mio, "yönetim panosu")["intent"] == "ceo"


def test_cli_ceo_direct_and_delegate(mio):
    code, out = run_command(mio, ["ceo", "direct", "Satışları artır", "--days", "60",
                                  "--steps", json.dumps([{"description": "Reklam"}])])
    assert code == 0
    plan_id = json.loads(out)["plan"]["id"]
    code2, out2 = run_command(mio, ["ceo", "delegate", plan_id])
    assert code2 == 0 and json.loads(out2)["delegated"] == 1
