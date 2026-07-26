"""MIO Core · Vertical Domain Brains (bounded contexts). Public yüzey.

8 dikey alan beyni (Business/Finance/Marketing/Sales/Product/Engineering/Security/Operations) — hepsi tavsiye
üretir, KARAR VERMEZ. Ortak `VerticalBrain` çekirdeği + bildirimsel `VerticalSpec`'ler."""

from .contract import CONTRACT_VERSION, VerticalEvents, vertical_contract, verticals_layer_contract
from .models import (
    Advice,
    GateVerdict,
    NotFoundError,
    UnauthorizedError,
    VERTICAL_BY_NAME,
    VERTICAL_SPECS,
    ValidationError,
    VerticalConfig,
    VerticalError,
    VerticalSpec,
)
from .repository import AdviceRepository
from .service import VerticalBrain, VerticalBrains

__all__ = [
    "VerticalBrains", "VerticalBrain", "VerticalSpec", "VERTICAL_SPECS", "VERTICAL_BY_NAME",
    "Advice", "GateVerdict", "AdviceRepository", "VerticalConfig",
    "VerticalError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "VerticalEvents", "vertical_contract", "verticals_layer_contract", "CONTRACT_VERSION",
]
