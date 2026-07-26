# Simulation & Digital Twin Domain (Faz 5 · Domain 42) — Maturity: STABLE

> Constitution refs: **Madde 24 (simülasyon sonucunu gerçeğe/ikize yansıtma onay ister)**, Madde 8 (dürüstlük;
> sim ≠ gerçeklik), Madde 6/7 (dış simülatör adapter üzerinden), Madde 16. **Compliance: FULLY COMPLIANT
> (kapsam içi).**

**Anayasa gereği SİMÜLASYON ≠ GERÇEKLİK; simülasyon sonucu ÖNERİDİR, ikiz modeline/gerçeğe otomatik uygulanmaz;
yansıtma Madde 24 onayı ister.** Çekirdek: dijital ikiz (twin) registry (gerçek varlığın durum modeli) +
**deterministik durum/geçiş simülasyonu** (state + adım/effect; what-if, LLM'siz) + senaryo çalıştırma kaydı.
`simulate()` **ikizi MUTATE ETMEZ** (durum kopyası üzerinde çalışır). Gerçek fiziksel model gerektiren ikiz için
enjekte edilen **dış simülatör adapter (DI)**'a delege. **Adapter yoksa `no_simulator`** (Madde 8). Gerçek varlık
kontrolü **çekirdekte yok** (o, Execution/Autonomous Ops üzerinden ve ayrı onayla).

## Public API (`DigitalTwinDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_simulator(kind, fn, name)` | GERÇEK/dış fiziksel simülatör connector'ı bağla (DI) |
| `register_twin(actor, name, kind, state, requires_external_sim)` | İkiz kaydı (durum modeli) |
| `update_state(actor, twin_id, state)` | İkizin GERÇEK gözlemlenen durumunu güncelle (telemetri; simülasyon değil) |
| `simulate(actor, twin_id, steps, scenario)` | **DETERMİNİSTİK what-if** — kopya üstünde; ikizi MUTATE ETMEZ |
| `apply_result(actor, run_id)` | Sim sonucunu ikize yansıt (**owner/Executive** — Madde 24) |
| `get_twin / list_twins / get_run / list_runs / simulators / stats / contract` | Sorgu + sözleşme |

## Deterministik simülasyon (LLM'siz)
`apply_step(state, step)` — `STEP_OPS = {set, inc, dec, mul, min, max}` durum değişkenleri üzerinde deterministik
etki uygular; girdi state **mutate edilmez**, yeni state + trace döner. `simulate` adımları ikizin durum
**kopyasına** uygular; **aynı girdi → aynı çıktı**. Dış `kind` simülatörü bağlıysa ona delege (yine deterministik
beklenir); yoksa **dahili deterministik simülatör** (gerçek hesap, placeholder DEĞİL).

## sim ≠ gerçeklik sınırı (Madde 24)
`simulate()` **ikizin gerçek durumunu asla değiştirmez** — sonuç bir SimulationRun (öneri) olarak saklanır. Bu
sonucu ikiz modeline commit etmek **yalnız `apply_result` ile ve owner/Executive onayıyla** olur. `requires_external_
sim=True` ikizde adapter yoksa `no_simulator` (dürüst).

## Invariantlar
- **Mutasyonsuz simülasyon:** `simulate()` ikizi değiştirmez (sim ≠ gerçeklik).
- **Yansıtma onayı (Madde 24):** sonucu ikize commit yalnız owner/Executive onayıyla; iki kez yansıtılamaz.
- **Determinizm:** aynı girdi → aynı sonuç; LLM karar verici değil.
- **Dürüstlük (Madde 8):** dış simülatör gerekli+yoksa `no_simulator`; uydurma sonuç yok.
- **Gerçek varlık kontrolü çekirdekte yok.**

## Yetki
Okuma: owner + Executive/Operations/Engineering/Planning/Reasoning/Perception. İkiz/simülasyon: owner + Executive/
Operations/Engineering/Planning. **Yansıtma (apply_result): owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Twin/SimulationRun + deterministik `apply_step`/STEP_OPS) · Repository (SQLite; twin/sim_run) · Contract
v1.0.0 · Events (registered/simulated/no_simulator/sim_failed/result_applied) · Authorization (approver ayrımı) ·
Validation · Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_digital_twin_domain.py`) · Docs.

## Bağımlılıklar (DI)
`DigitalTwinDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.digital_twin`). Gerçek/dış
simülatörler sonradan `register_simulator` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek fiziksel simülatör/varlık bağlı değil
(`no_simulator` = **dürüst** durum; dahili deterministik simülatör gerçek hesaptır, placeholder değil). Bkz.
`docs/development/MATURITY_AUDIT.md`.
