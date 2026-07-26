# CLI — Terminal Arayüzü (Interface Katmanı #1)

> Sistemi terminalden **etkileşimli** ya da **tek-atış** kullanmayı sağlar (geliştirme + hata-ayıklama).
> **DETERMİNİSTİK ve LLM-BAĞIMSIZ** (Anayasa: LLM danışman, karar verici değil) — komut arayüzü her zaman çalışır.
> Doğal dil, ancak bir LLM danışman (connector) bağlıysa anlamlıdır; birincil arayüz **komutlar**dır.

## Çalıştırma
```bash
# Etkileşimli kabuk (gerçek terminal)
python -m mio_core                    # veya: python -m mio_core shell
mio> domains
mio> call iot register_thing {"actor":"owner","name":"Kazan","kind":"sensor"}
mio> quit

# Tek-atış (script/otomasyon)
python -m mio_core domains --workspace /data/mio
python -m mio_core call iot ingest '{"actor":"owner","thing_id":"<id>","metric":"temp","value":42}'
```
Yerel geliştirmede (sistem py3.14 kırık): `uv run --python 3.12 python -m mio_core <cmd>`.

## Komutlar
| Komut | Açıklama |
|---|---|
| `domains` | Tüm domainleri + sözleşme versiyonu + operasyon sayısı + kısa açıklama |
| `contract <domain>` | Domainin public sözleşmesi (operasyonlar/events/invariantlar) |
| `stats <domain>` | Domainin metrikleri (`stats()`) |
| `metrics` | Tüm domainlerin birleşik metrik snapshot'ı |
| `readiness` / `health` | Operasyonel hazırlık / sağlık (readiness ready değilse **çıkış kodu 1**) |
| `events [N]` | Son N event bus olayı (varsayılan 20) |
| `call <domain> <op> [json]` | **Reflektif çağrı** — herhangi bir domain operasyonu (`json = {"actor":"owner",...}`) |
| `help` · `quit`/`exit` | Yardım · çıkış |

## Reflektif `call` (hata-ayıklamanın kalbi)
Herhangi bir domain operasyonunu terminalden çağırır; JSON nesnesi **kwargs** olarak geçer (domain API'leri
positional-or-keyword olduğundan `{"actor":"owner","name":"S"}` doğrudan çalışır):
```bash
call model_management register_model {"actor":"owner","name":"llama","kind":"llm","provider":"ollama"}
call multi_agent register_agent {"actor":"owner","name":"Ajan","capabilities":["research"]}
call federation register_peer {"actor":"owner","name":"Peer","endpoint":"https://peer.mio.net/api"}
```
**Güvenlik:** özel (underscore) metodlar çağrılamaz; domain'in kendi authz'i (Madde 24 vb.) yürürlükte kalır —
yetki hatası CLI'yı çökertmez, `HATA: ...` olarak döner (çıkış kodu 1).

## Yönlendirme (`__main__`)
- `readiness | health | metrics` → **ops probe** (exit-kodlu; Docker HEALTHCHECK / monitoring — bkz. DEPLOYMENT.md).
- diğer her şey (argsız dahil) → **CLI** (etkileşimli veya tek-atış).

## Kapsam / dürüstlük
CLI **deterministik komut** arayüzüdür (LLM'siz, her zaman çalışır). **Doğal dil** ve dışa açık **HTTP/API** ayrı,
sıradaki Interface katmanı çıktılarıdır. Test kanıtı: `tests/test_cli.py` (10 yeşil).
