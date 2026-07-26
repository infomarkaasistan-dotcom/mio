# Executive Domain (Faz 1 · Domain 1) — v1.0.0 · FROZEN

Stratejik karar verme · planlama · koordinasyon · delegasyon · hedef yönetimi · sistem orkestrasyonu.
Bounded context olarak çekirdek E1-E5'i **sarar** (değiştirmez).

## Public API (`ExecutiveDomain`)
| Operasyon | Açıklama | Yetki |
|---|---|---|
| `set_goal(actor, text, horizon_days)` | Uzun-vadeli hedef (E2→E1) | owner + brain |
| `abandon_goal(actor, goal_id, reason)` | Hedeften meşru vazgeçiş | owner-only |
| `decide(actor, DecisionCommand)` | Karar → E4 governance → E1 audit | owner + brain |
| `review(trigger)` | E3 stratejik review (goal/belief/evidence) | owner + brain |
| `introspect(decision_id)` | E5 bilişsel iç-gözlem | owner + brain |
| `status()` | Executive state snapshot | owner + brain |
| `set_mission/set_purpose(actor, ...)` | Kimlik/amaç (sürümlü) | owner-only |
| `metrics()` / `contract()` | Observability + versioned sözleşme | — |

## Bileşenler (production-grade, placeholder YOK)
- **Domain modeli + iş kuralları:** E1-E5 + authorization (owner-only ops), validation, karar-audit zorunluluğu.
- **API + Contract:** `contract.py` (versioned v1.0.0, operations, events, invariants).
- **Events (event-driven):** `executive.goal.set/abandoned`, `executive.decision.made`, `executive.review.completed`, `executive.mission/purpose.set` → EventBus.
- **Policy + Governance:** her karar E4 `GovernanceEngine`'den geçer.
- **Audit:** kararlar E1 DecisionLedger'a (gerekçe+skor) yazılır.
- **Security/Authorization:** `ExecutiveConfig.is_authorized` (owner + kayıtlı 14 brain; mission/purpose/abandon owner-only).
- **Versioning/backward-compat:** contract_version 1.0.0; E1-E5 imzaları değişmedi.
- **Validation + Error handling:** `ValidationError/UnauthorizedError/NotFoundError` (ExecutiveError hiyerarşisi).
- **Observability:** metrics sayaçları + logging + event yayını.
- **Configuration:** `ExecutiveConfig` (owner, authorized_actors, owner_only_ops, sınırlar).
- **Repository:** E1 SQLite store (kalıcı).

## Testler
`tests/test_executive_domain.py` — unit (validation/authorization/kural) + integration (E1-E5 uçtan uca + events) + smoke (boot→domain akışı). Tümü `python -m pytest`.

## Bağımlılıklar (DI)
`ExecutiveDomain(state, goals, governance, review, cognitive_identity, bus, config)` — hepsi enjekte;
`runtime.boot()` bağlar (`mio.executive`).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`). Değişiklik yalnız sürüm artışı + backward-compat ile.
