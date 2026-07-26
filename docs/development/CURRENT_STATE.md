# MIO — CURRENT STATE

> **Yeni oturum başlangıç noktası burasıdır** (Constitution Madde 17). Mimariyi yeniden analiz etmeden önce
> bu dosyayı + `NEXT_STEPS.md` + son `SESSION_LOG.md` girdisini oku.

| | |
|---|---|
| **Son güncelleme** | 2026-07-25 |
| **Platform sürümü** | MIO Platform v1.0 (Constitution v1.0 ratified) |
| **Test durumu** | ✅ 454 / 454 yeşil (`uv run --python 3.12 --with pytest pytest -q`) |
| **Platform maturity** | **STABLE** — tasarım-tam, deterministik, test-kaplı; **üretim-doğrulanmış DEĞİL** (bkz. `MATURITY_AUDIT.md`) |
| **Constitution Compliance** | **PARTIALLY COMPLIANT** — Madde 27 & 28 fiili ihlal (bkz. `CONSTITUTION_COMPLIANCE.md`) |

> ⚠️ **Dürüstlük düzeltmesi (2026-07-25):** Daha önce "production-grade / Production Readiness ✅" ifadeleri
> kullanıldı; bu **hak edilmemiş bir iddiaydı** ve geri alındı. Doğru ifade: *"çok iyi bir deterministik
> temel; henüz üretim-sertleştirilmiş değil."* "FROZEN" = geliştirme tamam (sonraki domaine geçilebilir) ≠
> Production. Ölçüt artık test sayısı değil, olgunluk + Constitution uyumu. Bkz. `MATURITY_AUDIT.md`,
> `TECHNICAL_DEBT.md`, `CONSTITUTION_COMPLIANCE.md`.

## Mimari durum

Bağımsız **Cognitive Operating System**. stdlib-only deterministik çekirdek (dataclass/sqlite3/urllib/
subprocess); DI + event-driven + Clean Architecture. **LLM = değiştirilebilir uzman danışman**, karar verici
değil (Governance Extensions §9). Çekirdek küçük ve LLM-bağımsız (Madde 16); her yetenek Domain / Capability /
MCP / Native Adapter / Plugin olarak eklenir.

## Aktif katmanlar

- **Cognitive core (E1–E5):** ExecutiveState (E1) · GoalManager (E2) · ExecutiveReview (E3) ·
  Governance/Decision (E4) · CognitiveEngine (E5: belief/çelişki/refutation). LLM-siz, deterministik.
- **Born Capable:** Purpose/Mission/Identity · innate Knowledge (tipli) · innate Beliefs · 14 Domain Brain ·
  Self Awareness · Cognitive Identity.
- **Execution altyapısı:** Tool Orchestrator · Model Gateway (LLM=araç) · MCP Hub · Meta MCP Manager v2.0 ·
  Capability Discovery/Registry · Transport abstraction (STDIO/HTTP/SSE) · Marketplace/Recommendation/Policy
  Profiles/Diagnostics/Analytics.
- **Event Bus** (record + subscribe_all) — ortak iletişim omurgası.

## Domain'ler (32 · geliştirme tamam · **Maturity: STABLE**, Production DEĞİL) — Faz 1-3 TAMAM, Faz 4 sürüyor

`mio_core/domains/<ad>/` — her biri: models · repository (SQLite write-through) · contract (versiyonlu) ·
service · events · authz · validation · observability · README · unit+integration+smoke test.
17'si dondurulmuş (Development Complete). Hepsi **STABLE**; hiçbiri Production Ready değil.
**Platform katmanı:** `mio_core/platform/resilience.py` (retry/backoff/circuit-breaker — Production Hardening #1).

| Faz | # | Domain | runtime erişimi |
|---|---|---|---|
| 1 Cognitive Core | 1 | Executive | `mio.executive` |
| | 2 | Memory | `mio.memory` |
| | 3 | Knowledge | `mio.knowledge_domain` |
| | 4 | Reasoning | `mio.reasoning` |
| | 5 | Planning | `mio.planning` |
| | 6 | Learning | `mio.learning` |
| | 7 | Goal Management | `mio.goal_management` |
| 2 Etkileşim & Yürütme | 8 | Communication | `mio.communication` |
| | 9 | Execution | `mio.execution` |
| | 10 | Perception | `mio.perception` |
| 3 Dikey Alan Beyinleri | 11 | Vertical Domain Brains (8) | `mio.verticals` |
| 4 Altyapı & Platform | 12 | Scheduler/Lifecycle | `mio.scheduler` |
| | 13 | Observability | `mio.observability_domain` |
| | 14 | Policy | `mio.policy` |
| | 15 | Security | `mio.security` |
| Constitution Faz 2 | 16 | Capability Management | `mio.capability_management` |
| | 17 | MCP Management | `mio.mcp_management` |
| | 18 | Audit & Compliance | `mio.audit` |
| | 19 | Resource & Runtime | `mio.resources` |
| Faz 3 Intelligence | 20 | Software Engineering | `mio.software_engineering` |
| | 21 | Research | `mio.research` |
| | 22 | Document Intelligence | `mio.document_intelligence` |
| | 23 | Data Analytics | `mio.data_analytics` |
| | 24 | Business & Operations | `mio.business_operations` |
| | 25 | Finance | `mio.finance` |
| | 26 | Sales & CRM | `mio.sales` |
| | 27 | Marketing & Growth | `mio.marketing` |
| | 28 | Customer Success | `mio.customer_success` |
| Faz 4 Multimodal | 29 | Vision | `mio.vision` |
| | 30 | Voice | `mio.voice` |
| | 31 | Media Generation | `mio.media` |
| | 32 | Web Intelligence | `mio.web` |
| | 33 | Device & Native Integration | `mio.device` |
| | 34 | IoT | `mio.iot` |
| Faz 5 Distributed | 35 | Model Management | `mio.model_management` |
| | 36 | Multi-Agent | `mio.multi_agent` |
| | 37 | Marketplace / Ecosystem | `mio.marketplace_domain` |
| | 38 | Knowledge Marketplace | `mio.knowledge_marketplace` |
| | 39 | Federation | `mio.federation` |
| | 40 | Distributed Execution | `mio.distributed_execution` |
| | 41 | Autonomous Operations | `mio.autonomous_operations` |
| | 42 | Simulation & Digital Twin | `mio.digital_twin` |
| | 43 | Extension SDK | `mio.extension_sdk` |

> **Not (backward-compat):** `mio.observability()` **metodu** (runtime özeti) korunmuştur; Observability
> Domain `mio.observability_domain` altındadır. Aynı şekilde `mio.marketplace` mevcut **CapabilityMarketplace**'tir;
> Faz 5 Marketplace/Ecosystem Domain `mio.marketplace_domain` altındadır (isim çakışması önlendi).

## Constitution roadmap haritalaması (dürüst)

Geliştirme, kullanıcıyla blok-blok ilerledi; Constitution'ın 40-domain fazlamasıyla birebir sıralı değildir
ama örtüşür. Constitution'ın **Platform Domains (Faz 2)** karşılıkları:

- **Communication** ✅ (Domain 8) · **Policy & Governance** ✅ (Domain 14 + core PolicyProfiles/E4) ·
  **Security & Identity** ✅ (Domain 15) · **Observability & Diagnostics** ✅ (Domain 13 + core Diagnostics) ·
  **Automation & Workflow / Resource & Runtime** ≈ kısmen (Domain 12 Scheduler; Resource Awareness çekirdekte
  Self Awareness/hardware ile başlangıç) · **Capability Management / MCP Management / Audit & Compliance** ≈
  çekirdekte var (CapabilityRegistry/Discovery, MCP Hub/Meta MCP, audit_store) ama **henüz tam bounded-context
  Domain değil** → gelecekte Domain'leştirilecek (bkz. NEXT_STEPS).

## Aktif capability'ler / MCP

- Native: reasoning capability (register_reasoning) — LLM-siz karar desteği.
- LLM: Ollama (gerçek, canlı doğrulandı) `orchestrator.execute("llm",…)` üzerinden; `connect_ollama=False`
  ile tamamen deterministik çalışır.
- MCP: gerçek stdio JSON-RPC client + HTTP/SSE transport plugin'leri hazır; bağlı MCP sunucusu opsiyonel.

## Bilinen limitler

- Capability/MCP/Audit/Resource henüz ayrı bounded-context Domain değil (çekirdek servisleri hâlinde).
- Multi-Organization (Madde 10), Digital Twin (Madde 22), Simulation-First (Madde 23), Self Development
  (Madde 18) mimari olarak **tanımlı ama Domain seviyesinde implemente edilmedi.**
- Otonom loop yalnız `scheduler.tick()` çağrılınca ilerler (gerçek-zaman sürücüsü yok — güvenli varsayılan).
- Test ortamı: py3.12 venv (sistem py3.14 kırık). Ollama tek-model cap: `OLLAMA_MAX_LOADED_MODELS=1`.
