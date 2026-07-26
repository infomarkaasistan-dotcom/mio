# Policy Domain (Faz 4 · Domain 14) — v1.0.0 · FROZEN

Merkezî, sürümlü, **sorgulanabilir** bir deterministik **Policy Decision Point (PDP)**. Herhangi bir domain
bir aksiyon+bağlam için `evaluate` çağırır, tek deterministik verdict alır. Anayasa'yı yansıtan **innate
politikalarla doğar** (değiştirilemez). E4 (karar verdict'i) ve vertical guardrail'lerini **tamamlar** —
yerine geçmez; farkı: merkezî, veri-driven, çalışırken düzenlenebilir politika kümesi.

## Çözüm (deterministik)
Eşleşen politikalar (`scope` uyar + tüm `conditions` bağlamda) arasında efekt önceliği: **DENY > REQUIRE_APPROVAL
> ALLOW**; eşitlikte yüksek `priority`. Hiç eşleşme yoksa `default_effect` (ALLOW). `deny` bypass edilemez;
`require_approval` yalnız `user_approved=True` ile geçer.

## Doğuştan (anayasal) politikalar
- `financial-commitment-approval` — `financial_commitment` → **require_approval** (Financial Rule).
- `new-expense-approval` — `new_expense` → **require_approval** (para harcamak çözüm değildir).
- `irreversible-approval` — `irreversible_action` → **require_approval** (Executive onayı + geri-alınabilirlik).

## Public API (`PolicyDomain`)
| Operasyon | Açıklama |
|---|---|
| `evaluate(actor, action, context_tags, user_approved)` | Deterministik verdict (allow/deny/require_approval) |
| `define_policy(actor, name, effect, conditions, scope, priority, description)` | Özel politika (admin) |
| `remove_policy / set_enabled` | Yönetim (admin; innate değiştirilemez) |
| `list_policies / get_policy / stats / contract` | Sorgu + observability + sözleşme |

## Yetki
Değerlendirme/okuma: owner + Executive/Planning/Operations/Workflow/Security/Finance/Engineering/Communication.
Yönetim (define/remove/toggle): **admin** = owner + Executive + Security.

## Invariantlar
- **Deterministik:** aynı politika kümesi + bağlam → aynı verdict.
- **Innate korunur:** anayasal politika silinemez/devre dışı bırakılamaz.
- **deny bypass edilemez; require_approval yalnız onayla geçer.**

## Production bileşenleri (placeholder YOK)
Model (Policy + innate seed) · Repository (SQLite write-through) · Contract v1.0.0 · Events (defined/removed/
toggled/evaluated/gated) · Authorization (admin ayrımı) · Validation · Error hiyerarşisi · Observability
(metrics+events) · Config · Unit+Integration+Smoke (`tests/test_policy_domain.py`) · Docs.

## Bağımlılıklar (DI)
`PolicyDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.policy`), innate politikalarla doğar.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
