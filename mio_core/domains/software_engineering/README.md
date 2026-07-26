# Software Engineering Domain (Faz 3 · Domain 20) — Maturity: STABLE

> Constitution refs: Madde 14 (üretim-kalite), Madde 37 (Fitness Functions zemin), Governance Extensions §9
> (LLM danışman). **Compliance: FULLY COMPLIANT (kapsam içi).**

Deterministik SE çekirdeği: stdlib `ast` ile **GERÇEK statik analiz** + Anayasa **'placeholder yok' quality
gate** + artifact/engineering-task registry. Kod-üretimi LLM danışmana bırakılır (**karar vermez**);
**doğrulama deterministiktir** ve çekirdektedir.

## Public API (`SoftwareEngineeringDomain`)
| Operasyon | Açıklama |
|---|---|
| `analyze_code(actor, source, language)` | Deterministik rapor: fonksiyon/sınıf/LOC/docstring/karmaşıklık + issue'lar |
| `quality_gate(actor, source, language)` | **Anayasa kapısı**: placeholder/stub/TODO/syntax → **reject** |
| `register_artifact / list_artifacts` | Kod artefaktı registry'si |
| `create_task / update_task_status / list_tasks` | Mühendislik görevi (feature/bug/refactor/test/docs) |
| `stats / contract` | Observability + versioned sözleşme |

## Deterministik analiz (stdlib `ast` + re)
- **Metrik:** LOC, fonksiyon, sınıf, döngüsel-karmaşıklık (dallanma), docstring coverage.
- **Stub tespiti (ast):** gövdesi yalnız `pass` / `...` / `raise NotImplementedError` olan fonksiyon/sınıf.
- **Placeholder tespiti (re):** TODO/FIXME/XXX/HACK/placeholder/stub/dummy/mock.
- **Syntax:** geçersiz Python → `syntax_error` issue.

## Invariantlar
- **Determinizm:** aynı kaynak → aynı rapor (rastgelelik yok, LLM yok).
- **Quality gate Anayasa'yı uygular:** placeholder/stub/TODO **reddedilir** (Madde 14 / no-mock).
- **Kod-üretimi karar değildir:** LLM danışman üretir; doğrulama deterministik çekirdekte.

## Yetki
Okuma/analiz: owner + Executive/Engineering/Operations/Planning/Workflow/Reasoning. Yazma (artifact/task):
owner + Executive/Engineering/Operations/Workflow.

## Production bileşenleri (placeholder YOK)
Model (Artifact/EngTask) · Analyzer (ast, deterministik) · Repository (SQLite) · Contract v1.0.0 · Events
(analyzed/quality_gate/artifact_registered/task_created/task_updated) · Authorization · Validation · Error
hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_software_engineering_domain.py`) · Docs.

## Bağımlılıklar (DI)
`SoftwareEngineeringDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.software_engineering`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
