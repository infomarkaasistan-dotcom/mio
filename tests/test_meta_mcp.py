"""MIO Core · Meta MCP Manager (v2.0) — üretim testleri (deterministik, LLM-siz).

Health Monitor + Trust Engine + Capability Graph + Load Balancer + Cost Optimizer + Policy Engine + Catalog.
"""

import pytest

from mio_core.capability import Capability, CapabilityRegistry, RiskLevel
from mio_core.execution import (
    CapabilityPolicyEngine,
    MetaMCPManager,
    ToolOrchestrator,
    ToolRequest,
)


class OkExecutor:
    def execute(self, cap, action, args):
        return "ok"


# ---- Health Monitor ----
def test_health_monitor_records_and_excludes_blocked():
    reg = CapabilityRegistry()
    reg.register(Capability("x", connected=True))
    meta = MetaMCPManager(reg)
    meta.record("x", success=True, latency_ms=100)
    meta.record("x", success=False, latency_ms=200)
    meta.record("x", success=True, latency_ms=0, blocked=True)   # engel → hata sayılmaz
    m = meta.metrics("x")
    assert m.calls == 3 and m.successes == 1 and m.errors == 1
    assert m.success_rate == 0.5 and m.avg_latency_ms == 100
    assert m.first_used and m.last_used


# ---- Trust Engine (dinamik) ----
def test_trust_engine_base_and_history():
    reg = CapabilityRegistry()
    reg.register(Capability("native_cap", source="native", connected=True))
    reg.register(Capability("mcp_cap", source="mcp", connected=True))
    reg.register(Capability("risky", source="mcp", risk_level=RiskLevel.HIGH, connected=True))
    meta = MetaMCPManager(reg)
    assert meta.trust_score("native_cap") == 85
    assert meta.trust_score("mcp_cap") == 60
    assert meta.trust_score("risky") == 50                       # 60 - 10 (yüksek risk)
    for _ in range(5):
        meta.record("mcp_cap", success=True, latency_ms=50)
    assert meta.trust_score("mcp_cap") > 60                      # iyi geçmiş → yükseldi
    for _ in range(5):
        meta.record("risky", success=False)
    assert meta.trust_score("risky") < 50                        # kötü geçmiş → düştü


def test_health_state():
    reg = CapabilityRegistry()
    reg.register(Capability("y", connected=True))
    meta = MetaMCPManager(reg)
    assert meta.health_state("y") == "healthy"                   # çağrı yok + bağlı
    for _ in range(4):
        meta.record("y", success=False)
    meta.record("y", success=True)
    assert meta.health_state("y") == "down"                      # error_rate 0.8


# ---- Capability Graph + Load Balancer + Cost Optimizer ----
def test_graph_and_load_balancer_prefers_free():
    reg = CapabilityRegistry()
    reg.register(Capability("playwright.navigate", category="browser_automation", source="mcp", connected=True))
    reg.register(Capability("puppeteer.goto", category="browser_automation", source="mcp",
                            connected=True, incurs_cost=True))
    reg.register(Capability("pg.query", category="database", source="mcp", connected=True))
    meta = MetaMCPManager(reg)
    graph = meta.by_category()
    assert set(graph["browser_automation"]) == {"playwright.navigate", "puppeteer.goto"}
    assert meta.select_best("browser_automation") == "playwright.navigate"   # ücretsiz tercih (Cost Optimizer)
    assert meta.select_best("database") == "pg.query"
    assert meta.select_best("yok") is None


def test_load_balancer_uses_trust_when_same_cost():
    reg = CapabilityRegistry()
    reg.register(Capability("a.tool", category="cat", source="mcp", connected=True))
    reg.register(Capability("b.tool", category="cat", source="native", connected=True))  # native → daha yüksek trust
    meta = MetaMCPManager(reg)
    assert meta.select_best("cat") == "b.tool"                   # native trust 85 > mcp 60


# ---- Policy Engine ----
def test_policy_engine_rules():
    pol = CapabilityPolicyEngine()
    assert pol.required_approvals(Capability("fs.delete_file", risk_level=RiskLevel.HIGH)) == ["executive"]
    assert pol.required_approvals(Capability("stripe.charge", incurs_cost=True, category="payment")) == ["user"]
    assert pol.required_approvals(Capability("k8s.deploy", risk_level=RiskLevel.HIGH)) == ["executive", "user"]
    ok, reason, req = pol.evaluate(Capability("stripe.charge", incurs_cost=True), user_approved=False)
    assert not ok and "user" in reason
    ok2, _, _ = pol.evaluate(Capability("stripe.charge", incurs_cost=True), user_approved=True)
    assert ok2


# ---- Rich Catalog ----
def test_catalog_has_dynamic_fields():
    reg = CapabilityRegistry()
    reg.register(Capability("fs.delete_file", source="mcp", risk_level=RiskLevel.HIGH, connected=True))
    meta = MetaMCPManager(reg)
    entry = next(e for e in meta.catalog() if e["name"] == "fs.delete_file")
    assert "trust_score" in entry and "health_state" in entry and "metrics" in entry
    assert entry["required_approvals"] == ["executive"]


# ---- Orchestrator entegrasyonu (gerçek kullanımdan metrik) ----
def test_meta_records_from_orchestrator():
    reg = CapabilityRegistry()
    reg.register(Capability("x"))
    orch = ToolOrchestrator(reg)
    orch.register_executor("x", OkExecutor())
    meta = MetaMCPManager(reg)
    meta.attach(orch)
    orch.execute(ToolRequest("x", "a", {}))
    assert meta.metrics("x").calls == 1 and meta.metrics("x").successes == 1
    assert meta.trust_score("x") >= 55                          # gerçek başarı trust'ı besledi
