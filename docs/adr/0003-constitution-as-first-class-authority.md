# ADR-0003 — MIO Architectural Constitution birinci-sınıf otorite olarak kabul

> Constitution refs: Madde 34 (Constitutional Governance), Madde 17 (Development Memory), Governance
> Extensions §3 (ADR şablonu). **Compliance: FULLY COMPLIANT.**

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-25 |
| **Supersedes** | — (ADR-0001, ADR-0002 yürürlükte kalır; bu ADR onları Constitution'a bağlar) |

## 1. Problem Statement
Constitution ve Governance Extensions yalnız konuşma bağlamında vardı; kalıcı, sürümlü, projede
referans verilebilir bir otorite değildi. Bu, uzun vadeli mimari tutarlılığı (Madde 1, 15) riske atar.

## 2. Context
15 domain FROZEN, 325 test yeşil. Kullanıcı, Constitution'ı en üst mimari otorite olarak repoya
kalıcılaştırmayı ve tüm alt dokümanların ona referans vermesini direktif olarak verdi.

## 3. Decision
`docs/constitution/` altında Constitution v1.0 + Governance Extensions v1.0 canonical, sürümlü artefact
olarak yayımlandı; INDEX + CHANGELOG ile yönetişim altına alındı. Development Memory (`docs/development/`),
Roadmap (`docs/roadmap/`) ve Reference Architecture (`docs/architecture/`) oluşturuldu. Bundan sonraki tüm
ADR/Domain Spec/Capability Contract Constitution'a ilgili madde numarasıyla referans verecek.

## 4. Alternatives Considered
- (a) Constitution'ı yalnız memory'de tutmak. (b) Tek README'ye gömmek. (c) Sürümsüz düz dosya.

## 5. Rejected Alternatives
- (a/b) Referans verilemez, denetlenemez, oturumlar arası kaybolur (Madde 17 ihlali). (c) Constitution
  Lifecycle (sürüm geçmişi izlenebilirliği) sağlanamaz.

## 6. Constitution Impact
Madde 34/36/17'yi operasyonel yapar. Hiçbir maddeyi değiştirmez (Addendum niteliğinde kalıcılaştırma).

## 7. Quality Attribute Impact
İyileştirir: Maintainability, Testability (fitness fonksiyonları için zemin), Explainability, Governance.
Olumsuz: yok (doküman-only).

## 8. Domain Impact
Domain kodu değişmedi; `mio_core/knowledge.py`'ye önceki oturumda eklenen additive `remove()` dışında çekirdek
dokunulmadı. Tüm domain README'leri Constitution'a bağlanacak (takip işi).

## 9. Migration Strategy
Mevcut `docs/GOVERNANCE_EXTENSIONS.md` tarihsel olarak yerinde bırakıldı; canonical sürüm
`docs/constitution/GOVERNANCE_EXTENSIONS_v1.0.md`. Geriye-uyum tam.

## 10. Rollback Strategy
Doküman-only; geri alma = `docs/constitution/`, `docs/development/`, `docs/roadmap/` ve bu ADR'ı kaldırmak.
Kod/testler etkilenmez.

## 11. Risks
Düşük. Tek risk: alt dokümanların Constitution'a referans vermeyi ihmal etmesi → Madde 37 fitness
fonksiyonlarıyla ileride otomatik denetlenecek.

## 12. Consequences
Constitution artık aktif yönetişim sistemi. Her büyük geliştirme Compliance raporu üretecek (Madde 36). Yeni
oturumlar `CURRENT_STATE.md`'den devam edecek.
