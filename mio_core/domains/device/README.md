# Device & Native Integration Domain (Faz 4 · Domain 33) — Maturity: STABLE

> Constitution refs: Madde 24 (Autonomous Execution Governance — geri-alınamaz aksiyon onay ister), Madde 6/7
> (dış sistem adapter üzerinden), Madde 8 (dürüstlük), Madde 11 (Hardware Operations), Madde 16. **Compliance:
> FULLY COMPLIANT (kapsam içi).**

Native/donanım erişimi gerçek **OS/aygıt** gerektirir → deterministik **ORKESTRASYON**: device registry +
komut durum makinesi (pending→running→completed/failed/**no_connector**/**requires_approval**) + connector
routing + **risk sınıflandırma**. **Yüksek-risk/geri-alınamaz komut ONAY ister** (Madde 24); onaysız çalışmaz.
Gerçek erişim enjekte edilen **handler (adapter)**'a delege. **Handler yoksa `no_connector`** (Madde 8). Donanım
erişimi **çekirdekte yok**.

## Public API (`DeviceNativeDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_handler(kind, fn, name)` | GERÇEK OS/donanım connector'ı bağla (DI; os/filesystem/peripheral) |
| `register_device(actor, name, kind)` | Aygıt kaydı |
| `execute(actor, device_id, operation, params, risk, user_approved)` | Komut → risk<high çalışır, high+onaysız `requires_approval` |
| `approve_command(actor, job_id)` | Onay bekleyen yüksek-risk komutu onayla+çalıştır (**owner/Executive**) |
| `get_job / list_jobs / list_devices / connectors / stats / contract` | Sorgu + sözleşme |

## Güvenlik (Madde 24 · deterministik)
`classify_risk`: bildirilen `risk=high` **veya** operasyon tehlikeli işaret içeriyorsa (`delete/format/shutdown/
reboot/wipe/rm/kill/sil/biçimlendir/kapat`) → **high**. Yüksek-risk + `user_approved=False` → **`requires_approval`**
(çalıştırılmaz). Onay yalnız **owner/Executive**.

## Invariantlar
- **Delege:** gerçek OS/donanım adapter'a gider; çekirdek erişim yapmaz.
- **Onay şart (Madde 24):** yüksek-risk komut onaysız EXECUTED olmaz.
- **Dürüstlük (Madde 8):** handler yoksa `no_connector`; uydurma sonuç yok.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Perception/Reasoning/Planning. Komut: owner + Executive/
Operations/Engineering. **Onay: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Device/CommandJob + risk classifier) · Repository (SQLite) · Contract v1.0.0 · Events (registered/
command_created/completed/failed/no_connector/approval_required/approved) · Authorization (approver ayrımı) ·
Validation · Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_device_domain.py`) · Docs.

## Bağımlılıklar (DI)
`DeviceNativeDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.device`). Gerçek handler'lar
sonradan `register_handler` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek OS/donanım connector'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
