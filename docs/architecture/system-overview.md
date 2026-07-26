# MIO — System Overview (Reference Architecture)

> Constitution refs: Madde 40 (Reference Architecture zorunlu), Governance Extensions §2 (Platform Invariants),
> §4 (Bounded Context Isolation). Bu belge platformun bütününü tanımlar; ilkeler için `docs/constitution/`.

## Platform Context

```
                 ┌─────────────────────────────────────────────┐
   İnsan  ◀──────▶│  Communication Domain  (diyalog arayüzü)     │
 (nihai otorite) └───────────────┬─────────────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
   Dış sinyaller ──▶│  Perception Domain        │──▶ E5 belief / Memory / Attention
   (event/metric)  └────────────┬─────────────┘
                                 │
   ┌─────────────────────────────▼──────────────────────────────┐
   │  EXECUTIVE  (E1–E5)  — stratejik karar & orkestrasyon        │  ◀── Policy (PDP) · Security (RBAC)
   │  Goal · Review · Decision/Governance · Cognitive Engine     │
   └───┬───────────────┬───────────────┬───────────────┬────────┘
       │               │               │               │
  Reasoning       Planning        Knowledge          Memory      Learning   Goal Mgmt
   (deduce/         (deterministik   (tipli + apply)  (WM/LTM/…)  (emergence) (hedef ağacı)
    deliberate)      topo sıralama)
       │
       ▼
   ┌───────────────────────────────────────────────────────────┐
   │  Vertical Domain Brains (8): Finance/Marketing/Sales/…      │  → tavsiye üretir, KARAR VERMEZ
   └───────────────────────────────────────────────────────────┘
       │  (onaylı plan/karar)
       ▼
   ┌───────────────────────────────────────────────────────────┐
   │  Execution Domain  → Tool Orchestrator → Capabilities/MCP   │  (yürütme yetkilendirme ister)
   └───────────────────────────────────────────────────────────┘
       │
       ▼  (dış sistemler yalnız Operation Domain üzerinden — hiçbir zaman doğrudan Executive'e)
   [ Operation Domains: Marketplace/Marketing/Finance/… → Connector/Adapter → Trendyol/Google Ads/… ]

  Kesişen omurga:  EventBus  ·  Scheduler/Lifecycle  ·  Observability  ·  Policy  ·  Security  ·  Audit
```

## Domain Map (mevcut, 15 FROZEN)
Cognitive Core: Executive · Memory · Knowledge · Reasoning · Planning · Learning · Goal Management.
Etkileşim/Yürütme: Communication · Execution · Perception. Dikey: Vertical Domain Brains (8). Altyapı:
Scheduler · Observability · Policy · Security. Hedef harita: `../roadmap/PLATFORM_ROADMAP.md`.

## Executive Flow (özet)
`Algı/Talep → Executive değerlendirir → (Knowledge.apply + Reasoning + Vertical advice) → Policy/E4/Security
gate → Planning → Execution (onaylı) → Learning (outcome) → Memory/Knowledge güncellenir → Observability
gözler`. Her adım deterministik; LLM yalnız danışman (Model Gateway/orchestrator).

## Event Flow
Tüm domainler `EventBus`'a versiyonlu event publish eder. Observability `subscribe_all` ile pasif dinler
(tüm domainleri tek noktadan kapsar). Dashboard/API (gelecek) yalnız subscribe eder → backend değişmeden UI
eklenebilir.

## Memory / Knowledge Architecture
Memory Domain: WM/STM/LTM/episodik/semantik/prosedürel + konsolidasyon/çürüme. Knowledge Domain: tipli
bilgi (belief/rule/concept/pattern/principle/mental_model/reasoning_template/decision_heuristic) + bağlama
**deterministik `apply`** (LLM'siz karar üretimi). Unified Knowledge hedefi: Madde 25.

## Model Orchestration Architecture
LLM = değiştirilebilir uzman araç (Governance Extensions §9). `Model Gateway` sağlayıcıları soyutlar;
`Tool Orchestrator` tek geçiş noktasıdır (governance + audit). LLM bağlı değilse sistem deterministik çalışır.

## Security / Governance Architecture
Policy Domain (deterministik PDP: allow/deny/require_approval) + Security Domain (RBAC + append-only audit +
redact + lockout) + E4 Governance (karar verdict'i) + Vertical guardrail'ler. Katmanlı, birbirini tamamlar.

## Deployment (bilgi)
stdlib-only çekirdek; her domain kendi SQLite write-through deposu (`.mio/*.db`, WAL). Teknoloji seçimleri
Constitution'ın parçası değildir (Governance Extensions §8); bu bölüm Reference Architecture seviyesindedir.
