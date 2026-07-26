# Connector Adapters — GERÇEK dış sistem entegrasyonları

> `mio_core/connectors/adapters/` — Capability Adapter Layer'ın gerçek connector'ları. **stdlib-only** (urllib/
> smtplib/subprocess); çekirdek framework-bağımsız kalır. Her biri `CallableConnector` fabrikasıdır →
> `mio.connectors.register(...)`. Transport enjekte edilebilir → deterministik test.

## 4 kategori · connector'lar
| Kategori | Connector | capability | Doğrulama durumu (DÜRÜST) |
|---|---|---|---|
| System | **filesystem** | fs.read/write, files.read/write/list | ✅ **CANLI doğrulandı** (yerel fs, sandbox'lı) |
| System | **shell** | shell.exec | ✅ **CANLI doğrulandı** (subprocess) · yüksek-risk (Madde 24) |
| System | **git** | git.clone, git.status | ✅ **CANLI doğrulandı** (git varsa; yoksa health=False) |
| Communication | **smtp** | send_email | ✅ Gerçek kod + enjekte-transport testi (canlı: SMTP config) |
| Communication | **webhook** | send_message | ✅ Gerçek kod + enjekte test — Slack/Discord/Telegram/generic |
| AI (danışman) | **ollama** | ai.advise, ai.embed | ✅ Gerçek kod + enjekte test (canlı: localhost:11434) |
| AI (danışman) | **openai** | ai.advise | ✅ Gerçek kod + enjekte test — OpenAI/DeepSeek/Qwen (aynı şema) |
| Productivity | **caldav** | calendar.create_event/list_events | ✅ Gerçek kod + enjekte test (iCloud/Nextcloud/Fastmail) |

> **Dürüstlük:** System (filesystem/shell/git) CANLI doğrulandı. Ağ tabanlı olanlar **gerçek kod**tur ve
> enjekte-transport ile doğrulandı; **canlı bir servise karşı doğrulanmadı** (hesap/anahtar gerektirir) — config
> verildiğinde çalışır. Bu, doğrulanmamış-ama-çalışır kodun **dürüst** etiketidir (Madde 8).

## Bağlama (env'e göre)
```bash
python -m mio_core connect        # env'e göre yapılandırılmışları bağlar → {registered, skipped}
```
Varsayılan (config yok) → yalnız **filesystem** + **git** (güvenli/yerel). Diğerleri için `.env`:
```bash
MIO_SHELL_ENABLED=true                    # shell.exec (yüksek-risk; Madde 24 yine yürürlükte)
SMTP_HOST=smtp.gmail.com  SMTP_USER=..  SMTP_PASSWORD=..     # send_email (Gmail app-password)
MIO_WEBHOOK_URL=https://hooks.slack.com/... MIO_WEBHOOK_STYLE=slack   # send_message
LLM_ENABLED=true  OLLAMA_HOST=http://localhost:11434        # ai.advise (yerel, anahtarsız)
OPENAI_API_KEY=..  # veya DEEPSEEK_API_KEY / QWEN_API_KEY    # ai.advise (bulut)
CALDAV_URL=..  CALDAV_USER=..  CALDAV_PASSWORD=..           # calendar.*
```
`register_from_env` sır DEĞERİNİ asla döndürmez/loglamaz — yalnız bağlanan connector ADINI.

## Güvenlik / Anayasa
- **Filesystem sandbox:** tüm yollar `root` (varsayılan `<workspace>/files`) altına kısıtlanır; `..` traversal reddedilir.
- **Madde 24:** shell.exec / fs.write / files.write / docker.run / k8s.apply / github.pr onaysız çalışmaz
  (`requires_approval`); `user_approved=True` ile çalışır. Manager kapısı adapter'dan bağımsız yürürlüktedir.
- **Madde 1:** AI connector'lar (ollama/openai) DANIŞMAN — `advice` döndürür, KARAR VERMEZ.
- **Madde 8:** connector bağlı değil/sağlıksızsa `connector_unavailable`/`failed` (çökmez).
- **Madde 28:** aynı capability'yi birden çok connector sağlıyorsa öncelik + failover.

## Kullanım (capability ile, isimle değil)
```python
from mio_core.connectors.adapters import register_from_env
register_from_env(mio.connectors, workspace="/data/mio")
mio.connectors.execute("send_email", {"to": "a@b.com", "subject": "S", "body": "..."})
mio.connectors.execute("fs.write", {"path": "notes.txt", "content": "x"}, user_approved=True)   # Madde 24
mio.advisor.ask("özetle")     # → ai.advise (ollama/openai; hangisi bağlıysa)
```

Test: `tests/test_connector_adapters.py` (11) — System canlı, network enjekte-transport.
