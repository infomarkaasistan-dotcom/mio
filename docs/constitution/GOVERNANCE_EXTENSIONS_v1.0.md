# MIO Architectural Constitution — Governance Extensions v1.0

| | |
|---|---|
| **Version** | 1.0.0 |
| **Effective Date** | 2026-07-25 |
| **Status** | RATIFIED · Constitution Addendum |
| **Relation** | `MIO_ARCHITECTURAL_CONSTITUTION_v1.0.md`'nin doğal tamamlayıcısı (Governance Addendum). |

> Bu belge Constitution'a **yeni kural eklemez.** Amacı; mimari yorum farklılıklarını azaltmak, uzun vadeli
> tutarlılığı korumak, yeni geliştiricilerin platformu aynı şekilde yorumlamasını sağlamak ve büyük mimari
> kararların ortak bir çerçevede alınmasını kolaylaştırmaktır. Constitution ile aynı seviyede değerlendirilmez;
> onun **yönetişim uzantısıdır.**

---

## §1 — Constitutional Priority Order

Mimari kararlar arasında çelişki oluştuğunda (performans, güvenlik, maliyet, modülerlik, geriye-uyum aynı anda
en üst seviyede sağlanamayabilir) aşağıdaki **öncelik sırası** uygulanır:

1. **Human Safety**
2. **Security**
3. **Constitutional Compliance**
4. **Backward Compatibility**
5. **Correctness**
6. **Reliability**
7. **Maintainability**
8. **Extensibility**
9. **Performance**
10. **Cost Optimization**

Alt seviyedeki hiçbir optimizasyon üst seviyedeki ilkeyi ihlal edemez. *Performans için güvenlik azaltılamaz;
maliyet için geriye-uyum bozulamaz; sadeleştirme için Constitution ihlal edilemez.*

---

## §2 — Platform Invariants (Değişmez Mimari Gerçekler)

Platformun temel kimliğini oluşturur. Yeni teknoloji/Domain/Capability bunları değiştiremez. Yalnız
Constitution Revision ile değişebilir.

- Executive sistemin **stratejik karar** katmanıdır.
- Executive hiçbir zaman **doğrudan dış sistemlerle** konuşmaz.
- Her dış sistem önce ilgili **Operation Domain**'ine bağlanır.
- **Connector hiçbir zaman Operation değildir.**
- Domain'ler birbirinin iç implementasyonlarını bilemez.
- **Capability sözleşmeleri versiyonludur.**
- **Event sözleşmeleri versiyonludur.**
- Memory ortak bilgi katmanıdır.
- Event Bus ortak iletişim omurgasıdır.
- Policy merkezi yönetişim katmanıdır.
- Audit tüm kritik işlemleri izler.
- **İnsan nihai otoritedir.**
- Çekirdek mümkün olan **en küçük** yapıda tutulur.
- Platform **Domain-First** büyür.
- Hiçbir teknoloji platformun ayrılmaz parçası değildir.
- Tüm AI sistemleri **değiştirilebilir uzman bileşenlerdir.**

---

## §3 — Architectural Decision Principles (ADR Şablonu)

Her ADR şu başlıkları içerir: **1.** Problem Statement · **2.** Context · **3.** Decision · **4.** Alternatives
Considered · **5.** Rejected Alternatives · **6.** Constitution Impact · **7.** Quality Attribute Impact ·
**8.** Domain Impact · **9.** Migration Strategy · **10.** Rollback Strategy · **11.** Risks · **12.**
Consequences. Hiçbir ADR yalnız teknik çözüm anlatmaz; **kararın neden alındığı** da belgelenir.

---

## §4 — Bounded Context Isolation Rule

Her Domain kendi iş modelinin sahibidir. Hiçbir Domain başka bir Domain'in Entity/Aggregate/Repository/
Internal Service/Internal Event gibi **iç yapılarını doğrudan kullanamaz.** İletişim yalnız: **Public
Capability Contract · Public API · Public Event · Approved Shared Kernel** yollarıyla olur.

---

## §5 — Canonical Vocabulary

Platform genelinde tek anlam taşır:

| Terim | Anlam |
|---|---|
| **Domain** | İş alanını temsil eden bağımsız bounded context. |
| **Capability** | Platformun gerçekleştirebildiği versiyonlanabilir yetenek. |
| **Operation** | Gerçek dünyadaki iş süreci. |
| **Executive** | Stratejik karar ve orkestrasyon katmanı. |
| **Policy** | Yönetişim ve yetki kuralları. |
| **Memory** | Platformun kalıcı bilgi katmanı. |
| **Knowledge** | Yapısal ve anlamsal bilgi. |
| **Tool** | Tek bir işi yapan yardımcı bileşen. |
| **Plugin** | Platforma sonradan eklenen genişletme modülü. |
| **Adapter** | Harici sistemleri platform sözleşmelerine uyarlayan katman. |
| **Connector** | Belirli bir dış sistemle haberleşen teknik entegrasyon bileşeni. |
| **MCP** | Standartlaştırılmış harici yetenek erişim protokolü. |
| **Digital Twin** | Gerçek sistemin dijital temsili. |
| **Simulation** | Karar öncesi senaryo değerlendirme süreci. |

---

## §6 — Domain Lifecycle

`Need Analysis → Domain Proposal → Architecture Review → Constitution Compliance Review → Domain Registration →
Capability Registration → Policy Registration → Event Registration → Memory Registration → Executive
Integration → Monitoring → Evolution → Retirement`. **Hiçbir Domain doğrudan Production'a eklenmez.**

---

## §7 — Capability Maturity Levels

`Experimental` (araştırma) · `Preview` (kullanılabilir, kararlılık garantisiz) · `Stable` (üretimde) ·
`Production` (tam destekli) · `Deprecated` (yerine yenisi geldi) · `Retired` (kullanılmaz). Executive
Capability seçiminde bu seviyeleri dikkate alır.

---

## §8 — Technology Independence Principle

Constitution teknoloji bağımsızdır. FastAPI/PostgreSQL/MongoDB/Ollama/Docker/Kubernetes/Redis/Kafka veya
gelecekteki hiçbir teknoloji Constitution'ın parçası değildir. Teknoloji seçimleri **Reference Architecture /
ADR / Implementation Standards** seviyesinde tanımlanır.

---

## §9 — AI Independence Principle

MIO hiçbir modele/sağlayıcıya/çıkarım altyapısına bağımlı değildir. **LLM'ler karar verici değil, uzman
araçtır** — değiştirilebilir, birlikte çalışabilir, devre dışı bırakılabilir, alternatifiyle değiştirilebilir.
Platformun zekâsı modellerde değil; **Executive, Policy, Knowledge, Capability ve Constitution** katmanlarındadır.

---

## §10 — Constitution Compliance Levels

Her büyük geliştirme sonunda uyum şu seviyelerden biriyle raporlanır:

| Seviye | Anlam |
|---|---|
| **FULLY COMPLIANT** | Tamamen uyumlu. |
| **SUBSTANTIALLY COMPLIANT** | Küçük teknik sapma var; mimari ilkelere uygun. |
| **PARTIALLY COMPLIANT** | Bazı maddeler eksik uygulanmış. |
| **EXCEPTION APPROVED** | Bilinçli istisna (ilgili ADR **zorunlu**). |
| **NON-COMPLIANT** | Constitution ihlali; **production'a alınamaz.** |

Bu sınıflandırma tüm Architecture Review süreçlerinde standarttır.
