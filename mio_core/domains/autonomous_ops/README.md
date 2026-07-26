# Autonomous Operations Domain (Faz 5 · Domain 41) — Maturity: STABLE

> Constitution refs: **Madde 3/4 (Executive tek karar verici; alt birim tek başına karar vermez)**, Madde 24
> (öneri uygulaması onay ister), Madde 8 (dürüstlük), Madde 16. **Compliance: FULLY COMPLIANT (kapsam içi).**
> Anayasa'nın EN HASSAS noktası: **autonomy ≠ otonom karar.**

**Anayasa gereği otonom aksiyon KARAR VERMEZ; Executive'e ÖNERİ (recommendation) üretir; uygulama Madde 24
onayıyla.** Çekirdek: operasyon kuralı (rule) registry (izle→değerlendir→öner) + **deterministik tetik/koşul
değerlendirme** (metrik eşiği; LLM'siz) + öneri üretimi + aksiyon durum makinesi (requires_approval→executed/
rejected/failed/**no_connector**). **Kapalı-döngü otomasyon YALNIZ açıkça allowlisted güvenli aksiyonlarda +
`closed_loop_enabled` açıkken** (opt-in; **varsayılan kapalı = güvenli**; her tetik öneri kalır). Aksiyon yürütme
enjekte edilen **action adapter (DI)**'a delege. **Adapter yoksa `no_connector`** (Madde 8). İnsan/Executive
gözetimi **zorunlu**. Gerçek yürütme **çekirdekte yok**.

## Public API (`AutonomousOperationsDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_action(action, fn, name)` | GERÇEK aksiyon yürütme connector'ı bağla (DI) |
| `add_rule(actor, name, metric, comparator, threshold, action, severity, enabled)` | İzle→öner kuralı |
| `observe(actor, metric, value)` | Deterministik değerlendir → tetikleneni **ÖNERİYE** dönüştür (Madde 24) |
| `approve_proposal(actor, proposal_id)` | Öneriyi onayla+uygula (**owner/Executive**) |
| `reject_proposal(actor, proposal_id, reason)` | Öneriyi reddet (approver) |
| `get_proposal / list_proposals / list_rules / actions / stats / contract` | Sorgu + sözleşme |

## Deterministik tetik (Madde 3 · LLM'siz)
`observe` her metrikte eşleşen **enabled** kuralları değerlendirir; `COMPARATORS[comparator](value, threshold)`
**True** ise **Proposal** (öneri) üretir — varsayılan `requires_approval`. Karar tamamen deterministik; LLM yok.

## Kapalı-döngü sınırı (autonomy ≠ karar · Madde 24)
`AutoOpsConfig.may_auto_execute(action) = closed_loop_enabled AND action ∈ safe_actions`. Yani otomatik yürütme
**yalnız** operatörün açıkça güvenli-allowlist'e koyduğu aksiyonlarda ve ana anahtar açıkken olur. Diğer her tetik
Executive'e **öneri** kalır (`requires_approval`) — onaysız yürütülmez.

## Invariantlar
- **Karar değil öneri:** otonom aksiyon karar vermez; Executive'e recommendation üretir.
- **Onay şart (Madde 24):** öneri uygulaması owner/Executive onayı ister.
- **Güvenli varsayılan:** `closed_loop_enabled=False` → her tetik öneri kalır.
- **Kapalı-döngü kısıtı:** yalnız allowlisted güvenli aksiyon + opt-in.
- **Dürüstlük (Madde 8):** action adapter yoksa `no_connector`; uydurma sonuç yok.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Planning/Reasoning/Perception. Kural/gözlem: owner + Executive/
Operations/Engineering. **Onay/Red: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (OpsRule/Proposal + COMPARATORS + `may_auto_execute` allowlist mantığı) · Repository (SQLite; ops_rule/
proposal) · Contract v1.0.0 · Events (rule_added/proposal_created/auto_executed/approved/rejected/executed/failed/
no_connector) · Authorization (approver ayrımı) · Validation · Error hiyerarşisi · Observability (metrics+events) ·
Config (safe_actions allowlist + closed_loop switch) · Unit+Integration+Smoke
(`tests/test_autonomous_ops_domain.py`) · Docs.

## Bağımlılıklar (DI)
`AutonomousOperationsDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.autonomous_operations`).
Gerçek action'lar `register_action` ile; güvenli-allowlist + kapalı-döngü anahtarı `AutoOpsConfig` ile (varsayılan
kapalı = güvenli).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek aksiyon adapter'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
