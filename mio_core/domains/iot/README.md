# IoT Domain (Faz 4 · Domain 34) — Maturity: STABLE

> Constitution refs: Madde 24 (Autonomous Execution Governance — geri-alınamaz aktüatör aksiyonu onay ister),
> Madde 6/7 (dış sistem adapter üzerinden), Madde 8 (dürüstlük), Madde 11 (Hardware Operations), Madde 16.
> **Compliance: FULLY COMPLIANT (kapsam içi).** Faz 4'ün SON domaini.

IoT erişimi gerçek **broker/protokol (MQTT/CoAP/HTTP/Zigbee)** + fiziksel cihaz gerektirir → deterministik
**ORKESTRASYON**: thing (sensör/aktüatör/gateway) registry + **telemetri alım + eşik-tabanlı uyarı**
(deterministik, LLM'siz) + aktüatör **komut durum makinesi** (pending→running→completed/failed/**no_connector**/
**requires_approval**) + connector routing (protokole göre) + **risk sınıflandırma**. **Yüksek-risk/geri-alınamaz
aktüatör komut ONAY ister** (Madde 24); onaysız çalışmaz. **Sensör komut kabul etmez** (invariant). Gerçek
protokol/cihaz erişimi enjekte edilen **connector (adapter)**'a delege. **Connector yoksa `no_connector`**
(Madde 8). Protokol/donanım erişimi **çekirdekte yok**.

## Public API (`IoTDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_connector(protocol, fn, name)` | GERÇEK broker/cihaz connector'ı bağla (DI; mqtt/coap/http/zigbee) |
| `register_thing(actor, name, kind, protocol)` | Thing kaydı (sensor/actuator/gateway) |
| `ingest(actor, thing_id, metric, value, unit)` | Telemetri okuması → kaydet + **deterministik eşik değerlendir** |
| `add_alert_rule(actor, thing_id, metric, comparator, threshold)` | Eşik kuralı (`> >= < <= == !=`) |
| `send_command(actor, thing_id, command, params, risk, user_approved)` | Aktüatör komut → high+onaysız `requires_approval` |
| `approve_command(actor, job_id)` | Onay bekleyen yüksek-risk komutu onayla+çalıştır (**owner/Executive**) |
| `readings / latest / alerts / get_command / list_commands / list_things / connectors / stats / contract` | Sorgu + sözleşme |

## Telemetri & uyarı (deterministik · LLM'siz)
`ingest` her okumada eşleşen kuralları değerlendirir; `COMPARATORS[comparator](value, threshold)` **True** ise
**Alert** kaydı + `alert_triggered` olayı üretir. Karar tamamen deterministik — LLM yok.

## Güvenlik (Madde 24 · deterministik)
`classify_risk`: bildirilen `risk=high` **veya** komut tehlikeli işaret içeriyorsa (`unlock/open/disable/override/
shutdown/reboot/reset/wipe/factory/erase/kilit/aç/kapat/sıfırla/sil/devre dışı`) → **high**. Yüksek-risk +
`user_approved=False` → **`requires_approval`** (çalıştırılmaz). Onay yalnız **owner/Executive**.

## Invariantlar
- **Delege:** gerçek protokol/cihaz adapter'a gider; çekirdek erişim yapmaz.
- **Sensör ≠ komut:** yalnız actuator/gateway komutlanır (sensör `ValidationError`).
- **Onay şart (Madde 24):** yüksek-risk aktüatör komut onaysız EXECUTED olmaz.
- **Dürüstlük (Madde 8):** connector yoksa `no_connector`; uydurma sonuç yok.
- **Deterministik telemetri:** eşik değerlendirmesi LLM'siz.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Perception/Reasoning/Planning. Yazma/komut: owner + Executive/
Operations/Engineering. **Onay: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Thing/Reading/AlertRule/Alert/CommandJob + risk classifier + comparators) · Repository (SQLite; thing/
reading/alert_rule/alert/iot_command) · Contract v1.0.0 · Events (thing_registered/telemetry_ingested/
alert_rule_added/alert_triggered/command_created/completed/failed/no_connector/approval_required/approved) ·
Authorization (approver ayrımı) · Validation · Error hiyerarşisi · Observability (metrics+events) · Config ·
Unit+Integration+Smoke (`tests/test_iot_domain.py`) · Docs.

## Bağımlılıklar (DI)
`IoTDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.iot`). Gerçek connector'lar sonradan
`register_connector` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek protokol/cihaz connector'ı bağlı
değil (`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
