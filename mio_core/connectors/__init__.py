"""MIO Core · Capability Adapter Layer (Connector Layer). Public yüzey.

Executive → Connector Manager → [AI · Communication · Productivity · System] → Dış Sistem.
Executive isimle değil CAPABILITY ile çağırır; connector yoksa çökmez; AI danışmandır (karar vermez)."""

from .advisor import Advisor
from .contract import CONTRACT_VERSION, ConnectorEvents, connector_contract
from .manager import ConnectorManager
from .models import (
    Cap,
    CallableConnector,
    CapabilityNotSupported,
    ConnectorCategory,
    ConnectorConfig,
    ConnectorError,
    HealthStatus,
    HIGH_RISK_CAPABILITIES,
    Outcome,
    ValidationError,
)
from .registry import ConnectorRegistry

__all__ = [
    "ConnectorRegistry", "ConnectorManager", "Advisor", "CallableConnector",
    "ConnectorCategory", "Cap", "HIGH_RISK_CAPABILITIES", "Outcome", "HealthStatus", "ConnectorConfig",
    "ConnectorError", "ValidationError", "CapabilityNotSupported",
    "ConnectorEvents", "connector_contract", "CONTRACT_VERSION",
]
