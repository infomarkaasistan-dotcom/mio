"""MIO Core · Production Runtime — üretim testleri (ağsız: connect_ollama=False; donanım gerçek stdlib)."""

import pytest

from mio_core.adapters import MCPServerConfig
from mio_core.execution import ToolRequest
from mio_core.knowledge import KnowledgeItem, KnowledgeType
from mio_core.runtime import boot


class _FakeTransport:
    def __init__(self, tools, result="ok"):
        self._tools = tools
        self._result = result
        self.calls = []

    def request(self, method, params=None):
        if method == "tools/list":
            return {"tools": self._tools}
        if method == "tools/call":
            self.calls.append((params["name"], params["arguments"]))
            return {"content": [{"type": "text", "text": self._result}]}
        return {}

    def is_alive(self):
        return True

    def close(self):
        pass


@pytest.fixture
def mio(tmp_path):
    rt = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=True)
    yield rt
    rt.close()


def test_boot_assembles_capable_mio(mio):
    m = mio.who_am_i()
    assert m["who_am_i"]["name"] == "MIO"
    assert m["purpose"]["primary_objective"]
    assert len(m["brains"]) == 14
    assert mio.birth_summary["innate_knowledge"] > 0
    assert mio.birth_summary["innate_beliefs"] > 0


def test_llm_blocked_when_not_connected(mio):
    # Ollama bağlanmadı → 'llm' tanımlı ama bağlı değil → dürüst blok (çekirdek LLM-siz çalışır)
    res = mio.ask_llm("merhaba", requester="Marketing")
    assert res.blocked and "bağlı değil" in res.reason


def test_recommend_from_innate_knowledge(mio):
    recs = mio.recommend({"new_expense"})
    assert recs and "ücretsiz" in recs[0].recommendation.lower()   # innate bilgi karar üretir (LLM'siz)


def test_hardware_discovered_into_self_model(mio):
    hw = mio.who_am_i()["hardware"]
    assert hw.get("system") and isinstance(hw.get("cpu_count"), int)


def test_boot_wires_real_mcp(tmp_path):
    ft = _FakeTransport([{"name": "read_file", "description": "oku"}], result="içerik")
    rt = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False,
              mcp_servers=[MCPServerConfig("fs", command=["x"])],
              mcp_transport_factory=lambda c: ft)
    assert rt.birth_summary["mcp_capabilities"] == 1
    assert rt.capabilities.can("fs.read_file")
    assert "fs.read_file" in rt.who_am_i()["active_mcps"]          # öz-modele yansıdı
    res = rt.orchestrator.execute(ToolRequest("fs.read_file", "read", {"p": "a"}, requester="Engineering"))
    assert res.success and res.output == "içerik"                 # gerçek MCP çağrısı akışı
    rt.close()


def test_runtime_discover_mcp_zero_code(tmp_path):
    """ÇALIŞMA ANINDA yeni MCP eklenir — sıfır kod. MIO 'artık X kullanabiliyorum' der."""
    rt = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    assert not rt.capabilities.can("postgres.query")               # başta yok
    ft = _FakeTransport([{"name": "query", "description": "SQL sorgu"}], result="rows")
    report = rt.discover_mcp(MCPServerConfig("postgres", command=["x"]),
                             transport_factory=lambda c: ft)
    assert "postgres.query" in {c.name for c in report.capabilities}
    assert rt.capabilities.can("postgres.query")                   # MIO artık kullanabiliyor
    assert "postgres.query" in rt.who_am_i()["active_mcps"]        # öz-modele yansıdı
    assert report.executive_decision_id                            # Executive'e raporlandı
    idx = {e["name"] for e in rt.capability_index()}
    assert "postgres.query" in idx                                 # meta katalogda
    rt.close()


def test_observability_and_health(mio):
    h = mio.health()
    assert h["status"] in ("booting", "operational", "degraded")
    obs = mio.observability()
    assert "health" in obs and "analytics" in obs and "recent_events" in obs
    assert obs["policy_profile"] == "safe"


def test_runtime_ecosystem_services(mio):
    assert "total_capabilities" in mio.diagnostics()          # Self Diagnostics
    assert "total_calls" in mio.analytics()                   # Analytics
    assert isinstance(mio.mcp_store(), list)                  # MCP Store
    assert any(e.name == "playwright" for e in mio.recommend_capability("tarayıcı otomasyon"))  # Recommendation
    assert mio.marketplace.get("filesystem")                  # Marketplace
    assert mio.activate_policy("read_only").name == "read_only"  # Policy Profiles
    assert "safe" in mio.policy_profiles.names()


def test_ecosystem_learning_persists(tmp_path):
    """Area 3: yaşayarak öğrenilen bilgi + kullanım metrikleri reboot'ta kalır."""
    ws = str(tmp_path / "mio")
    rt = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    rt.knowledge.add(KnowledgeItem(KnowledgeType.RULE, "learned-rule", statement="öğrenildi",
                                   source="observation", when=["ctx"], then="yap"))
    rt.orchestrator.execute(ToolRequest("reasoning.suite", "score",
                                        {"item": {"scores": {"x": 1}}, "weights": {"x": 1}},
                                        requester="Executive"))
    rt.close()                                                # persist
    rt2 = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    assert any(k.name == "learned-rule" for k in rt2.knowledge.learned())  # bilgi geri geldi
    assert rt2.meta.metrics("reasoning.suite").calls >= 1                   # metrik geri geldi
    rt2.close()


def test_persistence_across_reboot(tmp_path):
    ws = str(tmp_path / "mio")
    rt1 = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    ident1 = rt1.state.get_identity().name
    v1 = rt1.state.get_identity().version
    rt1.close()
    rt2 = boot(workspace=ws, connect_ollama=False, discover_hw=False)   # aynı çalışma alanı
    assert rt2.state.get_identity().name == ident1
    assert rt2.state.get_identity().version == v1                       # idempotent doğuş, kimlik korunur
    rt2.close()
