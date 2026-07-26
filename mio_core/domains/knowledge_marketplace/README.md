# Knowledge Marketplace Domain (Faz 5 · Domain 38) — Maturity: STABLE

> Constitution refs: **Madde 24 (denetlenmemiş bilgi çekirdeğe/Knowledge Domain'e sokulamaz)**, Madde 6/7 (dış
> kaynak adapter üzerinden), Madde 8 (dürüstlük), Madde 27 (görünür hata), Madde 16. **Compliance: FULLY
> COMPLIANT (kapsam içi).**

**Anayasa gereği denetlenmemiş bilgi Knowledge Domain'e/çekirdeğe SOKULAMAZ.** Çekirdek: bilgi paketi (knowledge
pack) registry (fact-set/ontology/prompt-lib/skill) + yayıncı/sürüm/lisans/checksum + **deterministik kalite &
lisans & allowlist politikası** + import durum makinesi (submitted→approved/rejected→imported/removed) +
**provenance (kaynak izlenebilirlik) etiketi**. **Onay yalnız owner/Executive** (Madde 24); uyumsuz/lisanssız
**otomatik reddedilir**. Gerçek indirme/import enjekte edilen **kaynak adapter (DI)**'a delege. **Source yoksa
`no_connector`** (Madde 8). Import hatası **görünür** (`import_failed` — Madde 27). Gerçek indirme **çekirdekte
yok**. Marketplace/Ecosystem deseniyle simetrik; hedef = Knowledge Domain'e **güvenli + izlenebilir** bilgi.

## Public API (`KnowledgeMarketplaceDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_source(kind, fn, name)` | GERÇEK indirme/import connector'ı bağla (DI) |
| `submit_pack(actor, name, kind, publisher, version, license, source_uri, checksum, item_count)` | Paket gönder (SUBMITTED; deterministik ön-değerlendirme) |
| `check_compatibility(actor, pack_id)` | Deterministik uyumluluk raporu (salt-okunur) |
| `approve(actor, pack_id)` | **Madde 24** onay (owner/Executive); uyumsuzsa OTOMATİK reddeder |
| `reject(actor, pack_id, reason)` | Elle reddet (approver) |
| `import_pack(actor, pack_id)` | Yalnız APPROVED → kaynak adapter'a delege + **provenance** etiketi; yoksa `no_connector` |
| `remove / get_pack / list_packs / sources / stats / contract` | Kaldır + sorgu + sözleşme |

## Deterministik kalite & lisans (Madde 24 · LLM'siz)
`KnowledgeMarketConfig.evaluate`: `publisher ∈ trusted_publishers` **veya** kaynak host ∈ `trusted_sources` değilse
→ `untrusted_source`; `license ∉ allowed_licenses` → `license_not_allowed`; `require_checksum` açık ve checksum
yoksa → `missing_checksum`; geçersiz tür → `invalid_kind`. Boş gerekçe → **uyumlu**. `approve` uyumsuzu **otomatik
reddeder**.

## Provenance (izlenebilirlik · Madde 8)
Başarılı import'ta pack, `{publisher, source_uri, license, version, checksum, imported_at, approved_by}` provenance
etiketiyle işaretlenir — çekirdeğe giren her bilgi parçasının **kaynağı ve onaylayanı izlenebilir**.

## Yaşam-döngüsü durum makinesi
`submitted → {approved, rejected}` · `approved → {imported, removed, rejected}` · `imported → {removed}` ·
`rejected`/`removed` **terminal**. Import yalnız `approved`.

## Invariantlar
- **Denetim şart (Madde 24):** lisanssız/güvenilmez bilgi onaylanamaz (otomatik red).
- **Onay sahibi:** yalnız owner/Executive.
- **İzlenebilirlik:** import edilen bilgi provenance etiketiyle işaretlenir.
- **Dürüstlük (Madde 8):** source yoksa `no_connector`; **görünür hata (Madde 27):** `import_failed`.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Reasoning/Planning/Knowledge. Gönder/import/kaldır: owner +
Executive/Operations/Engineering/Knowledge. **Onay/Red: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (KnowledgePack + provenance + deterministik `evaluate` + lifecycle TRANSITIONS) · Repository (SQLite) ·
Contract v1.0.0 · Events (submitted/approved/rejected/imported/import_failed/no_connector/removed) ·
Authorization (approver ayrımı) · Validation · Error hiyerarşisi (+ TransitionError) · Observability
(metrics+events) · Config (allowlist+lisans) · Unit+Integration+Smoke
(`tests/test_knowledge_marketplace_domain.py`) · Docs.

## Bağımlılıklar (DI)
`KnowledgeMarketplaceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.knowledge_marketplace`).
Gerçek source'lar sonradan `register_source` ile bağlanır; lisans/allowlist `KnowledgeMarketConfig` ile ayarlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek kaynak/import adapter'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
