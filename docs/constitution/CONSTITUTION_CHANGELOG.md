# Constitution Changelog

> Constitution **yaşayan fakat kontrollü evrimleşen** bir belgedir (Constitution Lifecycle). Eski sürümler
> **silinmez**, yeni sürümler eskinin üzerine **yazılmaz.** Her sürüm geçmişi tamamen izlenebilir kalır.
> Değişiklik yalnız **Constitution Revision** süreciyle yapılır: Mimari Etki Analizi → Geriye-Uyum Analizi →
> Risk Değerlendirmesi → Geçiş Planı → Revizyon Kaydı → yeni sürüm yayını.

---

## v1.0.0 — 2026-07-25 — RATIFIED (Initial Ratification)

- **Version:** 1.0.0
- **Effective Date:** 2026-07-25
- **Change Summary:** MIO Architectural Constitution v1.0 ve Governance Extensions v1.0 ilk kez birinci-sınıf
  (first-class), sürümlü artefact olarak repoya işlendi. Constitution artık projenin en üst mimari
  otoritesidir.
- **Breaking Principles:** Yok (ilk sürüm).
- **Migration Notes:** Mevcut 15 domain ve çekirdek KORUNUR (Madde 15 Evolutionary Architecture, Madde 29
  Backward Compatibility). Constitution'dan önce üretilen bileşenler geriye dönük olarak Constitution'a
  hizalanır; hiçbiri silinip yeniden yazılmaz. Compliance durumu için bkz. `../development/CURRENT_STATE.md`.
- **Compatibility Statement:** Bu ratifikasyon çalışan sistemi bozmaz; tam süit yeşil kalır (325 test).
- **Revision History:**
  - Constitution metni ve Governance Extensions daha önce konuşma bağlamında verilmişti; bu sürümle repoya
    kalıcılaştırıldı ve INDEX + CHANGELOG ile yönetişim altına alındı.
  - Önceki `docs/GOVERNANCE_EXTENSIONS.md` bu sürümle `docs/constitution/GOVERNANCE_EXTENSIONS_v1.0.md`
    olarak canonicalize edildi (eski dosya tarihsel referans olarak yerinde bırakıldı).

---

### Revizyon prosedürü (gelecekteki değişiklikler için)

1. Değişiklik önerisi bir **ADR** olarak açılır (Governance Extensions §3 şablonu).
2. Architecture Review + Constitution Compliance Review yapılır (Madde 38, §10).
3. Onaylanırsa **yeni sürüm dosyası** oluşturulur (`..._v1.1.md` / `..._v2.0.md`), eski dosya **korunur.**
4. Bu changelog'a Version/Effective Date/Change Summary/Breaking Principles/Migration Notes/Compatibility/
   Revision History ile kayıt eklenir.
5. `CONSTITUTION_INDEX.md` güncel sürüme işaret edecek şekilde güncellenir.
