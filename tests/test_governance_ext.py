"""MIO Core · Governance Extensions v1.0 — Capability Maturity + Priority Order + Compliance (üretim testleri)."""

from mio_core.capability import Capability, CapabilityRegistry, MaturityLevel
from mio_core.execution import MetaMCPManager
from mio_core.governance_ext import (
    CANONICAL_VOCABULARY,
    PRIORITY_ORDER,
    ComplianceLevel,
    priority_rank,
    resolve_conflict,
)


# ---- §7 Capability Maturity ----
def test_capability_maturity_default_stable():
    assert Capability("x").maturity == MaturityLevel.STABLE
    assert Capability("y").to_dict()["maturity"] == "stable"


def test_select_best_prefers_maturity_and_excludes_retired():
    reg = CapabilityRegistry()
    reg.register(Capability("a.x", category="cat", source="mcp", connected=True, maturity="experimental"))
    reg.register(Capability("b.x", category="cat", source="mcp", connected=True, maturity="production"))
    reg.register(Capability("c.x", category="cat", source="mcp", connected=True, maturity="retired"))
    meta = MetaMCPManager(reg)
    assert meta.select_best("cat") == "b.x"              # production > experimental; retired elendi
    entry = next(e for e in meta.catalog() if e["name"] == "b.x")
    assert entry["maturity"] == "production"


# ---- §1 Constitutional Priority Order ----
def test_priority_order_and_conflict_resolution():
    assert PRIORITY_ORDER[0] == "human_safety" and PRIORITY_ORDER[1] == "security"
    assert priority_rank("security") < priority_rank("performance")
    assert resolve_conflict("performance", "security") == "security"     # güvenlik performansı yener
    assert resolve_conflict("backward_compatibility", "cost_optimization") == "backward_compatibility"


# ---- §10 Compliance Levels ----
def test_compliance_levels():
    assert ComplianceLevel.production_allowed(ComplianceLevel.FULLY)
    assert ComplianceLevel.production_allowed(ComplianceLevel.EXCEPTION)
    assert not ComplianceLevel.production_allowed(ComplianceLevel.NON)      # ihlal → production yok
    assert not ComplianceLevel.production_allowed(ComplianceLevel.PARTIALLY)


# ---- §5 Canonical Vocabulary ----
def test_canonical_vocabulary():
    for term in ("Domain", "Capability", "Executive", "Connector", "MCP", "Simulation"):
        assert term in CANONICAL_VOCABULARY
