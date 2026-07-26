# MIO Architectural Constitution — v1.0

| | |
|---|---|
| **Version** | 1.0.0 |
| **Effective Date** | 2026-07-25 |
| **Status** | RATIFIED · Değişmez (yalnız Constitution Revision süreciyle güncellenir) |
| **Authority** | En üst seviye mimari otorite. Bu belge diğer TÜM teknik dokümanlardan üstündür. |

> Bu belge bir özellik talebi değildir. MIO Platformu'nun bundan sonraki tüm geliştirme sürecini yöneten
> **kalıcı mimari anayasadır.** Hiçbir ADR, Domain Specification, Capability Contract, Sprint, Roadmap veya
> Coding Standard bu Anayasa ile çelişemez. Otorite zinciri:
>
> **Constitution → Architecture Principles → Reference Architecture → ADR → Domain Specifications →
> Capability Contracts → Implementation Standards → Coding Standards → Tests → Deployment → Operations.**

---

## Madde 0 — Constitution Scope

Bu belge MIO Platformu'nun **en üst seviye mimari otoritesidir.** Bu belge; ürün gereksinimlerini,
sprint planlarını, teknik implementasyon detaylarını veya belirli teknoloji seçimlerini **tanımlamaz.**
Yalnızca platformun uzun vadeli **mimari prensiplerini, yönetişim kurallarını ve değişmez tasarım
ilkelerini** tanımlar. Hiçbir alt doküman bu Anayasa ile çelişemez.

---

## Bölüm I — Kimlik ve Vizyon

### Madde 1 — MIO bir proje değildir
MIO, uzun yıllar boyunca büyüyecek bir **Cognitive Operating System**'dir. Her karar en az **10 yıllık
büyüme** düşünülerek alınır; hiçbir karar yalnızca bugünkü ihtiyaca göre verilmez.

### Madde 2 — Özellik değil, platform
Her özellik platformun **doğal sonucu** olmalıdır. Marketplace, Manufacturing, Finance, Hardware,
Marketing gibi alanlar sonradan eklenen özellikler değil, platformun **doğal parçalarıdır.**

### Madde 12 — Amaç sohbet değil, operasyon
MIO'nun amacı operasyon yönetmektir. **Sohbet yalnızca kullanıcı arayüzlerinden biridir.**

### Madde 41 — Architecture North Star
MIO'nun amacı mümkün olan en fazla özelliğe sahip olmak değil; **yeni sektörleri, organizasyonları ve
operasyonları mevcut çekirdeği değiştirmeden** sisteme dahil edebilen, uzun ömürlü bir Cognitive Operating
System olmaktır.

---

## Bölüm II — Domain ve Operasyon Mimarisi

### Madde 3 — Domain-First zorunludur
Yeni geliştirmede önce **Domain** tanımlanır. Entegrasyon sırası:
`Domain → Capability → Events → Memory → Executive → Policy → Audit → MCP/Native Adapter/Plugin →
Dashboard Events → API → Tests`. Hiçbir Domain yalnızca klasör olarak eklenmez; sistemin **yaşayan** bir
parçası olur.

### Madde 4 — Bir Domain girdiği gün tam vatandaştır
Domain eklendiğinde: Executive tanır, Capability Registry tanır, Policy Engine tanır, Audit izler, Memory
kullanır, Event Bus görür, Dashboard event üretir, Health Monitor izler, Metrics ölçer, testleri yazılmıştır.
İş mantığı zamanla gelişebilir; **mimari konumu ilk günden eksiksiz** tanımlanmış olmalıdır.

### Madde 5 — Ana operasyon alanları bugünden tanımlanır
Gelecekte "şunu da ekleyelim" mantığıyla çekirdeğin yeniden tasarlanması **istenmez.** MIO'nun destekleyeceği
tüm ana operasyon alanlarının mimari sınırları, sorumlulukları, yaşam döngüleri, sözleşmeleri, entegrasyon
kuralları ve genişleme noktaları tanımlıdır. Örnekler: Marketplace · Marketing · Finance · Manufacturing ·
Logistics · Customer · CRM · Business Intelligence · Knowledge · Research · Media · Software · Game Studio ·
AI · Infrastructure · Hardware · Procurement · Inventory · Security · Compliance · Legal · Personal · IoT ·
Robotics · Smart Home Operations. Hiçbir yeni Domain **çekirdeğin yeniden tasarlanmasını gerektirmemelidir.**

### Madde 6 — Connector değil, Operation
Trendyol, Amazon, Hepsiburada, Shopify, Etsy, WooCommerce bir operasyon **değildir** — bunlar **Marketplace
Operations Domain**'inin Connector/Adapter katmanıdır.

### Madde 7 — Aynı kural tüm sistemde geçerlidir
Google/Meta/TikTok/LinkedIn Ads = **Marketing Operations** · 3D Printer/CNC/Laser/Robot/PLC = **Manufacturing
Operations** · GitHub/GitLab/Docker/Kubernetes = **Software/Infrastructure Operations**. **Hiçbir dış sistem
doğrudan Executive'e bağlanmaz** — önce ilgili Operation Domain'ine bağlanır.

### Madde 9 — MIO API değil, operasyon yönetir
Hedef tek tek entegrasyon değil, **operasyon yönetmektir.** Örn. Marketplace Operations; ürün/stok/sipariş/
müşteri mesajı/fiyat/rakip/trend/kampanya/kârlılık/raporlama operasyonlarından sorumludur. Trendyol yalnızca
bu operasyonun çalıştığı kanallardan biridir.

### Madde 39 — Platform Evolution Policy
Yeni Domain oluşturmak **her zaman son seçenektir.** Önce sor: Gerçekten gerekli mi? Mevcut Domain
genişletilebilir mi? Yeni Capability yeter mi? Plugin/MCP/Connector çözer mi? Amaç Domain sayısını artırmak
değil, **mimari bütünlüğü korumaktır.**

---

## Bölüm III — Çekirdek ve Evrim

### Madde 15 — Evolutionary Architecture zorunludur
Hiçbir geliştirme mevcut çekirdeği, Executive davranışını, Capability sözleşmelerini veya çalışan sistemleri
**bozmayacak** şekilde tasarlanır. Büyük değişiklikler mevcut davranışı kırmadan **yeni katmanlar veya
adaptörler** üzerinden yapılır. **"Silip yeniden yazmak son çaredir."**

### Madde 16 — Çekirdek küçük kalır
Her geliştirmede sor: **"Bu gerçekten çekirdeğe mi ait?"** Aynı davranış Capability/MCP/Native Adapter/Plugin
olarak yapılabiliyorsa **çekirdeğe eklenmez.** Çekirdek yalnızca platformun değişmez kurallarını taşır;
ekosistem sürekli büyüyebilir.

### Madde 29 — Versioned Platform Contracts
Hiçbir Domain, Capability, Event, Memory Schema, API, MCP Contract veya Plugin Interface kontrolsüz
değiştirilemez. Her sözleşme: semantic version · compatibility level · migration strategy · deprecation
policy · rollback strategy ile yönetilir. Böylece yüzlerce Domain birbirini kırmadan yıllarca gelişebilir.

### Madde 26 — Capability Evolution & Skill Acquisition
MIO yeni Capability kazanabilir, mevcutları geliştirebilir, kullanılmayanları güvenle emekliye ayırır.
Yaşam döngüsü: `İhtiyaç → Tasarım → Contract → Sandbox → Test → Benchmark → Executive Review → Production →
Monitoring → Learning → Version Management`. Hiçbir Capability çekirdeğe doğrudan bağımlı değildir.

### Madde 33 — Ecosystem Architecture
Platform üçüncü parti Domain/Capability/Plugin/MCP, Marketplace Packages ve Community Extensions
eklenebilecek şekilde tasarlanır. MIO gelecekte **kendi ekosistemini** oluşturabilir.

---

## Bölüm IV — Zekâ, Karar ve Otonomi

### Madde 18 — Self Development Architecture
MIO statik değildir; zamanla kendi yeteneklerini/mimarisini/operasyonlarını **analiz** edebilir. Amaç
kontrolsüz kod değiştirmek **değil**; gözlem → eksik/darboğaz tespiti → iyileştirme önerisi → güvenli test →
**Executive onayı ile entegrasyon**. Alt sistemler: System Observation · Repository Intelligence ·
Architecture Intelligence · Code Knowledge Graph · Development Memory · Improvement Engine · Experiment/
Sandbox Engine · Learning Memory · Code Review Engine. Değişim yaşam döngüsü:
`Problem → Çözüm Önerisi → Mimari Etki Analizi → Değişiklik Planı → Sandbox → Test → Benchmark →
Executive Review → Production Approval → Learning Memory`. **Hiçbir otomatik değişiklik doğrudan production'a
uygulanmaz.**

### Madde 19 — Intelligence Routing & Model Orchestration
MIO hiçbir modele bağımlı değildir. **LLM'ler karar verici değil, uzman araçlardır.** Model seçimi görev
türü/kalite/maliyet/gizlilik/ortam/kaynağa göre Executive+Policy+Capability kurallarınca yapılır. Modeller
yalnız analiz/öneri/kod üretimi/inceleme/test/dokümantasyon/mimari değerlendirmede kullanılır; **hiçbir model
doğrudan sistemi değiştiremez.** Tüm çıktılar Executive/Policy/Audit/Test süreçlerinden geçer.

### Madde 20 — Strategic Planning & Goal-Driven Development
MIO uzun vadeli hedefler için kendi planlarını oluşturur, ilerlemeyi izler, stratejisini günceller.
`Hedef → Alt hedefler → Projeler → Görevler → Capability kullanımı → Gerçek operasyonlar`. Planlar çalışma
sırasında değiştirilebilir (continuous replanning).

### Madde 23 — Simulation-First Decision Making
Kritik operasyonlarda (büyük fiyat/reklam bütçesi/üretim planı/altyapı/kod/finans/strateji) önce simülasyon
çalışır: `Problem → Alternatif Senaryolar → Simulation → Risk Analizi → Beklenen Sonuç → Executive Kararı →
Production → Learning Memory`. Amaç hızlı değil **daha doğru** karar.

### Madde 24 — Autonomous Execution Governance
Hiçbir operasyon sınırsız yetkiyle çalışmaz. Güven seviyeleri: **Observe · Recommend · Assisted Execute ·
Autonomous Execute · Restricted.** Yüksek riskli operasyon Executive+Policy+Security birlikte karar vermeden
çalışmaz. Amaç tamamen otonom değil, **güvenli şekilde otonom** olmaktır.

### Madde 32 — Human Governance
MIO insanı sistemden çıkarmaz, doğru seviyeye taşır. Executive gerektiğinde açıklama/onay ister, alternatif
sunar, risk belirtir, geri-alma planı gösterir. **İnsan her zaman nihai otoritedir.**

---

## Bölüm V — Bilgi, Bellek ve Öğrenme

### Madde 21 — Continuous Learning & Organizational Knowledge
Her tamamlanan operasyon bir öğrenme fırsatıdır. Katmanlar: Decision Memory · Experience Memory · Best
Practices · Failure Repository · Lessons Learned · Organizational Knowledge Base · Pattern Library. Her
önemli operasyon sonunda: Ne amaçlandı? Ne oldu? Ne başarılı/başarısız? Bir dahaki sefere ne farklı?

### Madde 25 — Unified Knowledge Architecture
Bilgi tek mantıksal mimaride yönetilir: Structured · Semantic · Episodic · Procedural · Knowledge Graph ·
Vector · Document Store · Operational History · Learning Memory. Hiçbir Domain bilgi modelini **tamamen izole**
kurmaz; ortak ontoloji + sözleşmelerle paylaşılır.

### Madde 22 — Digital Twin Architecture
Yönetilen her organizasyon/cihaz/operasyon/kaynak için Digital Twin oluşturulabilir (şirket, fabrika, 3D
yazıcı, bilgisayar, depo, robot, IoT, pazaryeri/reklam hesabı). Executive mümkün olduğunda kararlarını bu
temsiller üzerinden **simüle ederek** alır.

---

## Bölüm VI — Kalite, Gözlemlenebilirlik ve Dayanıklılık

### Madde 27 — Observability & Explainability
Her önemli karar izlenebilir ve açıklanabilir olmalı: Distributed Tracing · Decision/Capability/Event/Memory/
Policy Trace · Performance/Cost Metrics · Explainability Report. **Hiçbir kritik karar kara kutu değildir.**

### Madde 28 — Resilience & Graceful Degradation
Sistem tek bileşene bağımlı çalışmaz. Bir LLM/MCP/Connector/Domain/servis düşerse en güvenli şekilde
sürdürülür: Health Monitoring · Retry · Circuit Breaker · Fallback · Model/Capability Failover · Queue/State
Recovery · Partial Operation · Disaster Recovery.

### Madde 30 — Resource Awareness
Executive görevi de kaynakları da değerlendirir: CPU/GPU/RAM/VRAM/Disk/Network/Energy/API Budget/Token
Budget/Latency gerçek zamanlı izlenir. En doğru değil, **en verimli** çözüm seçilir. MIO dizüstünde de veri
merkezinde de aynı mimariyle çalışır.

### Madde 31 — Time Awareness
MIO zamanı yönetir: geçmiş/mevcut/planlanan durum · zamanlanmış görevler · recurring operations · deadlines ·
SLA · maintenance windows · historical replay. Tüm operasyonlar zamansal bağlama sahiptir.

### Madde 11 — Hardware Operations zorunludur
MIO kendi çalıştığı sistemi tanır: CPU/GPU/RAM/VRAM/Disk/Network/Power/BIOS/Firmware/Drivers/USB/Displays/
Peripherals/3D Printers/Kameralar/Mikrofonlar. Darboğazları analiz eder, yükseltme önerir, donanımını yönetir.

### Madde 35 — Architectural Quality Attributes
Her önemli mimari karar şu nitelikler açısından analiz edilir: Maintainability · Extensibility · Modularity ·
Reliability · Availability · Scalability · Security · Privacy · Performance · Resource Efficiency ·
Observability · Explainability · Testability · Recoverability · Portability · Interoperability. Karar hangi
niteliği iyileştirdiğini/kötüleştirdiğini açıkça belirtir.

---

## Bölüm VII — Çok-Organizasyon

### Madde 10 — Multi-Organization zorunludur
MIO tek şirket için yazılmaz. Bugün A, yarın B, sonra kendi şirketlerim aynı çekirdek tarafından
yönetilebilmelidir. **Tüm geliştirmeler Multi-Organization mantığıyla** yapılır.

---

## Bölüm VIII — Yönetişim ve Süreç

### Madde 8 — Her geliştirmede sorulacak sorular
Bu kod gerçekten gerekli mi? Mevcut mimariye doğal oturuyor mu? Yeni katman mı oluşturuyorum yoksa mevcudu mu
güçlendiriyorum? 5 yıl sonra da doğru mu? Yüzlerce Connector destekler mi? MIO'yu daha modüler yapıyor mu?

### Madde 13 — Yalnız bugünü düşünme
Her geliştirme cevaplamalı: *"Bu yapı iki yıl sonra yeni bir sektör/şirket/operasyon eklendiğinde değişmeden
çalışabilecek mi?"* Cevap hayırsa mimari yeniden düşünülür.

### Madde 14 — Belge değil, çalışan sistem — ama üretim-kalite artefact'larla
Çalışan sistem üretilirken ADR'ler, sözleşmeler, testler ve mimari kararlar üretim seviyesinde hazırlanır.
Her büyük geliştirme sonunda sistem gerçekten **entegre, test edilmiş ve mimariye doğal yerleşmiş** olur.

### Madde 17 — Development Memory & Sürekli Proje Hafızası zorunludur
Geliştirme oturum-bazlı ilerlemez. `docs/development/` altında sürekli güncel teknik hafıza tutulur:
`CURRENT_STATE.md · COMPLETED.md · NEXT_STEPS.md · BLOCKERS.md · SESSION_LOG.md` + `docs/roadmap/
PLATFORM_ROADMAP.md`. Büyük kararlar ADR olur. **Yeni oturum prosedürü:** (1) CURRENT_STATE oku, (2) NEXT_STEPS
oku, (3) son SESSION_LOG oku, (4) ilgili ADR'leri kontrol et, (5) mimariyi yeniden analiz etmek yerine kaldığın
yerden devam et. Amaç: proje hafızası insana veya tek bir oturuma bağlı olmasın.

### Madde 34 — Constitutional Governance
Bu belge en üst mimari otoritedir; ADR/Domain Spec/Capability Contract/Event Contract/Memory Model/Executive
kuralları/Policy/Security/API/MCP/Adapter/Plugin/Dashboard/Development/Test/Roadmap/Sprint/Refactoring dahil
tüm çıktılar buna uyar. Bir ADR/Sprint/Domain/Capability bu belgeyi **değiştiremez.** Yalnız **Constitution
Revision** (mimari etki + geriye-uyum + risk + geçiş planı + revizyon kaydı) ile güncellenir.

**Constitution Interpretation Principle** — Amaç geliştirmeyi yavaşlatmak değil, uzun vadeli mimari bütünlüğü
korumaktır. Çelişkide öncelik: (1) uzun vadeli sürdürülebilirlik, (2) geriye-uyum, (3) güvenlik/doğrulanabilirlik,
(4) modülerlik/genişletilebilirlik, (5) performans/maliyet. *(Ayrıntılı 10-seviyeli öncelik: Governance
Extensions §1.)*

### Madde 36 — Constitutional Compliance
Her büyük geliştirme sonunda sistem testlerden **ve** Constitution uyum kontrolünden geçer. Sorular: Hangi
maddeler etkilendi? Ne destekleniyor? İhlal var mı? Varsa gerekçe/geçici istisna? ADR oluşturuldu mu? Hiçbir
büyük geliştirme **Compliance raporu olmadan** tamamlanmış sayılmaz. *(Seviyeler: Governance Extensions §10.)*

### Madde 37 — Architectural Fitness Functions
İlkeler yalnız yazılı kalmaz; mümkün olan her ilke otomatik doğrulanır: circular dependency, domain isolation,
katman ihlali, API/Event Contract doğrulama, version uyumluluğu, plugin izolasyonu, test coverage, performans
eşiği, security policy. Bunlar CI/CD'nin doğal parçasıdır.

### Madde 38 — Architecture Review Board
Her büyük mimari değişiklik uygulanmadan önce Review'dan geçer: Constitution uyumu · Domain/Capability etkisi ·
Backward compatibility · Güvenlik/Performans/Resource etkisi · Migration/Rollback planı · Risk. Süreç tek
kişinin görüşü değildir.

### Madde 40 — Reference Architecture zorunludur
Constitution yalnız ilkeleri değil, referans mimariyi de tanımlar: Platform Context Diagram · Domain Map ·
Capability Map · Event Flow · Executive Flow · Memory Architecture · Deployment · Security · Knowledge ·
Model Orchestration Architecture.

---

## Constitution Lifecycle

Constitution **yaşayan fakat kontrollü evrimleşen** bir belgedir. Her sürüm: Version Number · Effective Date ·
Change Summary · Breaking Principles · Migration Notes · Compatibility Statement · Revision History ile
yayımlanır. **Eski sürümler silinmez, yeni sürümler üzerine yazılmaz** — geçmiş tamamen izlenebilir kalır.
(Bkz. `CONSTITUTION_CHANGELOG.md`.)

## Son Direktif

Geliştirme odağı yeni özellik eklemek **değildir.** Odak: MIO'yu onlarca sektörü, yüzlerce entegrasyonu ve
birden fazla organizasyonu yıllarca yönetebilecek **modüler, sürdürülebilir, genişletilebilir ve kendi
ekosistemini yönetebilen** gerçek bir Cognitive Operating System yapmaktır. Mevcut çekirdek korunur.
Geriye-uyum korunur. Yeni çalışmalar çekirdeği büyütmek yerine **platformu ve ekosistemi olgunlaştırır.**
