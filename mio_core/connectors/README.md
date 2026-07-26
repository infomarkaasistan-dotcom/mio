# Capability Adapter Layer (Connector) — Maturity: STABLE

> Constitution refs: **Madde 1 (AI DANIŞMAN, karar verici değil)**, Madde 8 (connector yoksa çökmez — dürüst
> unavailable), Madde 15/16 (Executive'e kod gömülmez; adapter), Madde 24 (yüksek-risk onay), Madde 28
> (failover). **Compliance: FULLY COMPLIANT.**

```
Executive
     │  execute(capability, request)   ← Executive YALNIZ bunu bilir
Connector Manager                       ← hangi connector çalışacağına O karar verir (Executive değil)
 ┌────┬──────────────┬──────────────┬────────────┐
 AI   Communication   Productivity    System
(danışman)  SMTP/Slack   Calendar/Drive  Shell/Docker/K8s/Git
```

**Executive isimle değil CAPABILITY ile çağırır** (`send_email`, `gmail.send()` DEĞİL). Böylece ileride connector
değiştirmek gerekmez — capability sabit, sağlayıcı değişir. **Connector bağlı değilse sistem ÇÖKMEZ** → dürüst
`connector_unavailable`; Executive çalışmaya devam eder. **AI connector'lar DANIŞMAN'dır** (`advisor.ask()` →
Ollama/OpenAI/Gemini/Claude; Executive asla `openai.chat()` görmez; danışman KARAR VERMEZ).

## Katmanlar
| Bileşen | Sorumluluk |
|---|---|
| **ConnectorRegistry** | Hangi connector yüklü, hangi capability, öncelik, health. `providers_for(cap)` öncelik sırasıyla |
| **ConnectorManager** | `execute(capability, request)` → dispatch (priority+health) + **failover** + graceful degradation + Madde 24 |
| **Advisor** | `ask()`/`embed()` → AI capability; LLM danışman yüzeyi (karar vermez) |
| **CallableConnector** | Dış sisteme ADAPTER: `{capability: fn}` + kategori + öncelik + health |

## 4 Kategori
`ai` (Ollama/OpenAI/Gemini/Claude — danışman) · `communication` (SMTP/Gmail/Slack/Discord/WhatsApp/Telegram) ·
`productivity` (Calendar/Outlook/Drive/OneDrive/Dropbox) · `system` (Shell/Filesystem/Docker/Kubernetes/Git/GitHub).

## Dispatch (DETERMİNİSTİK, LLM'siz)
`providers_for(capability)` → `(priority↓, name↑)`. Sağlıklı olanlar öne alınır; ilk uygun çalışır. Patlarsa bir
sonrakine **failover** (Madde 28). Tümü başarısızsa `failed` (yine çökmez). Sağlayan yoksa `connector_unavailable`.

## Sonuç (execute — ASLA raise etmez)
`{"ok", "status": executed|connector_unavailable|requires_approval|failed, "capability", "connector"?, "result"?,
"message"?, "errors"?}`.

## Madde 24 (yüksek-risk)
`HIGH_RISK_CAPABILITIES` (shell.exec/fs.write/files.write/docker.run/k8s.apply/github.pr) onaysız →
`requires_approval` (çalışmaz); `user_approved=True` (owner/Executive assert'i) → çalışır.

## Kullanım
```python
mio.connectors.register(CallableConnector("smtp", "communication",
    handlers={"send_email": lambda req: smtp_send(req)}, priority=100))
mio.connectors.execute("send_email", {"to": "a@b.com", "subject": "..."})   # capability ile
mio.advisor.ask("özetle")                                                    # LLM danışman
```
CLI: `connectors` · `capabilities` · `execute <cap> {json}`. HTTP: `GET /connectors` · `GET /capabilities` ·
`POST /capabilities/{cap}` (?actor=&approved=). CLI+HTTP **aynı appservice**'i kullanır (iş mantığı kopyalanmaz).

## Bağımlılıklar (DI)
`ConnectorManager(ConnectorRegistry(), bus)` — `runtime.boot()` bağlar (`mio.connectors`, `mio.connector_registry`,
`mio.advisor`). Gerçek connector'lar `mio.connectors.register(...)` ile sonradan bağlanır. Gerçek dış sistem erişimi
**çekirdekte yok** (adapter'da).

## Durum: **STABLE** — üretim-doğrulanmış DEĞİL; gerçek connector adapter'ı bağlı değil (`connector_unavailable` =
**dürüst** durum, placeholder değil). `tests/test_connectors.py` (8).
