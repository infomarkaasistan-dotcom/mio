# Platform Hardening — Production Hardening Fazı (tek platform fazı)

> **Bağlam:** Tüm 43 ana domain STABLE (Development Complete). Kullanıcı direktifi: kapsamlı hardening tüm ana
> domainler bittikten sonra **tek bir platform fazı** olarak ele alınır. **Olgunluk-dürüstlüğü kuralı:** maturity
> iddiası ancak KANIT (test/ölçüm) ile yükselir; STABLE = Development Complete ≠ Production.
> Bkz. `MATURITY_AUDIT.md`, memory `feedback_maturity_label_honesty`.

## İlke
Her hardening çıktısı **iddia değil kanıt** üretmelidir: çalışan test, ölçüm veya doğrulanabilir artefakt.
Mevcut Domain API'leri, Capability Contract'ları ve backward-compatibility KORUNUR (Madde 15 wrap-don't-rewrite).

## Öncelik sırası (kullanıcı + dürüst sıralama)
| # | Kalem | Durum | Kanıt |
|---|---|---|---|
| 1 | **Fitness Functions** (mimari değişmezleri otomatik test) | ✅ **TAMAM** | `tests/test_fitness_functions.py` — 218 kontrol yeşil |
| 2 | **Operational Readiness** (readiness probe + graceful shutdown + config validation) | ✅ **TAMAM** | `mio.readiness()` + idempotent `mio.close()` raporu; `tests/test_operational_readiness.py` — 7 yeşil |
| 3 | Resilience yayılımı (retry/backoff/circuit breaker → connector çağrıları) | ⏳ **ERTELENDİ** | Gerçek adapter yokken spekülatif (tüm connector'lar absent → yalnız test-double sarar). Gerçek connector bağlanınca yapılacak |
| 4 | **CI/CD pipeline** (suite + fitness + readiness gate'leri) | ✅ **TAMAM + AKTİF** | `.github/workflows/ci.yml` (matris 3.10-3.12); GitHub Actions'ta **yeşil** (conclusion=success). `docs/development/CI.md` |
| 5 | **Load / Soak testing** | ✅ **TAMAM** | `tests/test_load_soak.py` — 5 yeşil (eşzamanlı yazma bütünlüğü + 1500-iter soak + boot/close döngüsü). **Eşzamanlılık bulgusu** kayıtlı (↓) |
| 6 | **Recovery / backup-restore** | ✅ **TAMAM** | `tests/test_recovery.py` — 4 yeşil (crash-recovery + hot-backup API + point-in-time + WAL-checkpoint soğuk-kopya) |
| 7 | **Observability** (structured logging + tracing + metrics) | ✅ **TAMAM** | `mio_core/platform/observability.py` (JSON log+redaction, nested Tracer) + `mio.metrics()`; `tests/test_observability.py` — 7 yeşil |
| 8 | **Deployment artefaktları + monitoring probe** | ✅ **TAMAM (artefakt)** | `mio_core/ops.py` (`python -m mio_core readiness/health/metrics`) + `Dockerfile` (HEALTHCHECK) + `docs/development/DEPLOYMENT.md`; `tests/test_ops_entrypoint.py` — 7 yeşil. **Gerçek deploy = kullanıcı altyapı kararı** |
| 3 | Resilience yayılımı | ⏳ **ERTELENDİ** | Gerçek adapter yokken spekülatif; connector bağlanınca |
| — | HTTP/API katmanı · HA/replica · canlı monitoring stack | ⏳ planlı | Dışa açık servis + cluster deploy (dürüst kapsam: henüz yok) |

> **Sıralama notu (dürüstlük):** Resilience kullanıcı önceliğinde #1'di; ancak tüm connector'lar şu an *absent*
> (gerçek adapter yalnız testlerde enjekte) olduğundan resilience'ı 15 domaine yaymak **çalışma-zamanı faydası
> sıfır spekülatif iskele** olurdu. Kullanıcı onayıyla önce **Operational Readiness** yapıldı (şu an gerçekten
> test edilebilir, kanıt üretir). Resilience, gerçek connector bağlandığında anlam kazanınca ele alınacak.

## 2 — Operational Readiness (TAMAM)
`mio.readiness()` — DETERMİNİSTİK self-check (dış adapter gerektirmez): event bus, kalıcılık store'ları (>30),
resilience katmanı yüklenebilirliği, **workspace yazılabilirliği** (config validation) ve tüm sözleşmeli
domainlerin `contract()` sorgulanabilirliği. Kapandıktan sonra `ready=False` (dürüst). K8s readiness probe'un
çekirdek muadili.

`mio.close()` — **IDEMPOTENT graceful shutdown** + hataları **GÖRÜNÜR** kılan yapılandırılmış rapor
(`{already_closed, closed[], errors[]}`). Önceki hali hataları sessizce yutuyordu (Madde 27 ihlali) → artık her
bileşen hatası raporda; best-effort (raise etmez, süreci durdurmaz); ikinci çağrı no-op. Backward-compat: eski
`close()` çağrıları dönüşü yok sayarak çalışmaya devam eder (768 test yeşil).

## 1a — Fitness Functions (TAMAM)
`tests/test_fitness_functions.py` her CI/test koşusunda mimari değişmezleri doğrular ve regresyonu yakalar:
- **Madde 8** — çekirdek kodda stub/placeholder (TODO/FIXME/XXX/NotImplementedError) YOK.
  (`software_engineering` domaini muaf: görevi stub'ı VERİ olarak tanımaktır.)
- **§4 Bounded Context** — bir domain başka domainin İÇ modülünü import ETMEZ (sıfır ihlal).
- **Determinizm + LLM-bağımsızlık** — domain service'leri canlı LLM/gateway import ETMEZ.
- **Domain sözleşmesi** — her domain models+contract+service+__init__+README + semver CONTRACT_VERSION içerir.
- **Kalıcılık deseni** — repository.py'si olan her domain SQLite WAL + threading.Lock kullanır.
- **Kompozisyon** — boot() tanımlı her domaini MIORuntime'a bağlar (attribute mevcut, contract versiyonlu).

### Fitness Functions'ın kanıtladığı & kanıtlamadığı (dürüstlük)
**Kanıtlar:** mimari tutarlılık, izolasyon, no-placeholder, LLM-bağımsızlık, kompozisyon bütünlüğü — statik +
boot-zamanı. **Kanıtlamaz:** yük altında davranış, HA, gerçek CI pipeline, gerçek dış connector'larla uçtan uca
doğrulama. Bunlar sıradaki kalemlerdir. Fitness geçmesi domaini **Production Ready** yapmaz; **mimari borç yok**
demektir.

### Kalibrasyon notu (gerçeğe uyum)
İlk koşuda fitness functions gerçek yapısal varyasyonu ortaya çıkardı: `executive` ve `goal_management` domainleri
`repository.py` yerine çekirdeğin paylaşılan store'larını (ExecutiveState/GoalStore) kullanıyor. Kural **gerçeğe
göre kalibre edildi** (repository.py evrensel değil; persistence-sahibi domainlere özgü) — aşırı-katı, gerçeğe
uymayan kural da bir dürüstlük ihlalidir.

## 4 — CI/CD (TAMAM, taslak)
`.github/workflows/ci.yml` üç kapıyı sırayla koşar (hızlı geri-bildirim önce): **fitness gate** → **readiness
gate** → **tam süit**. Matris: Python 3.10/3.11/3.12. Çekirdek stdlib-only → CI yalnız `pip install pytest`
gerektirir (uv gerekmez). `docs/development/CI.md`: gate'ler + lokal reçete + **aktivasyon** (git init/commit/push)
+ kapsam/dürüstlük. Öz-doğrulama: `test_ci_workflow_references_real_gates` CI'nin ölü dosyaya işaret etmesini
yakalar. **Aktif değil:** repo git deposu değil; aktivasyon = kullanıcı kararı (dış-yüze işlem).

## 5 — Load / Soak (TAMAM) + Eşzamanlılık bulgusu
`tests/test_load_soak.py` (5 test) gerçek runtime'a karşı: eşzamanlı yazmada **veri bütünlüğü** (kayıp yok),
sürekli 1500-iterasyon soak sonrası **readiness kararlı**, 4× boot/close döngüsünde **temiz kapanış**, ve
thread-başına-bağlantıyla eşzamanlı okuma güvenli.

### ⚠️ Eşzamanlılık bulgusu (load-testing'in ürettiği GERÇEK bilgi — dürüstçe kaydedilmiştir)
**Bulgu:** Repository katmanı **yazmaları** `threading.Lock` ile serileştirir → veri bütünlüğü eşzamanlı yazmada
korunur (kanıtlandı). Ancak **okumalar lock-free**'dir ve tüm thread'ler tek **paylaşılan** `sqlite3.Connection`
kullanır. `sqlite3.Connection` çok-thread'li eşzamanlı erişim için güvenli olmadığından, eşzamanlı yazma **veya
eşzamanlı okuma** sırasında lock-free bir okuma geçici olarak hata verebilir (`fetchone()` None).

**Kapsam / şiddet:** Bu bir **veri bütünlüğü** sorunu DEĞİL — dosya asla bozulmaz, yazmalar doğru iner. Bir
**okuma-eşzamanlılığı** sınırı. MIO'nun mevcut akışı (senkron EventBus, domain'ler sıralı çağrılır) tek repo'ya
çok-thread'li eşzamanlı erişim ÜRETMEZ → bu **latent** bir sınırdır, aktif bug değil. Load testing gelecekteki
ölçeklenme için sınırı ortaya çıkardı.

**Remediasyon (gerektiğinde):** (a) okumaları da mevcut `self._lock` ile sar (basit, okumaları serileştirir),
veya (b) **thread-başına ayrı bağlantı** (WAL çoklu-okur + tek-yazar destekler — `test_concurrent_readers_with_
own_connections_are_safe` bunu kanıtlar), veya (c) bağlantı havuzu. Şu an uygulanmadı çünkü mevcut kullanım
desenini etkilemiyor ve 40+ repository'ye dokunmak orantısız olurdu; gerçek çok-thread'li repo erişimi
gerektiğinde (b) tercih edilmelidir.

## Sıradaki adaylar
- **Load/Soak** — çok-thread'li repository yazma + boot/close döngüsü altında throughput/latency ölçümü (gerçek
  runtime'a karşı, adapter gerektirmez → şu an ölçülebilir).
- **Recovery** — SQLite WAL yedek/geri-yükleme senaryosu (checkpoint + kopya + yeniden-boot doğrulaması).
- **Resilience** — gerçek connector bağlandığında; `resilient_call` o adapter çağrısına sarılır.
- **Gerçek connector bağlama** — resilience'a + uçtan uca kanıta anlam kazandırır.
