"""MIO Core · Contract Versioning (Platform Invariant §2) — üretim testleri, deterministik."""

from mio_core.capability import Capability, RiskLevel
from mio_core.contracts import (
    EventContracts,
    capability_contract,
    contract_signature,
    contracts_compatible,
    version_tuple,
)
from mio_core.events import Ev, EventBus


def _cap(**kw):
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    base = dict(name="fs.read", parameters=schema, risk_level=RiskLevel.LOW, contract_version="1.0.0")
    base.update(kw)
    return Capability(**base)


def test_capability_contract_shape():
    c = capability_contract(_cap())
    assert c["name"] == "fs.read" and c["version"] == "1.0.0"
    assert c["required_params"] == ["path"] and c["params"] == ["path"]


def test_signature_drift_detection():
    same1, same2 = contract_signature(_cap()), contract_signature(_cap(contract_version="9.9.9"))
    assert same1 == same2                                # şekil aynı → imza aynı (sürümden bağımsız)
    diff = contract_signature(_cap(risk_level=RiskLevel.HIGH))
    assert diff != same1                                 # risk değişti → drift


def test_backward_compatibility_rules():
    old = capability_contract(_cap(contract_version="1.0.0"))
    assert contracts_compatible(old, capability_contract(_cap(contract_version="1.2.0")))   # minor → ok
    assert not contracts_compatible(old, capability_contract(_cap(contract_version="2.0.0")))  # major → breaking
    # zorunlu parametre kaldırıldı → breaking
    no_req = _cap()
    no_req.parameters = {"type": "object", "properties": {"path": {}}, "required": []}
    assert not contracts_compatible(old, capability_contract(no_req))
    # risk yükseldi → breaking
    assert not contracts_compatible(old, capability_contract(_cap(risk_level=RiskLevel.HIGH)))


def test_version_tuple():
    assert version_tuple("2.3.1") == (2, 3, 1) and version_tuple("1") == (1, 0, 0)


def test_event_contracts_and_bus_version():
    ec = EventContracts()
    ec.register(Ev.TOOL_CALL, "2.0.0")
    assert ec.version(Ev.TOOL_CALL) == "2.0.0" and ec.version(Ev.DIAGNOSTIC) == "1.0.0"
    bus = EventBus(record=True, contracts=ec)
    ev = bus.publish(Ev.TOOL_CALL, {"x": 1})
    assert ev["v"] == "2.0.0"                             # publish sözleşme sürümünü iliştirdi
