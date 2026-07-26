# Federation Domain (Faz 5 · Domain 39) — Maturity: STABLE

> Constitution refs: **Madde 24 (dış düğümle paylaşım onay ister; egemenlik/gizlilik korunur)**, Madde 6/7 (uzak
> düğüm adapter üzerinden), Madde 8 (dürüstlük), Madde 16. **Compliance: FULLY COMPLIANT (kapsam içi).**

**Anayasa gereği egemenlik/gizlilik korunur; dış düğümle paylaşım ONAY ister (Madde 24) ve DETERMİNİSTİK scope
sınırıyla kısıtlanır.** Çekirdek: eş (peer) düğüm registry (endpoint/güven/yetenek) + **deterministik federasyon
politikası** (host allowlist + izinli paylaşım kapsamı) + güven durum makinesi (registered→trusted→revoked) +
paylaşım job durum makinesi (pending→requires_approval→shared/failed/**no_connector**). Gerçek uzak düğüm çağrısı
enjekte edilen **transport adapter (DI)**'a delege. **Transport yoksa `no_connector`** (Madde 8). Gerçek ağ/uzak
yürütme **çekirdekte yok**. **Varsayılan allowlist boştur → varsayılan-güvenli** (hiçbir dış host kendiliğinden
güvenilir değildir).

## Public API (`FederationDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_transport(fn, name)` | GERÇEK uzak düğüm transport connector'ı bağla (DI) |
| `register_peer(actor, name, endpoint, capabilities, trust_level)` | Peer kaydı (REGISTERED) |
| `trust_peer(actor, peer_id, trust_level)` | **Madde 24** güven ver (owner/Executive); host allowlist dışıysa OTOMATİK reddeder |
| `revoke_peer(actor, peer_id)` | Güveni kaldır (approver) |
| `share(actor, peer_id, scope, payload, user_approved)` | Paylaşım isteği — TRUSTED peer + izinli scope; onaysız `requires_approval` |
| `approve_share(actor, share_id)` | Onay bekleyen paylaşımı onayla+gönder (**owner/Executive**) |
| `get_peer / list_peers / get_share / list_shares / scopes / stats / contract` | Sorgu + sözleşme |

## Deterministik federasyon politikası (Madde 24 · LLM'siz)
`FederationConfig.host_trusted`: peer endpoint host'u `trusted_hosts` allowlist'inde değilse güvenilir kılınamaz →
`trust_peer` OTOMATİK `revoked`. `scope_allowed`: yalnız `allowed_scopes` (egemenlik sınırı) dışarı paylaşılabilir;
diğer scope `share`'de `ValidationError`. Dış paylaşım **her zaman** onay ister (onaysız `requires_approval`).

## Güven & paylaşım durum makineleri
Peer: `registered → {trusted, revoked}` · `trusted → {revoked}` · `revoked` **terminal**. Paylaşım:
`pending → requires_approval → shared/failed/no_connector`. `approve_share` anında peer güveni **yeniden doğrulanır**
(revoke edilmişse gönderilmez).

## Invariantlar
- **Egemenlik (Madde 24):** dış düğüm yalnız allowlist host ise güvenilir; yalnız izinli scope paylaşılır.
- **Onay şart:** dış paylaşım onaysız gönderilmez; onay yalnız owner/Executive.
- **Deterministik politika:** LLM karar verici değil.
- **Dürüstlük (Madde 8):** transport yoksa `no_connector`; uydurma sonuç yok.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Planning/Reasoning. Kayıt/paylaşım: owner + Executive/Operations/
Engineering. **Güven/Revoke/Onay: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Peer/ShareJob + deterministik `host_trusted`/`scope_allowed` + PEER_TRANSITIONS) · Repository (SQLite;
peer/share_job) · Contract v1.0.0 · Events (peer_registered/trusted/rejected/revoked/share_requested/
approval_required/share_approved/shared/share_failed/no_connector) · Authorization (approver ayrımı) ·
Validation · Error hiyerarşisi (+ TransitionError) · Observability (metrics+events) · Config (allowlist+scope) ·
Unit+Integration+Smoke (`tests/test_federation_domain.py`) · Docs.

## Bağımlılıklar (DI)
`FederationDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.federation`). Gerçek transport
`register_transport` ile; allowlist/scope `FederationConfig` ile ayarlanır (varsayılan boş = güvenli).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek transport adapter'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
