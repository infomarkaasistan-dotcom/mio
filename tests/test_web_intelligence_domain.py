"""MIO Core · Web Intelligence Domain (Faz 4 · Domain 32) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik fetcher üzerinden. Durum makinesi,
connector routing, DÜRÜST no_connector, domain allowlist güvenliği (blocked), authorization, events doğrulanır."""

import pytest

from mio_core.domains.web_intelligence import (
    JobStatus,
    WebConfig,
    WebEvents,
    WebIntelligenceDomain,
    WebKind,
    WebRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    host_of,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = WebRepository(":memory:")
    bus = EventBus(record=True)
    dom = WebIntelligenceDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def wd():
    return _build()


# ---- UNIT: host_of + validation + authz ----
def test_host_extraction_and_authz(wd):
    d, _r, _b = wd
    assert host_of("https://Example.com/path?q=1") == "example.com"
    with pytest.raises(ValidationError):
        d.fetch("owner", "  ")
    with pytest.raises(UnauthorizedError):
        d.fetch("Reasoning", "https://x.com")              # reader ama writer değil


# ---- INTEGRATION: connector YOK → DÜRÜST no_connector ----
def test_no_connector_is_honest(wd):
    d, _r, bus = wd
    job = d.fetch("owner", "https://example.com")
    assert job["status"] == JobStatus.NO_CONNECTOR and job["result"] == {}   # uydurma içerik YOK
    assert any(e["type"] == WebEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: allowlist güvenliği (blocked) ----
def test_allowlist_blocks_disallowed_host():
    d, _r, bus = _build(WebConfig(allowed_hosts={"trusted.com"}))
    def fake_fetch(ctx):
        return {"content": "ok"}
    d.register_fetcher(WebKind.FETCH, fake_fetch)
    blocked = d.fetch("owner", "https://evil.com/x")
    assert blocked["status"] == JobStatus.BLOCKED                            # allowlist dışı → engellendi
    ok = d.fetch("owner", "https://trusted.com/page")
    assert ok["status"] == JobStatus.COMPLETED and ok["result"]["content"] == "ok"
    assert any(e["type"] == WebEvents.BLOCKED for e in bus.history())


def test_admin_allow_host(wd):
    d, _r, _b = wd
    with pytest.raises(UnauthorizedError):
        d.allow_host("Research", "x.com")                  # admin değil
    res = d.allow_host("owner", "MySite.com")
    assert "mysite.com" in res["allowed_hosts"]


# ---- INTEGRATION: fetcher delege + search (allowlist gerekmez) ----
def test_fetcher_delegation_and_search(wd):
    d, _r, bus = wd
    d.register_fetcher(WebKind.SEARCH, lambda ctx: {"results": [ctx["target"]]}, name="fake-search")
    job = d.search("owner", "MIO nedir")
    assert job["status"] == JobStatus.COMPLETED and job["result"]["results"] == ["MIO nedir"]
    d.register_fetcher(WebKind.CRAWL, lambda ctx: (_ for _ in ()).throw(RuntimeError("timeout")))
    fail = d.crawl("owner", "https://example.com", depth=2)
    assert fail["status"] == JobStatus.FAILED and "timeout" in fail["error"]


# ---- INTEGRATION: get + list + stats + contract ----
def test_get_list_stats_contract(wd):
    d, _r, _b = wd
    j = d.fetch("owner", "https://example.com")
    assert d.get_job("owner", j["id"])["id"] == j["id"]
    assert len(d.list_jobs("owner", status=JobStatus.NO_CONNECTOR)) == 1
    with pytest.raises(NotFoundError):
        d.get_job("owner", "yok")
    s = d.stats()
    assert s["jobs"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "web_intelligence" and "fetch" in c["operations"]


# ---- SMOKE: boot() → dürüst no_connector ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    job = mio.web.fetch("owner", "https://example.com")
    assert job["status"] == JobStatus.NO_CONNECTOR          # dürüst: gerçek ağ connector'ı bağlı değil
    assert mio.web.contract()["version"] == "1.0.0"
    mio.close()
