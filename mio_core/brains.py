"""MIO Core · Brain Registry — DOĞUŞTAN gelen, kimlikli Domain Brain'ler (ADR-0002 Madde 2).

MIO 14 Domain Brain'le DOĞAR (sonradan oluşmaz). Her Brain'in kimliği tanımlıdır: sorumluluk alanı,
uzmanlık bilgi alanları ve kullanabileceği yetenekler. Deneyimleri zamanla gelişir; kimlikleri doğuştandır.

NOT: Bir Brain düşünen bağımsız bir varlık DEĞİLDİR (LLM değildir). Brain, bir uzmanlık alanının kimliği +
o alanın bilgi/yetenek kapsamıdır; kararlar tek Executive'den geçer, yürütme Tool Orchestrator'dan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .executive.models import now_iso

__all__ = ["DomainBrain", "BrainRegistry", "default_domain_brains"]


@dataclass
class DomainBrain:
    name: str
    domain: str
    responsibilities: list[str] = field(default_factory=list)
    knowledge_domains: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)   # kullanabileceği yetenek adları (["*"] = tümü)
    born_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "domain": self.domain,
                "responsibilities": list(self.responsibilities),
                "knowledge_domains": list(self.knowledge_domains),
                "capabilities": list(self.capabilities), "born_at": self.born_at}


class BrainRegistry:
    """Doğuştan Domain Brain kayıt defteri (bellek-içi; her doğuşta default_domain_brains ile dolar)."""

    def __init__(self) -> None:
        self._brains: dict[str, DomainBrain] = {}

    def register(self, brain: DomainBrain) -> DomainBrain:
        self._brains[brain.name] = brain
        return brain

    def register_all(self, brains: list[DomainBrain]) -> int:
        for b in brains:
            self.register(b)
        return len(brains)

    def get(self, name: str) -> Optional[DomainBrain]:
        return self._brains.get(name)

    def list(self) -> list[DomainBrain]:
        return list(self._brains.values())

    def names(self) -> list[str]:
        return list(self._brains.keys())


def default_domain_brains() -> list[DomainBrain]:
    """MIO'nun DOĞUŞTAN gelen 14 Domain Brain'i (ADR-0002 Madde 2). Kimlikleri sabit, deneyimleri sonradan."""
    return [
        DomainBrain("Executive", "executive",
                    ["hedef yönetimi", "strateji", "karar", "review", "governance"],
                    ["Decision Science", "Systems Thinking", "Business"], ["*"]),
        DomainBrain("Business", "business",
                    ["iş modeli", "değer önerisi", "pazar konumlandırma"],
                    ["Business", "Economics", "Systems Thinking"], []),
        DomainBrain("Finance", "finance",
                    ["nakit akışı", "bütçe", "maliyet", "gelir modeli"],
                    ["Finance", "Economics"], []),
        DomainBrain("Marketing", "marketing",
                    ["konumlandırma", "içerik", "kanal", "büyüme"],
                    ["Marketing", "Human Psychology & Behavior", "Communication"], []),
        DomainBrain("Sales", "sales",
                    ["huni", "dönüşüm", "müzakere", "müşteri ilişkisi"],
                    ["Sales", "Human Psychology & Behavior", "Communication"], []),
        DomainBrain("Product", "product",
                    ["ürün stratejisi", "özellik önceliklendirme", "kullanıcı değeri"],
                    ["Product", "Decision Science"], []),
        DomainBrain("Engineering", "engineering",
                    ["yazılım tasarımı", "uygulama", "otomasyon", "entegrasyon"],
                    ["Software Engineering", "AI", "Security"], []),
        DomainBrain("Knowledge", "knowledge",
                    ["bilgi yönetimi", "araştırma", "sentez", "hafıza"],
                    ["Systems Thinking", "AI"], []),
        DomainBrain("Security", "security",
                    ["risk", "izin", "uyum", "denetim"],
                    ["Security", "Legal & Compliance"], []),
        DomainBrain("Operations", "operations",
                    ["süreç", "kaynak", "yürütme koordinasyonu"],
                    ["Systems Thinking", "Business"], []),
        DomainBrain("Workflow", "workflow",
                    ["iş akışı tasarımı", "orkestrasyon", "durum yönetimi"],
                    ["Systems Thinking", "Software Engineering"], []),
        DomainBrain("Learning", "learning",
                    ["deneyimden öğrenme", "prediction-error", "iyileştirme"],
                    ["AI", "Decision Science"], []),
        DomainBrain("Communication", "communication",
                    ["kullanıcı iletişimi", "raporlama", "açıklama"],
                    ["Communication", "Human Psychology & Behavior"], []),
        DomainBrain("Identity", "identity",
                    ["kimlik", "misyon", "değerler", "öz-model tutarlılığı"],
                    ["Systems Thinking"], []),
    ]
