# MIO — BLOCKERS

> Aktif engeller ve bilinen kısıtlar. Boşsa: engel yok.

## Aktif engel
- **Yok.** 15 domain FROZEN, tam süit yeşil, boot temiz.

## Bilinen ortam kısıtları (engel değil, dikkat)
- **Python:** sistem py3.14 kırık → testler **py3.12 venv** ile: `uv run --python 3.12 --with pytest pytest -q`.
- **Ollama:** çoklu model yükleme donmaya yol açtı (ilk oturum). Kalıcı çözüm: `OLLAMA_MAX_LOADED_MODELS=1`
  (User env). Ayrıca Scheduler Domain'de duvar-saati thread YOK → kontrolsüz süreç riski kök çözüldü.
- **PowerShell:** Türkçe karakter/çift tırnak `python -c` içinde bozulur → geçici script dosyası kullan.
  `.lower()` Türkçe tuzağı ("BAĞLI".lower() → "bağli"): kod içi karşılaştırmalarda dikkat.
- **Secret güvenliği (Anayasa):** `.env` içeriği (gerçek OpenAI/DeepSeek/Qwen anahtarları) hiçbir komutta
  yazdırılmaz/loglanmaz. Security Domain `redact()` bunu operasyonel güvence yapar.

## Mimari borç (planlı, engel değil)
- Capability/MCP/Audit/Resource henüz tam bounded-context Domain değil (çekirdek servisi) → NEXT_STEPS #1.
- Multi-Org, Digital Twin, Simulation, Self Development → roadmap ileri fazlar.
