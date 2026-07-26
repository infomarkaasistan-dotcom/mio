# MIO Technical Debt Register

> Constitution refs: Madde 36 (Compliance), Governance Extensions §10. **Teknik borçlar görünmez
> bırakılmaz** (Development Directive). Her kayıt: Problem · Etkilenen Domain · Constitution maddesi ·
> Risk · Etki · Öncelik · Çözüm · Planlanan faz.

Risk: 🔴 yüksek · 🟠 orta · 🟡 düşük · Öncelik: P0 (üretim bloklayıcı) → P3.

---

## DEBT-001 — `runtime.py` god composition-root
- **Problem:** 16 domain + ~20 çekirdek bileşeni 200+ satırlık `boot()` içinde elle, sıralı bağlanıyor.
  Yeni domain = runtime kodu değişikliği (Discovery/Registry/Plugin auto-loading yok).
- **Domain:** runtime (global). **Constitution:** Madde 16 (küçük çekirdek), Runtime Refactoring Policy.
- **Risk:** 🟠 · **Etki:** 40+ domain hedefinde bu dosya "çekirdek şişmesi" olur; kısmi-boot izolasyonu yok.
- **Öncelik:** P1 · **Çözüm:** Discovery+Registry tabanlı Boot Manager; domain'ler kendini kaydeder.
- **Faz:** Production Hardening #1 (Runtime Refactoring).

## DEBT-002 — Resilience mekanizmaları — 🟢 BÜYÜK ÖLÇÜDE KAPATILDI (2026-07-25)
- **Çözülen:** `mio_core/platform/resilience.py` — **Retry · Exponential Backoff · Circuit Breaker ·
  Graceful Degradation** (deterministik, enjekte clock/sleeper). Orchestrator'a (tüm tool/LLM/MCP çağrısının
  tek geçiş noktası) opt-in policy olarak entegre edildi; devre açıkken yürütücü korunuyor (`circuit_open`
  sonucu) ve `circuit_state()` ile gözlemlenebilir. **Capability Failover** zaten vardı (alternatives).
  Runtime üretim policy'siyle geliyor. 11 test + tam süit 345/345.
- **Kalan (ertelendi, gerekçeli — EXCEPTION APPROVED):** **Model Failover** (gateway-seviyesi), **Queue/State
  Recovery · Disaster Recovery** (→ DEBT-005 Recovery fazı), health-driven proaktif fallback.
- **Domain:** platform (cross-cutting) + orchestrator. **Constitution:** Madde 28 — **İHLAL → PARTIALLY
  COMPLIANT** (çekirdek mekanizmalar var; recovery mekanizmaları planlı).
- **Risk:** 🔴 → 🟠 · **Öncelik:** P1 (kalan: recovery). **Not:** Yük/stres testiyle henüz doğrulanmadı →
  "Production Ready" değil, mekanizma mevcut ve unit-doğrulanmış.

## DEBT-003 — Kritik sessiz-yutma — 🟢 KAPATILDI (2026-07-25)
- **Çözülen:** **EventBus** artık abone hatasını yutmuyor → sayaç (`dropped`) + son-hatalar halkası +
  `on_subscriber_error` hook (runtime'da observability sayacına akar) + log. `subscriber_errors()` ile
  görünür. **Orchestrator sonuç-dinleyici** `except: pass` → log. Backward-compat (yeni opsiyonel param).
- **Kabul edilen best-effort (kritik DEĞİL, log'lu — Madde 27 uyumlu):** transport/MCP teardown temizliği,
  runtime `close/persist` teardown, hardware probe keşfi, planning reasoning-rationale. Bunlar zaten
  log'luyor ve kritik yol değil (best-effort meşru).
- **Domain:** events (global), orchestrator. **Constitution:** Madde 27 — **İHLAL → SUBSTANTIALLY COMPLIANT**
  (hata görünürlüğü sağlandı; distributed tracing hâlâ eksik → ayrı iş, DEBT-006/Observability fazı).
- **Risk:** 🟠 → 🟡 · **Öncelik:** P2 (kalan: tracing).

## DEBT-004 — Çok-organizasyon (org_id) YOK
- **Problem:** Hiçbir repository/şema `org_id` taşımıyor. Madde 10 (Multi-Organization) mimari zorunlu.
- **Domain:** tüm repository'ler. **Constitution:** Madde 10.
- **Risk:** 🟠 · **Etki:** Geç eklenirse 16+ şemaya dokunur; borç zamanla büyür.
- **Öncelik:** P1 · **Çözüm:** Repository-seviyesi `org_id` (varsayılan tek org, geriye-uyumlu).
- **Faz:** Production Hardening (Runtime sonrası).

## DEBT-005 — Cross-store transaction/atomiklik YOK
- **Problem:** 16+ ayrı SQLite; çok-domainli operasyon (Execution planı → execution.db + learning.db +
  goals) atomik değil. Kısmi başarısızlık tutarsız durum bırakabilir.
- **Domain:** execution, goal_management, learning. **Constitution:** Madde 28 (State Recovery), 14.
- **Risk:** 🟠 · **Etki:** Kısmi yazımlarda tutarsızlık; recovery zor.
- **Öncelik:** P1 · **Çözüm:** Unit-of-work / saga + telafi (compensation) desenleri.
- **Faz:** Production Hardening #5 (Recovery).

## DEBT-006 — Event Bus: durability/replay/versioning nominal
- **Problem:** Süreç-içi senkron bus; kalıcı değil, replay/dead-letter yok. `EventContracts` bağlı değil →
  event versiyonlama nominal (hep "1.0.0"). Observability boot-öncesi eventleri kaçırır.
- **Domain:** events (global), observability. **Constitution:** Madde 29 (Versioned Event Contracts), 27.
- **Risk:** 🟠 · **Etki:** Restart'ta event kaybı; sürüm uyumu denetlenemiyor; federation'a hazır değil.
- **Öncelik:** P1 (ölçek/dağıtımda P0) · **Çözüm:** EventContracts wiring + kalıcı event log + replay.
- **Faz:** Production Hardening #3/#5.

## DEBT-007 — Security production sertleştirme eksik
- **Problem:** RBAC+audit+redact+lockout var; ama Secret Vault, Encryption-at-rest, Signed Events,
  Dependency/Vulnerability Scan, MCP Trust Validation yok.
- **Domain:** security, MCP. **Constitution:** Madde 24, Security Hardening.
- **Risk:** 🟠 · **Öncelik:** P2 · **Çözüm:** Vault + encryption + signed events + supply-chain scan.
- **Faz:** Production Hardening #8.

## DEBT-008 — Concurrency-güvenli değil (in-memory state)
- **Problem:** Repository'ler Lock'lu ama domain in-memory state (scheduler jobs, observability counters,
  capability registry, communication handlers) eşzamanlı erişime karşı korumasız.
- **Domain:** scheduler, observability, capability_mgmt, communication. **Constitution:** Madde 28.
- **Risk:** 🟠 (HTTP API gelince 🔴) · **Öncelik:** P1 (API öncesi) · **Çözüm:** state erişimini serialize
  et / immutable snapshot / actor-model.
- **Faz:** Production Hardening (API öncesi).

## DEBT-009 — Bounded context izolasyon sızıntısı (küçük)
- **Problem:** `learning/service.py`, `knowledge.KnowledgeError`'ı doğrudan import ediyor (başka context'in
  hata tipi). **Constitution:** Governance Extensions §4.
- **Risk:** 🟡 · **Öncelik:** P2 · **Çözüm:** Shared kernel'de ortak hata sözleşmesi veya facade dönüşümü.

## DEBT-010 — CI/CD + Fitness Functions YOK
- **Problem:** Otomatik kalite kapısı yok; Madde 37 (Fitness Functions) yazılı ama uygulanmadı (circular dep,
  domain isolation, contract, coverage kontrolleri manuel/yok).
- **Domain:** global. **Constitution:** Madde 37, CI/CD Quality Gates.
- **Risk:** 🟠 · **Etki:** Mimari zamanla sessizce bozulabilir; regresyon kapısı yok.
- **Öncelik:** P1 · **Çözüm:** CI pipeline + fitness fonksiyonları.
- **Faz:** Production Hardening #9/#10.
