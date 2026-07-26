# Capability Contracts — Index

> Constitution refs: Madde 16 (çekirdek küçük — yetenek Capability/MCP/Adapter/Plugin olarak), Madde 26
> (Capability Evolution), Madde 29 (Versioned Contracts), Governance Extensions §7 (Maturity Levels).

## Capability ilkeleri
- Her Capability **versiyonludur** (`contract_version`) ve bir **maturity** taşır: `experimental → preview →
  stable → production → deprecated → retired` (§7).
- Hiçbir Capability çekirdeğe doğrudan bağımlı değildir; yaşam döngüsü: `İhtiyaç → Tasarım → Contract →
  Sandbox → Test → Benchmark → Executive Review → Production → Monitoring → Learning → Version Mgmt` (Madde 26).
- Yeni yetenek eklerken sor: **"Bu gerçekten çekirdeğe mi ait?"** — Capability/MCP/Native Adapter/Plugin
  çözebiliyorsa çekirdeğe eklenmez (Madde 16).

## Mevcut altyapı (kaynak)
- **Capability modeli/registry:** `mio_core/capability.py` (`Capability`, `CapabilityRegistry`, maturity,
  contract_version, category, provenance).
- **Discovery:** Capability Discovery pipeline + Meta index.
- **Yürütme:** Tool Orchestrator (governance + audit tek geçiş noktası).
- **MCP:** MCP Hub · Meta MCP Manager v2.0 · transport plugin (STDIO/HTTP/SSE) · Marketplace.
- **Native karar-desteği:** `register_reasoning` (LLM-siz).

## Sözleşme kayıt yeri
Domain-seviyesi contract'lar ilgili pakette (`mio_core/domains/<ad>/contract.py`) ve README'de. Bağımsız
Capability sözleşmeleri olgunlaştıkça bu dizinde belgelenecek (Capability Management Domain — roadmap #8).
