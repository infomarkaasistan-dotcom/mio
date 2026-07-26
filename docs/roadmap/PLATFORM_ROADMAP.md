# MIO Platform Roadmap — 40 Domain · 5 Faz

> Constitution refs: Madde 3 (Domain-First), Madde 5 (ana operasyon alanları bugünden tanımlı), Madde 39
> (Platform Evolution — yeni Domain son çare). Bu roadmap **hedef Domain haritasıdır**; her Domain
> `Governance Extensions §6 Domain Lifecycle` ve `Domain Geliştirme Kuralı` ile üretilip **FREEZE** edilir.

## Durum lejantı
✅ FROZEN (üretim) · 🟡 çekirdekte servis (Domain'leştirilecek) · ⬜ planlı

---

## Faz 1 — Cognitive Core Domains
| # | Domain | Durum | Sorumluluk |
|---|---|---|---|
| 1 | Executive | ✅ | Stratejik karar, planlama, koordinasyon, delegasyon, hedef yönetimi, orkestrasyon |
| 2 | Memory | ✅ | WM/STM/LTM/episodik/semantik/prosedürel + bellek yaşam döngüsü |
| 3 | Knowledge | ✅ | Bilgi yönetimi, tipli bilgi, ontoloji, semantik arama, doğrulama, Knowledge Graph |
| 4 | Reasoning | ✅ | Mantıksal çıkarım, çok-adımlı muhakeme, alternatif üretimi, öz-değerlendirme |
| 5 | Planning | ✅ | Uzun vadeli planlama, görev ayrıştırma, bağımlılık, kaynak planlama |
| 6 | Learning | ✅ | Deneyimden öğrenme, geri bildirim, performans optimizasyonu, sürekli gelişim |
| 7 | Goal Management | ✅ | Amaç oluşturma, önceliklendirme, takip, başarı ölçümü, yaşam döngüsü |

## Faz 2 — Platform Domains
| # | Domain | Durum | Not |
|---|---|---|---|
| 8 | Capability Management | ✅ | CapabilityRegistry'yi sarar (maturity §7, seçim, evolution) — STABLE |
| 9 | MCP Management | ✅ | MCPHub'ı sarar (trust yaşam-döngüsü Madde 24, kalıcı kayıt) — STABLE |
| 10 | Policy & Governance | ✅ | Domain 14 (Policy) + core PolicyProfiles/E4 |
| 11 | Security & Identity | ✅ | Domain 15 (Security: RBAC/audit/redact/lock) |
| 12 | Audit & Compliance | ✅ | Değişmez ledger + Constitution Compliance kaydı (§10) — STABLE |
| 13 | Resource & Runtime | ✅ | Resource Awareness (Madde 30): snapshot + bütçe + darboğaz — STABLE |
| 14 | Observability & Diagnostics | ✅ | Domain 13 (Observability) + core Diagnostics |
| 15 | Communication | ✅ | Domain 8 (Communication) |
| 16 | Automation & Workflow | 🟡 | Domain 12 (Scheduler) tick/lifecycle var → workflow orkestrasyon genişlet |

## Faz 3 — Intelligence Domains
| # | Domain | Durum | Not |
|---|---|---|---|
| 17 | Software Engineering | ✅ | Deterministik ast analizi + Anayasa quality gate + artifact/task — STABLE |
| 18 | Research | ✅ | Deterministik soruşturma + sentez (corroboration/doğrulama) — STABLE |
| 19 | Document Intelligence | ✅ | Deterministik analiz + kural-sınıflandırma + extractive özet — STABLE |
| 20 | Data Analytics | ✅ | Deterministik tablo analitiği (stdlib): istatistik/KPI/trend/anomali — STABLE |
| 21 | Business & Operations | ✅ | Deterministik süreç/darboğaz + iş kuralı motoru — STABLE |
| 22 | Finance | ✅ | Deterministik defter + nakit akışı/runway + Financial Rule (Madde 4) — STABLE |
| 23 | Sales & CRM | ✅ | Deterministik pipeline (ağırlıklı değer/win rate) + lead qualification — STABLE |
| 24 | Marketing & Growth | ✅ | Deterministik kampanya KPI (CTR/CVR/CPA/ROAS) + kanal kırılımı — STABLE |
| 25 | Customer Success | ✅ | Deterministik health score + churn-risk + ticket/CSAT — STABLE |

> Not: Faz 3'ün 8 dikey beyni **Domain 11 (Vertical Domain Brains)** olarak advice+guardrail seviyesinde
> hazır; buradaki hedef, her birini tam **Operation Domain** (connector/adapter'lı) hâline getirmek.

## Faz 4 — Multimodal & Integration Domains
| # | Domain | Durum |
|---|---|---|
| 26 | Vision | ✅ (STABLE — orkestrasyon + connector routing, dürüst no_connector) |
| 27 | Voice | ✅ (STABLE — STT/TTS orkestrasyon, dürüst no_connector) |
| 28 | Media Generation | ✅ (STABLE — üretim orkestrasyon, dürüst no_connector) |
| 29 | Web Intelligence | ✅ (STABLE — orkestrasyon + allowlist güvenliği, dürüst no_connector) |
| 30 | Device & Native Integration | ✅ (STABLE — risk sınıflandırma + Madde 24 onay kapısı + connector routing, dürüst no_connector) |
| 31 | IoT | ✅ (STABLE — thing registry + deterministik telemetri/eşik-uyarı + aktüatör Madde 24 onay kapısı + connector routing, dürüst no_connector) → **FAZ 4 TAMAM** |
| 32 | Model Management | ✅ (STABLE — registry + yaşam-döngüsü + DETERMİNİSTİK seçim (Madde 1) + provider routing + Madde 24 retire onayı, dürüst no_connector) |
| 33 | Multi-Agent | ✅ (STABLE — agent registry + DETERMİNİSTİK görev atama (Madde 3) + koordinasyon durum makinesi + Madde 24 onay kapısı, dürüst no_agent/no_connector) |
| 34 | Marketplace / Ecosystem | ✅ (STABLE — listing registry + DETERMİNİSTİK uyumluluk/allowlist + Madde 24 onay/otomatik-red + kurulum durum makinesi, dürüst no_connector) |
| 35 | Knowledge Marketplace | ✅ (STABLE — bilgi paketi registry + DETERMİNİSTİK lisans/allowlist + provenance izlenebilirlik + Madde 24 onay/otomatik-red + import durum makinesi, dürüst no_connector) |
| 36 | Federation | ✅ (STABLE — peer registry + DETERMİNİSTİK host allowlist/scope egemenlik + Madde 24 paylaşım onayı + güven/paylaşım durum makineleri, dürüst no_connector) |
| 37 | Distributed Execution | ✅ (STABLE — worker node registry + DETERMİNİSTİK dağıtım/zamanlama + idempotency effectively-once + node sağlık + Madde 24 onay, dürüst no_node/no_connector) |
| 38 | Autonomous Operations | ✅ (STABLE — kural registry + DETERMİNİSTİK tetik + ÖNERİ üretimi (autonomy≠karar) + Madde 24 onay + kapalı-döngü allowlist+opt-in, dürüst no_connector) |
| 39 | Simulation & Digital Twin | ✅ (STABLE — twin registry + DETERMİNİSTİK what-if simülasyon (sim≠gerçeklik, mutasyonsuz) + Madde 24 yansıtma onayı + senaryo kaydı, dürüst no_simulator) |
| 40 | Extension SDK | ✅ (STABLE — uzantı manifest registry + DETERMİNİSTİK izin-scope doğrulama + en-az-yetki + Madde 24 etkinleştirme/otomatik-red + host sandbox delege, dürüst no_connector) → **FAZ 5 TAMAM + TÜM ANA DOMAINLER TAMAM** |
| 30 | Device & Native Integration | ⬜ |
| 31 | IoT | ⬜ |

## Faz 5 — Distributed Cognitive Platform
| # | Domain | Durum |
|---|---|---|
| 32 | Model Management | 🟡 (Model Gateway çekirdekte) |
| 33 | Multi-Agent Collaboration | 🟡 (Domain Brain runtime çekirdekte) |
| 34 | Marketplace & Ecosystem | 🟡 (Capability/MCP Marketplace çekirdekte) |
| 35 | Knowledge Marketplace | ⬜ |
| 36 | Federation | ⬜ (Desktop/Server/Cloud MIO) |
| 37 | Distributed Execution | ⬜ |
| 38 | Autonomous Operations | ⬜ (Self Development — Madde 18) |
| 39 | Simulation & Digital Twin | ⬜ (Madde 22–23) |
| 40 | Extension SDK | ⬜ (3rd-party SDK) |

---

## Yatay mimari yetenekler (Domain-üstü, Constitution zorunlu)
Bu roadmap'e paralel, tüm Domain'lere işleyecek kesişen ilkeler: Multi-Organization (Madde 10) · Digital Twin
(22) · Simulation-First (23) · Autonomous Execution Governance (24) · Unified Knowledge (25) · Resource
Awareness (30) · Time Awareness (31) · Human Governance (32) · Resilience (28) · Versioned Contracts (29) ·
Observability & Explainability (27).

## Öncelik ilkesi
Yeni Domain oluşturmak **son çaredir** (Madde 39). Önce: mevcut Domain genişletilebilir mi? Capability/MCP/
Plugin/Connector çözer mi? Ancak hayırsa yeni Domain.
