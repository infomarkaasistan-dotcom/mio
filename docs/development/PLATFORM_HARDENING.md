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
| 4 | **CI/CD pipeline** (suite + fitness + readiness gate'leri) | ✅ **TAMAM (taslak)** | `.github/workflows/ci.yml` (matris 3.10-3.12) + `docs/development/CI.md`; öz-doğrulama `test_ci_workflow_references_real_gates`. **Aktif değil** — repo git değil (aktivasyon adımları CI.md'de) |
| 5 | Load / Soak testing + performans bütçeleri | ⏳ planlı | ölçülmüş throughput/latency raporu |
| 6 | HA / Deployment hardening | ⏳ planlı | — |
| 7 | Recovery / backup-restore drills | ⏳ planlı | WAL yedek/geri-yükleme senaryosu |

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

## Sıradaki adaylar
- **Load/Soak** — çok-thread'li repository yazma + boot/close döngüsü altında throughput/latency ölçümü (gerçek
  runtime'a karşı, adapter gerektirmez → şu an ölçülebilir).
- **Recovery** — SQLite WAL yedek/geri-yükleme senaryosu (checkpoint + kopya + yeniden-boot doğrulaması).
- **Resilience** — gerçek connector bağlandığında; `resilient_call` o adapter çağrısına sarılır.
- **Gerçek connector bağlama** — resilience'a + uçtan uca kanıta anlam kazandırır.
