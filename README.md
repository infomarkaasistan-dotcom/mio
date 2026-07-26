# MIO Executive OS

**Bağımsız bir Executive Operating System.** OpenJarvis, MIO Beyin ve MarkaAsistan yalnızca referans kod
tabanlarıdır; hiçbiri MIO'nun çekirdeği değildir. MIO Core, bu üç projeden çıkarılan en olgun yeteneklerin
adaptörlerle birleştiği yeni bir mimaridir. *"Merkez proje yok. Merkez mimari var."*

## Çekirdek ilkeler
- **Executive ≠ Execution.** Execution (kod/görev/araç/içerik) tek başına karar vermez; her önemli karar
  Executive'den geçer.
- **LLM asla beyin değildir** — gerektiğinde çağrılan, değiştirilebilir bir danışmandır. MIO'nun kimliği,
  sürekliliği, hedefleri, hafızası ve karar mekanizmaları LLM'den **bağımsız, deterministik ve kalıcıdır.**
- **Executive Core stdlib-only** (model/framework bağımlılığı yok) → hiçbir modele bağımlı değildir.
- **Amaç:** görev tamamlamak değil, **uzun-vadeli hedefleri yönetmek.**

## Mimari (özet)
- **Executive:** E1 Persistent State · E2 Goal · E3 Review (+Evidence Acquisition, +Belief Revision) ·
  E4 Decision & Governance (+DEFER) · E5 Cognitive.
- **Execution:** Planner · Agents/Runtime · Capability/Tool (+ses) · Model Gateway.
- **Infrastructure:** Registry · Event · Memory(+vektör) · Scheduler · Trace · Guards · Learning.

Mimari sözleşmeler için `mio-beyin/MIO_*` belgelerine bakın (referans dokümantasyon).

## Şu anki içerik
- `mio_core/executive/` — **E1 Persistent Executive State** (üretim-kalite, LLM-bağımsız):
  - `models.py` — Identity/Mission/GoalRef/Strategy/Decision(+öğrenme zinciri)/Lesson
  - `store.py` — `ExecutiveStateStore` protokolü + `SQLiteExecutiveStateStore` (gerçek kalıcılık)
  - `state.py` — deterministik servis: `consult`/`record_decision`/`link_outcome`/`set_strategy`/…

Karar defteri tam öğrenme zincirini taşır:
`Expectation → Decision → Evidence → Outcome → Prediction Error → Belief Update`.

## Test
```
python -m pytest
```
