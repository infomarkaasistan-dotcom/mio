"""MIO Core · Governance Extensions v1.0 (kod referansı) — Constitution addendum, LLM-BAĞIMSIZ.

Belge: docs/GOVERNANCE_EXTENSIONS.md. Bu modül yalnız makine-okunur sabitleri + çelişki-çözümü yardımcısını
sağlar; yeni kural EKLEMEZ, mevcut ilkeleri kodda referanslanabilir yapar (çekirdeği büyütmez)."""

from __future__ import annotations

__all__ = ["PRIORITY_ORDER", "priority_rank", "resolve_conflict",
           "ComplianceLevel", "CANONICAL_VOCABULARY"]

# §1 Constitutional Priority Order — üst, alta feda edilemez.
PRIORITY_ORDER = (
    "human_safety", "security", "constitutional_compliance", "backward_compatibility",
    "correctness", "reliability", "maintainability", "extensibility", "performance", "cost_optimization",
)
_RANK = {p: i for i, p in enumerate(PRIORITY_ORDER)}


def priority_rank(principle: str) -> int:
    """Düşük = daha öncelikli. Bilinmeyen → en düşük öncelik."""
    return _RANK.get(principle, len(PRIORITY_ORDER))


def resolve_conflict(a: str, b: str) -> str:
    """İki ilke çeliştiğinde öncelik sırasına göre kazananı döner (§1)."""
    return a if priority_rank(a) <= priority_rank(b) else b


class ComplianceLevel:
    """§10 — büyük geliştirme sonunda uyum raporu seviyesi."""
    FULLY = "fully_compliant"
    SUBSTANTIALLY = "substantially_compliant"
    PARTIALLY = "partially_compliant"
    EXCEPTION = "exception_approved"          # zorunlu ADR
    NON = "non_compliant"                     # production'a alınamaz

    PRODUCTION_OK = {FULLY, SUBSTANTIALLY, EXCEPTION}

    @classmethod
    def production_allowed(cls, level: str) -> bool:
        return level in cls.PRODUCTION_OK


# §5 Canonical Vocabulary — platform genelinde tek anlam.
CANONICAL_VOCABULARY = {
    "Domain": "Bağımsız bounded context (iş alanı).",
    "Capability": "Versiyonlanabilir yetenek.",
    "Operation": "Gerçek dünyadaki iş süreci.",
    "Executive": "Stratejik karar/orkestrasyon katmanı.",
    "Policy": "Yönetişim/yetki kuralları.",
    "Memory": "Kalıcı bilgi katmanı.",
    "Knowledge": "Yapısal/anlamsal bilgi.",
    "Tool": "Tek iş yapan yardımcı bileşen.",
    "Plugin": "Sonradan eklenen genişletme modülü.",
    "Adapter": "Harici sistemi platform sözleşmesine uyarlar.",
    "Connector": "Belirli bir dış sistemle teknik entegrasyon.",
    "MCP": "Standart harici yetenek erişim protokolü.",
    "DigitalTwin": "Gerçek sistemin dijital temsili.",
    "Simulation": "Karar-öncesi senaryo değerlendirme.",
}
