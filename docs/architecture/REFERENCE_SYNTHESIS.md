# Reference Synthesis — MIO'nun Üç Referans Tabandan Sentezi

> Constitution refs: Governance Extensions §8 (Technology Independence), §9 (AI Independence), Madde 15
> (Evolutionary). **MIO, üç referans kod tabanının güçlü yönlerinden sentezlenen YENİ, BAĞIMSIZ bir üründür.**
> Hiçbiri MIO'nun çekirdeği/tabanı değildir. Yaklaşım **kod kopyalamak değil, mimari desen çıkarmaktır**
> ("Merkez proje yok. Merkez mimari var.").

Üç referans: **OpenJarvis** · **MIO Beyin** · **MarkaAsistan**. Her birinden çıkarılan desen, MIO Core'a göre
sınıflandırıldı → tekilleştirildi → en olgun hâli korunarak Constitution'a uyarlandı.

---

## 1) OpenJarvis → *Referans Mimari Desenler* (yaşayan asistan runtime'ı)

**Ne aldık (kod değil, mimari desen):**

| OpenJarvis'ten çıkarılan desen | MIO'daki somut karşılığı |
|---|---|
| Event-driven runtime omurgası | `EventBus` (record + subscribe_all) — tüm domainler event publish eder |
| Scheduler / lifecycle / autonomous loop | **Domain 12 Scheduler/Lifecycle** — deterministik tick, LoopGuard, yaşam-döngüsü |
| Plugin / capability discovery pipeline | Capability Discovery + `CapabilityRegistry` + Meta index |
| MCP entegrasyonu & marketplace | MCP Hub · Meta MCP Manager v2.0 · Marketplace · transport plugin (STDIO/HTTP/SSE) |
| Proaktif "morning-digest" / periyodik operasyon fikri | Scheduler öz-bakım işleri (memory/executive/learning consolidation) |
| Crash-consistency / zombie-guard endişesi | Scheduler'da **zombie-guard** + WAL + atomik transaction (kök çözüm) |

**Ne almadık / farklı yaptık (dürüst):** OpenJarvis'in kendi kod tabanından **hiçbir satır kopyalanmadı.**
Duvar-saati arka-plan thread modeli yerine **deterministik mantıksal tick** seçildi (ilk oturumdaki "çoklu
model → donma" riskinin kök çözümü). OpenJarvis bir "asistan"; MIO bir "operasyon işletim sistemi" — sohbet
MIO'da yalnız bir arayüzdür (Madde 12).

---

## 2) MIO Beyin → *Yaşayan Bilişsel Çekirdek* (Executive Brain)

**Ne aldık (kavramsal çekirdek, MIO Core'a evrildi):**

| MIO Beyin'den çıkarılan kavram | MIO Executive OS'taki somut karşılığı |
|---|---|
| Yaşayan zihin çekirdeği: güdü/inanç/çelişki/öngörü/emergence | **E5 CognitiveEngine** — belief, **çelişki 1. sınıf**, refutation, belief revision |
| Executive Brain (stratejik akıl) | **E1–E4** — Persistent Executive State, Goal Mgmt, Executive Review, Decision & Governance |
| Purpose ≠ Mission ayrımı, değerler | Purpose Layer (primary/secondary objective, core principle, Financial Rule) |
| Born Capable (boş doğmaz) | Doğuşta identity + mission + innate belief + tipli innate knowledge + 14 Domain Brain |
| Bilinç/iç-gözlem | Cognitive Identity (Madde 11 iç-gözlem) + Self Awareness Layer |
| LLM'den bağımsız süreklilik | Tüm bilişsel çekirdek deterministik + kalıcı; LLM olmadan çalışır |

**Ne almadık / farklı yaptık:** MIO Beyin AKTİF/referans bir Executive Brain'di; MIO Executive OS onun
**anayasa v2.0'a evrilmiş, platformlaşmış** hâli değil — ondan **mimari desenleri** (bilişsel süreklilik,
çelişki-öncelikli inanç, Born Capable) çıkarıp bağımsız çekirdeğe uyarladık. "Beyin" bir uygulamaydı; burada
o desenler **çekirdek invariant** oldu (Governance Extensions §2).

---

## 3) MarkaAsistan → *Operasyonel Danışman & Dürüstlük Deseni*

**Ne aldık (davranış/güvence desenleri):**

| MarkaAsistan'dan çıkarılan desen | MIO'daki somut karşılığı |
|---|---|
| "LLM önerir, deterministik reddeder" (ufuk-dışını eler) | Model Gateway (LLM=araç) + Communication advisor→**deterministik fallback**; Planning ufuk doğrulama |
| Domain Brain deseni (marka/pazarlama vertikalleri) | **Domain 11 Vertical Domain Brains** (Finance/Marketing/Sales… advise+guardrail) |
| No-mock-data / dürüstlük ilkesi (Anayasa Madde 8) | Sistem-geneli invariant: uydurma yok; "bilmiyorum/bağlı değil" meşru; dürüst fallback |
| Finansal koruma / onay kapıları | **Financial Rule** — Policy innate + Finance Brain guardrail (financial_commitment→require_approval) |
| Üretim akışı / ROAS / kayıt registry disiplini | Execution audit trail + Learning outcome→emergence + write-through kalıcılık |

**Ne almadık / farklı yaptık:** MarkaAsistan tek-ürün/tek-marka odaklıydı; MIO **çok-organizasyonlu,
çok-sektörlü** bir platformdur (Madde 10). MarkaAsistan'ın "brain=AI Agent" uygulaması yerine, dikey beyinler
burada **tavsiye verir, KARAR VERMEZ** (karar Executive/E4'e gider) — güç ayrımı Constitution'a taşındı.

---

## Sentez ilkesi (özet)

- **OpenJarvis** → *nasıl yaşar/işler* (runtime, event, scheduler, MCP, plugin, discovery).
- **MIO Beyin** → *nasıl düşünür/kim olduğunu bilir* (E1–E5, inanç/çelişki, Born Capable, Purpose).
- **MarkaAsistan** → *nasıl güvenli & dürüst iş yapar* (LLM=danışman, no-mock, finansal koruma, vertikaller).

Üçünün de **sınırları** görüldüğü için hiçbiri taban alınmadı: bir projeyi taban almak, onun borçlarını miras
almak demekti. Bağımsız MIO Core tanımı, **en iyi parçaları borç olmadan** birleştirdi — ve hepsi Constitution
altında tek mimari vizyona bağlandı. (Bkz. `docs/constitution/`.)
