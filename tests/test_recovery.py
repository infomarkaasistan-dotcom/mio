"""MIO Core · Recovery (Production Hardening #6) — dayanıklılık + yedekten-dönüş KANITI.

İddia değil senaryo: (1) temiz kapanış olmadan (crash) commit'li veri WAL sayesinde hayatta kalır; (2) SQLite
online hot-backup API ile canlı yedek alınır ve felaket sonrası geri yüklenir; (3) yedek nokta-anı (point-in-time)
snapshot'tır. Deterministik; dış adapter gerektirmez."""

import os
import shutil
import sqlite3

from mio_core.domains.iot import IoTRepository, Reading


def _seed(repo, n, thing="t", metric="m"):
    for i in range(n):
        repo.put_reading(Reading(thing_id=thing, metric=metric, value=float(i)))


def _wipe_db_files(db):
    for suffix in ("", "-wal", "-shm"):
        p = db + suffix
        if os.path.exists(p):
            os.remove(p)


def _hot_backup(db, backup):
    """SQLite online backup API — kaynak/hedef bağlantıları AÇIKÇA kapatılır (Windows kilit güvenliği).

    NOT: `with sqlite3.connect(...) as c` bağlantıyı KAPATMAZ (yalnız transaction yönetir) — açık close şart."""
    src = sqlite3.connect(db)
    dst = sqlite3.connect(backup)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        src.close()
        dst.close()


# ---- (1) Crash recovery: temiz kapanış olmadan commit'li veri hayatta kalır (WAL dayanıklılık) ----
def test_committed_data_survives_unclean_shutdown(tmp_path):
    db = str(tmp_path / "crash.db")
    repo = IoTRepository(db)
    _seed(repo, 200)
    # 'CRASH': repo.close() ÇAĞRILMADAN yeni bir bağlantı açılır (süreç çökmesi gibi)
    survivor = IoTRepository(db)
    assert survivor.reading_count() == 200        # commit'li veri yeni bağlantıda görünür
    # içerik de tutarlı
    rows = survivor.readings("t", metric="m", limit=5)
    assert len(rows) == 5 and all(r.thing_id == "t" for r in rows)
    survivor.close()
    repo.close()


# ---- (2) Hot backup + restore: canlı yedek → felaket → yedekten tam dönüş ----
def test_hot_backup_and_restore(tmp_path):
    db = str(tmp_path / "live.db")
    backup = str(tmp_path / "backup.db")
    repo = IoTRepository(db)
    _seed(repo, 150)

    # CANLI hot-backup (SQLite online backup API — WAL dahil tutarlı snapshot), repo hâlâ açıkken
    _hot_backup(db, backup)
    repo.close()

    # 'FELAKET': canlı db + yan dosyaları kaybı
    _wipe_db_files(db)
    assert not os.path.exists(db)

    # RESTORE: yedeği yerine koy → yeniden aç → veri tam
    shutil.copy(backup, db)
    restored = IoTRepository(db)
    assert restored.reading_count() == 150        # yedekten tam geri dönüş
    assert restored.readings("t", metric="m", limit=1)[0].thing_id == "t"
    restored.close()


# ---- (3) Yedek nokta-anı snapshot'tır (sonradan yazılan yedeğe girmez) ----
def test_backup_is_point_in_time_snapshot(tmp_path):
    db = str(tmp_path / "pit.db")
    backup = str(tmp_path / "pit_backup.db")
    repo = IoTRepository(db)
    _seed(repo, 100)                              # yedek-anı: 100 kayıt

    _hot_backup(db, backup)

    _seed(repo, 50, metric="m2")                  # yedekten SONRA 50 kayıt daha
    assert repo.reading_count() == 150            # canlı: 150
    repo.close()

    # yedekten geri yükle → yalnız 100 (nokta-anı korunmuş)
    _wipe_db_files(db)
    shutil.copy(backup, db)
    restored = IoTRepository(db)
    assert restored.reading_count() == 100        # yedek: 100 (sonraki 50 yok)
    restored.close()


# ---- (4) WAL checkpoint sonrası soğuk-kopya yedeği de eksiksiz ----
def test_cold_copy_after_checkpoint(tmp_path):
    db = str(tmp_path / "cold.db")
    backup = str(tmp_path / "cold_backup.db")
    repo = IoTRepository(db)
    _seed(repo, 120)
    # WAL'ı ana dosyaya katla (TRUNCATE) → tek dosya soğuk-kopya tam olur
    cx = sqlite3.connect(db)
    try:
        cx.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cx.commit()
    finally:
        cx.close()
    repo.close()

    shutil.copy(db, backup)                       # soğuk kopya (tek dosya yeterli)
    _wipe_db_files(db)
    shutil.copy(backup, db)
    restored = IoTRepository(db)
    assert restored.reading_count() == 120        # soğuk kopyadan tam dönüş
    restored.close()
