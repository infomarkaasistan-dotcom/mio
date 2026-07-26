# Local Inference Management — MIO çalışacağı ORTAMI yönetir

> MIO sistemi tanır ve yerel çıkarım ortamını (Ollama + modeller) **kendisi hazırlar**: analiz → uygun modeli SEÇ
> → fazla/CPU'da yüklü modelleri DURDUR → eksikse İNDİR → sağlık+HIZ testi → başarılıysa **"Ollama bağlı"** bildirir.
> `mio_core/platform/local_inference.py`. `runner`/`urlopen` enjekte edilebilir → deterministik test.

## Anayasa sınırları (önemli)
- **Executive tek karar verici; seçim DETERMİNİSTİK** (VRAM'e göre, LLM'siz — Madde 1).
- **Geri-alınamaz işler ONAY ister (Madde 24):** model **SİLME** ve Ollama **KURULUMU**. MIO bunları **sessizce
  YAPMAZ** — önerir (`pending_approval`), yalnız açık onayla yürütür.
- **Güvenli/geri-alınabilir işler otomatik:** analiz, model **durdurma** (VRAM'den düşür, geri-alınabilir), eksik
  model **indirme** (additive), **test**.
- **Donma önleme:** ağır sağlık/hız testi **yalnız model GPU'ya sığıyorsa** çalışır; sığmazsa/GPU yoksa atlanır +
  uyarı (kullanıcının yaşadığı 4-dakika-donma senaryosu bir daha olmaz).

## Komutlar
```bash
python -m mio_core inference analyze          # salt-okunur: donanım + Ollama + kurulu/yüklü modeller + yerleşim
python -m mio_core inference ensure-ready     # ortamı hazırla (güvenli işler otomatik; silme/kurulum onay bekler)
python -m mio_core inference ensure-ready install_ollama delete_unfit   # onay vererek
```
HTTP: `GET /inference/analyze` · `POST /inference/ensure-ready` (body: `{approve:[...], auto_pull, run_test}`).

## ensure_ready akışı (adım adım)
1. **Ollama var mı?** Yoksa: kurulu değilse → `install_ollama` **onay** ister (platforma göre komut önerir);
   kuruluysa ama kapalıysa → "ollama serve başlatın" uyarısı.
2. **Uygun modeli seç** — `recommend_model` VRAM'e sığan **en yetenekli** modeli seçer (yoksa en küçük + uyarı).
3. **Eksikse indir** — seçili model kurulu değilse `ollama pull` (additive, güvenli).
4. **Fazlalığı durdur** — seçili olmayan yüklü modelleri `keep_alive=0` ile VRAM'den düşür (güvenli).
5. **Sağlık+hız testi** — küçük prompt (num_predict=8); GPU'da + `≤{FAST}ms` ise **TEST BAŞARILI · Ollama bağlı**.
   (GPU'ya sığmıyorsa test **atlanır** — donma önleme.)
6. **Silme önerisi** — VRAM'e sığmayan kurulu modeller `pending_approval`'a düşer (Madde 24; MIO **silmez**, önerir).

## Çıktı
`{ready, selected_model, actions_executed[], pending_approval[], test, warnings[], message}`. `ready=True` yalnız
model GPU'da + hızlı test geçince. `message` başarılıysa: `TEST BAŞARILI · Ollama bağlı · model=... · <ms> · GPU`.

## Bu makinede (canlı analiz — salt-okunur)
RTX 3050 8GB VRAM (~6.9GB boş) + CUDA 13.1 → **önerilen: mistral:7b** (sığar). `qwen3.5:9b` sığmaz → silme adayı
(ama onaysız silinmez). Donma çözümü: `OLLAMA_MAX_LOADED_MODELS=1` (ensure-ready fazlalığı zaten durdurur).

## Test / dürüstlük
`tests/test_local_inference.py` (8) — gerçek indirme/çıkarım/silme YOK; ollama CLI + HTTP enjekte edilerek tüm
akış deterministik doğrulanır. Otomatik Ollama kurulumu winget/brew ile denenir; Linux'ta elle komut önerilir
(sudo gerektirir — dürüst sınır).
