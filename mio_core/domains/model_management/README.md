# Model Management Domain (Faz 5 · Domain 35) — Maturity: STABLE

> Constitution refs: **Madde 1 (LLM değiştirilebilir danışmandır, karar verici DEĞİL)**, Madde 24 (retire =
> yetenek kaybı → onay), Madde 6/7 (dış sağlayıcı adapter üzerinden), Madde 8 (dürüstlük), Madde 16.
> **Compliance: FULLY COMPLIANT (kapsam içi).** Faz 5'in ilk domaini.

**Anayasa gereği model seçimi DETERMİNİSTİK bir politikadır; LLM yalnız danışmandır.** Çekirdek: model registry +
sürüm + **yaşam-döngüsü durum makinesi** (registered→available→deprecated→retired) + **deterministik seçim
politikası** (priority↑, context↑, cost↓, name tie-break) + sağlayıcı connector routing. Gerçek indirme/serve
enjekte edilen **provider adapter (DI)**'a delege. **Provider yoksa `no_connector` → model `available` OLMAZ**
(Madde 8). Provider hatası **görünür** (`provision_failed` — Madde 27). Model **çalıştırma çekirdekte yok**.

## Public API (`ModelManagementDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_provider(provider, fn, name)` | GERÇEK indirme/serve connector'ı bağla (DI) |
| `register_model(actor, name, kind, provider, location, version, context_window, cost_per_1k, priority)` | Model kaydı (REGISTERED) |
| `provision(actor, model_id)` | Provider'a delege → AVAILABLE; yoksa `no_connector` (REGISTERED kalır) |
| `select(actor, kind, min_context, location, provider)` | **DETERMİNİSTİK** seçim — yalnız AVAILABLE, en iyi skor |
| `deprecate / reactivate` | Yaşam-döngüsü geçişleri (AVAILABLE↔DEPRECATED) |
| `retire(actor, model_id)` | Emekliye ayır — **owner/Executive onayı** (Madde 24); değilse `requires_approval` |
| `get_model / list_models / providers / stats / contract` | Sorgu + sözleşme |

## Deterministik seçim (Anayasa Madde 1 · LLM'siz)
`select` yalnız **AVAILABLE** modelleri değerlendirir; kısıtları (min_context/location/provider) sağlayanlar
arasından `selection_score = (priority, context_window, -cost_per_1k, name)` en büyüğünü seçer. **Aynı girdi →
aynı sonuç.** LLM bu kararı VERMEZ; yalnız operatör politikası (priority) ve ölçülebilir özellikler belirler.

## Yaşam-döngüsü durum makinesi
`registered → {available, retired}` · `available → {deprecated, retired}` · `deprecated → {available, retired}`
· `retired` **terminal**. Geçersiz geçiş → `TransitionError`. Yalnız `available` seçilebilir.

## Invariantlar
- **Model seçimi deterministik** (LLM karar verici değil — Madde 1).
- **Dürüstlük (Madde 8):** provider yoksa `no_connector`; model `available` olmaz; seçim `None`.
- **Görünür hata (Madde 27):** provider hatası `provision_failed` olayı + dönüş `reason=failed`.
- **Retire onayı (Madde 24):** kalıcı devre dışı owner/Executive onayı ister.

## Yetki
Okuma/seçim: owner + Executive/Operations/Engineering/Reasoning/Planning/Perception. Yönetim (register/provision/
deprecate): owner + Executive/Operations/Engineering. **Retire: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Model + deterministik `selection_score` + lifecycle TRANSITIONS) · Repository (SQLite) · Contract v1.0.0 ·
Events (registered/provisioned/provision_failed/no_connector/selected/deprecated/reactivated/
retire_approval_required/retired) · Authorization (approver ayrımı) · Validation · Error hiyerarşisi (+
TransitionError) · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_model_management_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ModelManagementDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.model_management`). Gerçek
provider'lar sonradan `register_provider` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek provider adapter'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
