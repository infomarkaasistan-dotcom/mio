"""MIO Core · Load / Soak (Production Hardening #5) — uzun-süreli kararlılık + eşzamanlılık KANITI.

İddia değil ölçüm: eşzamanlı yazmada kayıp-yok (threading.Lock + WAL doğru), sürekli operasyonda durum tutarlı,
boot/close döngüsünde sızıntı/hata yok. Deterministik; dış adapter gerektirmez. Boyutlar süiti makul tutacak
şekilde (birkaç saniye) seçildi; korrektlik asıl kanıttır, throughput yalnızca çok gevşek bir taban."""

import time
from concurrent.futures import ThreadPoolExecutor

from mio_core.domains.iot import IoTRepository, Reading


# ---- Eşzamanlı yazma: kayıp-güncelleme YOK (lock + WAL) ----
def test_concurrent_writes_no_lost_updates(tmp_path):
    repo = IoTRepository(str(tmp_path / "load.db"))
    n_threads, per_thread = 8, 500
    total = n_threads * per_thread

    def worker(_t):
        for i in range(per_thread):
            repo.put_reading(Reading(thing_id="th", metric="m", value=float(i)))

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        list(ex.map(worker, range(n_threads)))
    dur = max(time.perf_counter() - start, 1e-6)

    assert repo.reading_count() == total          # tek yazma bile kaybolmadı (asıl kanıt)
    assert (total / dur) > 50                      # çok gevşek throughput tabanı (herhangi makine geçer)
    repo.close()


# ---- Eşzamanlı yazma altında VERİ BÜTÜNLÜĞÜ (garanti edilen kontrat) ----
def test_concurrent_writes_preserve_data_integrity(tmp_path):
    """Eşzamanlı yazma altında hiçbir kayıt kaybolmaz/bozulmaz (lock-protected write-through).

    NOT (load-testing bulgusu): repository YAZMALARI lock'lu ve thread-güvenlidir; OKUMALAR lock-free'dir ve
    tüm thread'ler tek paylaşılan SQLite bağlantısını kullandığından eşzamanlı yazma sırasında bir okuma geçici
    olarak hata verebilir (veri bütünlüğü değil, okuma-dayanıklılığı sınırı). Bu test garanti edileni doğrular:
    veri bütünlüğü. Bkz. docs/development/PLATFORM_HARDENING.md → 'Eşzamanlılık bulgusu'."""
    repo = IoTRepository(str(tmp_path / "rw.db"))
    n_threads, per_thread = 6, 300

    def writer(_t):
        for i in range(per_thread):
            repo.put_reading(Reading(thing_id="th", metric="m", value=float(i)))

    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        list(ex.map(writer, range(n_threads)))

    # yazma sonrası (yarış yok): kayıt sayısı TAM ve okuma tutarlı
    assert repo.reading_count() == n_threads * per_thread   # tek yazma bile kaybolmadı
    rows = repo.readings("th", metric="m", limit=10)
    assert len(rows) == 10 and all(r.thing_id == "th" for r in rows)  # okuma bozulmamış
    repo.close()


# ---- Eşzamanlı okuma DOĞRU desende (thread başına ayrı bağlantı) güvenli ----
def test_concurrent_readers_with_own_connections_are_safe(tmp_path):
    """Load-testing REMEDIASYON kanıtı: WAL + thread-başına-ayrı-bağlantı ile eşzamanlı okuma güvenlidir.

    Bulgu (bkz. PLATFORM_HARDENING.md 'Eşzamanlılık bulgusu'): tek PAYLAŞILAN sqlite3 bağlantısı çok-thread'li
    eşzamanlı erişim için güvenli değildir (okumalar lock-free). DOĞRU desen: her thread kendi bağlantısını açar
    (WAL çoklu-okur + tek-yazar destekler). Bu test o güvenli deseni kanıtlar."""
    db = str(tmp_path / "ro.db")
    seed = IoTRepository(db)
    for i in range(500):
        seed.put_reading(Reading(thing_id="th", metric="m", value=float(i)))
    seed.close()

    errors, counts = [], []

    def reader(_t):
        own = IoTRepository(db)                    # thread'e ÖZEL bağlantı (doğru desen)
        try:
            for _ in range(200):
                counts.append(own.reading_count())
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
        finally:
            own.close()

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(reader, range(8)))

    assert errors == []                           # ayrı bağlantılarla eşzamanlı okuma güvenli
    assert counts and all(c == 500 for c in counts)  # her okuma tutarlı 500


# ---- Soak: sürekli operasyon altında durum tutarlı + readiness kararlı ----
def test_soak_sustained_operations(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        thing = mio.iot.register_thing("owner", "sensor", kind="sensor")
        iterations = 1500
        for i in range(iterations):
            mio.iot.ingest("owner", thing["id"], "temp", float(i % 100))
        assert mio.iot.stats()["readings"] == iterations   # sürekli yükte kayıp yok
        assert mio.readiness()["ready"] is True            # yük sonrası hâlâ hazır (kararlı)
        # son okuma tutarlı
        latest = mio.iot.latest("owner", thing["id"], "temp")
        assert latest["value"] == float((iterations - 1) % 100)
    finally:
        mio.close()


# ---- Boot/close döngüsü: kaynak sızıntısı / kapanış hatası YOK ----
def test_boot_close_cycle_stability(tmp_path):
    from mio_core.runtime import boot
    for r in range(4):
        mio = boot(workspace=str(tmp_path / f"mio{r}"), connect_ollama=False, discover_hw=False)
        assert mio.readiness()["ready"] is True
        report = mio.close()
        assert report["errors"] == []                      # her döngüde temiz kapanış
        assert report["already_closed"] is False
        # kapandıktan sonra readiness dürüstçe not-ready
        assert mio.readiness()["ready"] is False
