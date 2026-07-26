# MIO Architectural Constitution — Governance Extensions v1.0 (Addendum)

> ⚠️ **SUPERSEDED / canonicalized (2026-07-25):** Bu belgenin yürürlükteki canonical sürümü artık
> [`constitution/GOVERNANCE_EXTENSIONS_v1.0.md`](./constitution/GOVERNANCE_EXTENSIONS_v1.0.md)'dir. Bu dosya
> tarihsel referans olarak korunur (Constitution Lifecycle: eski sürümler silinmez).

> Constitution'ı (ADR-0001 Born Capable, ADR-0002 Cognitive OS) DEĞİŞTİRMEZ; doğal uzantısıdır.
> Amaç: yeni kural değil, uzun-vadeli tutarlılık için yönetişim mekanizmaları. Constitution ile aynı
> seviyede değil, tamamlayıcı olarak değerlendirilir.

## 1. Constitutional Priority Order
Mimari çelişkide öncelik (üst, alta feda edilemez):
1. Human Safety · 2. Security · 3. Constitutional Compliance · 4. Backward Compatibility · 5. Correctness ·
6. Reliability · 7. Maintainability · 8. Extensibility · 9. Performance · 10. Cost Optimization.
*Alt seviye optimizasyon üst seviye ilkeyi ihlal EDEMEZ* (performans için güvenlik azaltılamaz; maliyet
için geriye-uyum bozulamaz; sadeleştirme için Constitution ihlal edilemez).

## 2. Platform Invariants (değişmez; yalnız Constitution Revision ile değişir)
- Executive stratejik karar katmanıdır; **hiçbir zaman doğrudan dış sistemlerle konuşmaz** (Tool
  Orchestrator/Domain üzerinden).
- Her dış sistem önce ilgili Operation Domain'ine bağlanır. **Connector ≠ Operation.**
- Domain'ler birbirinin iç implementasyonunu bilemez.
- **Capability sözleşmeleri versiyonludur. Event sözleşmeleri versiyonludur.**
- Memory ortak bilgi katmanı; Event Bus ortak iletişim omurgası; Policy merkezi yönetişim; Audit tüm
  kritik işlemleri izler.
- **İnsan nihai otoritedir.** Çekirdek en küçük yapıda; Domain-First büyüme; hiçbir teknoloji ayrılmaz
  parça değil; tüm AI değiştirilebilir uzman bileşenlerdir.

## 3. Architectural Decision Principles (her ADR şu 12 başlığı içerir)
Problem Statement · Context · Decision · Alternatives Considered · Rejected Alternatives · Constitution
Impact · Quality Attribute Impact · Domain Impact · Migration Strategy · Rollback Strategy · Risks ·
Consequences. *Sadece teknik çözüm değil, NEDEN de belgelenir.*

## 4. Bounded Context Isolation Rule
Her Domain kendi iş modelinin sahibidir; başka Domain'in Entity/Aggregate/Repository/Internal Service/
Internal Event'ini DOĞRUDAN kullanamaz. İletişim yalnız: Public Capability Contract · Public API ·
Public Event · Approved Shared Kernel.

## 5. Canonical Vocabulary (platform genelinde tek anlam)
Domain (bağımsız bounded context) · Capability (versiyonlanabilir yetenek) · Operation (gerçek iş süreci)
· Executive (stratejik karar/orkestrasyon) · Policy (yönetişim/yetki) · Memory (kalıcı bilgi) · Knowledge
(yapısal/anlamsal bilgi) · Tool (tek iş yapan yardımcı) · Plugin (sonradan eklenen genişletme) · Adapter
(harici→sözleşme uyarlayıcı) · Connector (belirli dış sistem entegrasyonu) · MCP (standart harici yetenek
protokolü) · Digital Twin (gerçek sistemin dijital temsili) · Simulation (karar-öncesi senaryo).

## 6. Domain Lifecycle (Domain doğrudan Production'a girmez)
Need Analysis → Domain Proposal → Architecture Review → Constitution Compliance Review → Domain
Registration → Capability Registration → Policy Registration → Event Registration → Memory Registration →
Executive Integration → Monitoring → Evolution → Retirement.

## 7. Capability Maturity Levels
Experimental (araştırma) · Preview (kararlılık garantisiz) · Stable (üretimde kullanılabilir) · Production
(tam destekli) · Deprecated (yerine yeni geldi) · Retired (kullanılmaz). Executive seçimde bunu gözetir.

## 8. Technology Independence Principle
Hiçbir teknoloji (FastAPI/PostgreSQL/Mongo/Ollama/Docker/K8s/Redis/Kafka/...) Constitution'ın parçası
değildir. Teknoloji seçimi Reference Architecture / ADR / Implementation Standards seviyesinde tanımlanır.

## 9. AI Independence Principle
MIO hiçbir modele/sağlayıcıya/çıkarım altyapısına bağımlı değildir. LLM karar-verici değil, değiştirilebilir
uzman araçtır. Platformun zekâsı modellerde değil; Executive · Policy · Knowledge · Capability ·
Constitution katmanlarındadır.

## 10. Constitution Compliance Levels
FULLY COMPLIANT · SUBSTANTIALLY COMPLIANT (küçük teknik sapma) · PARTIALLY COMPLIANT (eksik uygulama) ·
EXCEPTION APPROVED (bilinçli istisna + zorunlu ADR) · NON-COMPLIANT (ihlal → production'a alınamaz).
Her büyük geliştirme sonunda bu seviyelerden biriyle raporlanır.

---
## MIO Core uyumu (mevcut kod)
- **Zaten sağlanan:** Executive dış sistemle konuşmaz (Tool Orchestrator); LLM=araç (Model Gateway);
  Policy merkezi (CapabilityPolicyEngine + PolicyProfiles); Audit (SQLiteToolAuditStore); Event Bus;
  Memory (E1/E5/knowledge); teknoloji-bağımsız stdlib çekirdek; insan onayı (requires_user_approval).
- **Bu addendum ile eklenen (kod):** `Capability.maturity` + Meta seçimde maturity gözetimi;
  `governance_ext.py` (PRIORITY_ORDER + ComplianceLevel + CanonicalVocabulary + conflict-resolution).
- **İleri iş (Domain katmanı geldiğinde):** Bounded Context isolation, Domain Lifecycle, Capability/Event
  contract versioning tam uygulama.
