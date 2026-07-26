"""MIO Core · Innate Knowledge — TİPLİ bilişsel yapılar (ADR-0002 Madde 5), LLM-BAĞIMSIZ.

Bilgi statik veri (JSON/kayıt) değildir; KARAR ÜRETMEK için kullanılan bilişsel yapılardır:
Belief · Rule · Concept · Pattern · Principle · Mental Model · Reasoning Template · Decision Heuristic.

Aktif tipler (Rule / Decision Heuristic / Pattern) bir BAĞLAMA `apply()` ile uygulanır → deterministik
sonuç/öneri üretir (LLM'e gerek kalmadan). Böylece MIO innate bilgisini "okumaz", KULLANIR — bu, aşırı
LLM bağımlılığını ve kısır döngüleri azaltan Born Capable ilkesinin özüdür.

Innate bilgi doğuşta tohumlanır (source="innate"). Yaşayarak öğrenilen bilgi zamanla E1 Lessons / E5
Beliefs (kalıcı) üzerinden birikir; bu modül innate tipli çekirdeği ve uygulama motorunu sağlar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .executive.models import new_id

__all__ = ["KnowledgeType", "KnowledgeItem", "Applied", "KnowledgeBase",
           "KNOWLEDGE_DOMAINS", "default_innate_knowledge"]


# ADR-0002 Madde 1 — ayrıştırılmış eğitim alanları (World Knowledge tek kavram değil).
KNOWLEDGE_DOMAINS = (
    "physical_world", "business", "economics", "finance", "marketing", "sales", "product",
    "software_engineering", "ai", "human_psychology", "decision_science", "systems_thinking",
    "legal_compliance", "security", "communication",
)


class KnowledgeType(str, Enum):
    BELIEF = "belief"
    RULE = "rule"                          # koşul → sonuç (uygulanabilir)
    CONCEPT = "concept"                    # tanım/kavram
    PATTERN = "pattern"                    # tekrarlayan durum → tipik yanıt (uygulanabilir)
    PRINCIPLE = "principle"                # yol gösterici ilke
    MENTAL_MODEL = "mental_model"          # bir alanı yorumlama merceği
    REASONING_TEMPLATE = "reasoning_template"   # yapılandırılmış muhakeme adımları
    DECISION_HEURISTIC = "decision_heuristic"   # karar için pratik kural (uygulanabilir)


_APPLICABLE = {KnowledgeType.RULE, KnowledgeType.PATTERN, KnowledgeType.DECISION_HEURISTIC}


@dataclass
class KnowledgeItem:
    ktype: KnowledgeType
    name: str
    statement: str = ""
    domain: str = "general"
    when: list[str] = field(default_factory=list)   # koşul etiketleri (hepsi bağlamda varsa uygulanır)
    then: str = ""                                   # sonuç/öneri (Rule/Pattern/Heuristic)
    steps: list[str] = field(default_factory=list)   # ReasoningTemplate adımları
    confidence: float = 0.7
    tags: list[str] = field(default_factory=list)
    source: str = "innate"
    id: str = field(default_factory=new_id)

    def applies_to(self, context_tags: set[str]) -> bool:
        return (self.ktype in _APPLICABLE and bool(self.when)
                and all(w in context_tags for w in self.when))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "ktype": self.ktype.value, "name": self.name, "statement": self.statement,
                "domain": self.domain, "when": list(self.when), "then": self.then, "steps": list(self.steps),
                "confidence": self.confidence, "tags": list(self.tags), "source": self.source}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "KnowledgeItem":
        return cls(ktype=KnowledgeType(d["ktype"]), name=d["name"], statement=d.get("statement", ""),
                   domain=d.get("domain", "general"), when=list(d.get("when") or []), then=d.get("then", ""),
                   steps=list(d.get("steps") or []), confidence=float(d.get("confidence", 0.7)),
                   tags=list(d.get("tags") or []), source=d.get("source", "innate"),
                   id=d.get("id") or new_id())


@dataclass
class Applied:
    item_id: str
    name: str
    recommendation: str
    confidence: float
    ktype: str


class KnowledgeBase:
    """Tipli innate bilgi tabanı. Bilgiyi tutar, getirir ve BAĞLAMA UYGULAR (karar üretir)."""

    def __init__(self) -> None:
        self._items: dict[str, KnowledgeItem] = {}

    def add(self, item: KnowledgeItem) -> KnowledgeItem:
        self._items[item.id] = item
        return item

    def add_all(self, items: list[KnowledgeItem]) -> int:
        for it in items:
            self.add(it)
        return len(items)

    def get(self, item_id: str) -> Optional[KnowledgeItem]:
        return self._items.get(item_id)

    def remove(self, item_id: str) -> bool:
        """Bir bilgi öğesini kaldırır (yaşayan bilgi için). Innate koruması çağıran katmanın sorumluluğundadır."""
        return self._items.pop(item_id, None) is not None

    def list(self, ktype: Optional[KnowledgeType] = None,
             domain: Optional[str] = None) -> list[KnowledgeItem]:
        out = list(self._items.values())
        if ktype is not None:
            out = [i for i in out if i.ktype == ktype]
        if domain is not None:
            out = [i for i in out if i.domain == domain]
        return out

    def retrieve(self, query: str, limit: int = 10) -> list[KnowledgeItem]:
        """'X hakkında ne biliyorum?' — isim/ifade/etiket eşleşen bilgi (deterministik, uydurma yok)."""
        kws = [w.lower() for w in query.split() if len(w) > 2]
        if not kws:
            return []
        scored = []
        for it in self._items.values():
            hay = (it.name + " " + it.statement + " " + " ".join(it.tags)).lower()
            score = sum(1 for k in kws if k in hay)
            if score:
                scored.append((score, it))
        scored.sort(key=lambda t: (t[0], t[1].confidence), reverse=True)
        return [it for _, it in scored[:limit]]

    def apply(self, context_tags: set[str]) -> list[Applied]:
        """Bağlama UYGULANABİLİR bilgiyi (Rule/Pattern/Heuristic) değerlendirir → öneriler (güvene göre sıralı).
        MIO'nun innate bilgisi burada KARAR ÜRETİR — LLM'e gerek kalmadan, deterministik."""
        out = [
            Applied(item_id=it.id, name=it.name, recommendation=it.then,
                    confidence=it.confidence, ktype=it.ktype.value)
            for it in self._items.values() if it.applies_to(context_tags)
        ]
        out.sort(key=lambda a: a.confidence, reverse=True)
        return out

    def count(self, ktype: Optional[KnowledgeType] = None) -> int:
        return len(self.list(ktype=ktype))

    def learned(self) -> list[KnowledgeItem]:
        """Yaşayarak öğrenilen (innate olmayan) bilgi — kalıcılığa yazılan kısım."""
        return [i for i in self._items.values() if i.source != "innate"]

    def import_items(self, dicts: list[dict[str, Any]]) -> int:
        for d in dicts or []:
            self.add(KnowledgeItem.from_dict(d))
        return len(dicts or [])


def _k(ktype, name, **kw) -> KnowledgeItem:
    return KnowledgeItem(ktype=ktype, name=name, **kw)


def default_innate_knowledge() -> list[KnowledgeItem]:
    """MIO'nun DOĞUŞTAN gelen tipli bilgi çekirdeği (eğitim, deneyim değil). 14 alana yayılır; Purpose ile
    uyumlu. Aktif tipler (Rule/Heuristic/Pattern) bağlama uygulanır → deterministik öneri."""
    K = KnowledgeType
    return [
        # --- Governance / Finance (Purpose ile uyumlu, aktif) ---
        _k(K.RULE, "finansal-onay-kuralı", domain="finance",
           statement="Kullanıcı onayı olmadan finansal yükümlülük oluşturulamaz.",
           when=["financial_commitment", "no_user_approval"],
           then="Reddet / kullanıcı onayı iste (Financial Rule).", confidence=0.98),
        _k(K.DECISION_HEURISTIC, "önce-ücretsiz", domain="finance",
           statement="Yeni bir maliyet doğmadan önce ücretsiz/mevcut alternatif aranır.",
           when=["new_expense"], then="Önce ücretsiz/mevcut kaynak alternatifini araştır.", confidence=0.85),
        # --- Strateji (aktif) ---
        _k(K.DECISION_HEURISTIC, "otomasyon-önce", domain="systems_thinking",
           statement="Tekrarlayan iş, insan-emeğiyle değil otomasyonla çözülür.",
           when=["repetitive_task"], then="Otomasyon çözümünü tercih et.", confidence=0.8),
        _k(K.PATTERN, "soğuk-lead-değer-önce", domain="sales",
           statement="Soğuk potansiyel müşteride doğrudan satış değil, önce değer sunulur.",
           when=["cold_lead"], then="Değer-önce yaklaşım uygula, doğrudan satıştan kaçın.", confidence=0.75),
        _k(K.RULE, "geri-alınamaz-koruma", domain="security",
           statement="Geri-alınamaz/dış aksiyon onay ve geri-alınabilirlik kontrolü ister.",
           when=["irreversible_action"], then="Executive onayı + geri-alınabilirlik değerlendir.", confidence=0.9),
        # --- Kavram / İlke / Mental Model (referans) ---
        _k(K.CONCEPT, "sürdürülebilir-gelir", domain="business",
           statement="Sürdürülebilir gelir: tekrarlayan, öngörülebilir gelir akışı; tek-seferlikten üstündür.",
           tags=["gelir", "büyüme"]),
        _k(K.PRINCIPLE, "para-harcamak-çözüm-değil", domain="finance",
           statement="Para harcamak çözüm değildir; önce bilgi, otomasyon, ücretsiz yöntemler, mevcut kaynaklar.",
           tags=["maliyet", "sermaye"]),
        _k(K.MENTAL_MODEL, "sistem-düşüncesi", domain="systems_thinking",
           statement="Parçalar değil; ilişkiler, geri-besleme döngüleri ve kaldıraç noktaları belirleyicidir.",
           tags=["strateji"]),
        _k(K.CONCEPT, "değer-önerisi", domain="marketing",
           statement="Değer önerisi: hedef kitleye sağlanan somut fayda ile rakiplerden ayrışma.",
           tags=["pazarlama", "konumlandırma"]),
        _k(K.CONCEPT, "nakit-akışı", domain="finance",
           statement="Pozitif nakit akışı işletmenin hayatta kalması için kâr'dan daha önceliklidir.",
           tags=["finans"]),
        # --- Muhakeme şablonu (referans) ---
        _k(K.REASONING_TEMPLATE, "karar-muhakemesi", domain="decision_science",
           statement="Bir kararı değerlendirme adımları.",
           steps=["Hedefe hizmet ediyor mu?", "Kanıt yeterli mi?", "Risk nedir?",
                  "İlkelerle uyumlu mu?", "Alternatifler nelerdir?", "Geri-alınabilir mi?"]),
        _k(K.PRINCIPLE, "dürüstlük", domain="communication",
           statement="Yapamadığını yapabiliyormuş gibi gösterme; 'bağlı değil/bilmiyorum' meşrudur.",
           tags=["dürüstlük"]),
    ]
