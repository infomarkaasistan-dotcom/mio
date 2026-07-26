# CI/CD — Continuous Integration (Production Hardening #4)

> **Durum:** Workflow taslağı hazır (`.github/workflows/ci.yml`). **Henüz aktif değil** çünkü repo bir git deposu
> değil / GitHub remote'u yok. Etkinleştirmek için aşağıdaki "Aktivasyon" adımları. Çekirdek **stdlib-only**
> (harici bağımlılık YOK) → CI yalnızca `pytest` gerektirir.

## CI ne zorlar (gate'ler)
Workflow üç kapıyı sırayla koşar (hızlı geri-bildirim önce):
1. **Architecture fitness gate** — `tests/test_fitness_functions.py` (218 kontrol): mimari değişmezler
   (no-placeholder/bounded-context izolasyon/LLM-bağımsızlık/domain sözleşmesi/WAL+Lock/boot kompozisyonu).
2. **Operational readiness gate** — `tests/test_operational_readiness.py` (7 test): `readiness()` self-check +
   idempotent görünür-hatalı `close()`.
3. **Full test suite** — `pytest -q` (tüm domainler + fitness + readiness; şu an **768 test**).

Matris: Python **3.10 / 3.11 / 3.12** (`requires-python >= 3.10`). 3.13/3.14 bilerek dışarıda — yerel ortamda
3.14 kırık (bkz. proje notları).

## Lokal koşu reçetesi
Yerel sistem Python'u (3.14) kırık olduğundan **uv ile Python 3.12** kullanılır:

```bash
# Tam süit
uv run --python 3.12 --with pytest pytest -q

# Yalnız mimari fitness gate (hızlı)
uv run --python 3.12 --with pytest pytest tests/test_fitness_functions.py -q

# Yalnız operasyonel hazırlık
uv run --python 3.12 --with pytest pytest tests/test_operational_readiness.py -q

# Tek domain
uv run --python 3.12 --with pytest pytest tests/test_<domain>_domain.py -q
```

CI ortamında (temiz Python 3.10-3.12) reçete daha basittir — `uv` gerekmez:

```bash
python -m pip install --upgrade pip pytest
python -m pytest -q
```

## Aktivasyon (repo git değil)
Workflow'un GitHub Actions'ta çalışması için:

```bash
git init
git add -A
git commit -m "MIO Executive OS — 43 domain + Production Hardening (fitness + readiness + CI)"
git branch -M main
git remote add origin <GITHUB_REMOTE_URL>
git push -u origin main
```

> **Not:** `git init` ve ilk commit/push kullanıcı kararıdır (dış-yüze işlem). İstenirse yardımcı olunur; commit/push
> yalnız açık istekle yapılır.

## Kapsam & dürüstlük
CI **regresyon güvenlik ağı**dır: her değişiklikte mimari değişmezleri + tüm süiti doğrular. **Kanıtladığı:**
kod-seviyesi bütünlük, mimari tutarlılık, çok-Python-sürümü uyumu. **Kanıtlamadığı:** yük/performans (Load/Soak),
HA, gerçek dış connector'larla uçtan uca doğrulama, deploy güvenliği. Bunlar `PLATFORM_HARDENING.md`'de sıradaki
kalemlerdir. CI'nin yeşil olması **Production Ready** demek DEĞİL — "regresyon yok + mimari borç yok" demektir
([[feedback_maturity_label_honesty]]).
