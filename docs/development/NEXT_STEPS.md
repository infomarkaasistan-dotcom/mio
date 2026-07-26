# MIO — NEXT STEPS

> Her yeni oturum **önce bu dosyayı okuyarak** başlar (Constitution Madde 17). Öncelik sırası + bekleyen
> kararlar + bilinçli ertelenenler.

## Aktif durum
16 domain (15 FROZEN + Capability Mgmt in_progress), 334 test yeşil, Constitution v1.0 ratified. **Tüm
domainler Maturity: STABLE — Production DEĞİL** (`MATURITY_AUDIT.md`). Compliance: **PARTIALLY** (Madde 27/28
ihlal). Development Directive yürürlükte: **başarı ölçütü = olgunluk + uyum, test/domain sayısı değil.**

## Faz sırası (Development Directive)
`Faz 4 Production-Grade Domain 🔄 → Faz 5 Platform Maturity Audit ✅(başladı) → Faz 6 Production Hardening ⏳ →
Faz 7 Operational Validation ⏳ → Faz 8 İlk Operation Domain ⏳`. **Domainler bitince yeni domain YOK →
Production Hardening.**

## Öncelik sırası (öneri — kullanıcı onayına tabi)

1. **Platform Domain boşluklarını kapat (Constitution Faz 2 tamamlama).** Çekirdekte servis hâlinde olan ama
   henüz tam bounded-context Domain olmayanları Domain'leştir (Madde 3–4, Evolutionary — Madde 15):
   - **Capability Management Domain** (CapabilityRegistry/Discovery'yi sarar).
   - **MCP Management Domain** (MCP Hub / Meta MCP'yi sarar).
   - **Audit & Compliance Domain** (audit_store'u sarar + Constitution Compliance raporlama).
   - **Resource & Runtime Domain** (Resource Awareness — Madde 30; hardware/CPU/GPU/RAM izleme).
2. **Multi-Organization temeli (Madde 10).** Tüm domain repository'lerine `org_id` bağlamı — geriye-uyumlu
   (varsayılan tek org). Yeni katman/adaptörle, çekirdeği kırmadan.
3. **İlk Operation Domain örneği (Madde 6–9): Marketplace Operations.** Connector/Adapter deseni (Trendyol/
   Amazon = adapter) — "Connector değil Operation" ilkesinin referans implementasyonu.
4. **Self Development altyapısı (Madde 18) — gözlem-only başlangıç:** System Observation + Repository
   Intelligence (öneri üretir, uygulamaz; Executive onayı şart).
5. **Architectural Fitness Functions (Madde 37):** CI kontrolleri — domain isolation, contract versiyon,
   circular dependency, test coverage.

## Bekleyen kararlar
- Faz 2/3 domain sıralaması Constitution roadmap'iyle nasıl birebir hizalanacak? (Mevcut yapı korunur;
  eksikler eklenir — silme yok.)
- Multi-Org modeli: repository-seviyesi `org_id` mi, ayrı şema mı? (Öneri: repository-seviyesi, geriye-uyumlu.)
- HTTP/API katmanı ne zaman? (Domainler contract-hazır; Dashboard/API event-driven eklenebilir.)

## Bilinçli olarak ertelenenler
- Digital Twin (Madde 22), Simulation-First (Madde 23), Federation, Distributed Execution — mimari tanımlı,
  Domain implementasyonu roadmap Faz 5.
- Gerçek-zaman scheduler sürücüsü (arka-plan thread) — güvenlik gereği elle tick; talep gelince adaptör.

## Her yeni Domain için ZORUNLU (Domain Geliştirme Kuralı + Madde 4)
model+kural · Capability · Events · Policy · Audit · Security/authz · Versioning/backward-compat · MCP/Native
Adapter (gerekiyorsa) · API/Contract · Servis · Repository · Validation · Hata yönetimi · Observability ·
Config · Unit+Integration+Smoke test · Dokümantasyon → **tüm testler + geriye-uyum yeşil → FREEZE.** Placeholder/
TODO/stub/mock YOK.
