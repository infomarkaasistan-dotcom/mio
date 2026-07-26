"""MIO Core · Config — TEK yapılandırma kaynağı (.env + os.environ). REGRESYON KORUMASI.

Kök neden: `.env` hiç yüklenmiyordu → `LLM_ENABLED=true` runtime'a ulaşmıyordu. Bu testler onun bir daha
olmamasını garanti eder: .env parse, öncelik (env > .env), bool parse (case-insensitive), tek-kaynak paylaşımı
(runtime + connect + local_inference AYNI config), sır maskeleme."""

import pytest

from mio_core.platform.config import Config, load_env_file


def _write_env(tmp_path, content: str) -> str:
    p = tmp_path / ".env"
    p.write_text(content, encoding="utf-8")
    return str(p)


# ---- .env parse ----
def test_load_env_file_basic(tmp_path):
    path = _write_env(tmp_path, "# comment\nLLM_ENABLED=true\nSMTP_PORT=587\n\nexport OLLAMA_HOST=http://x:1\n"
                                'QUOTED="a b"\nNOEQ\n')
    d = load_env_file(path)
    assert d["LLM_ENABLED"] == "true" and d["SMTP_PORT"] == "587"
    assert d["OLLAMA_HOST"] == "http://x:1"        # export öneki soyuldu
    assert d["QUOTED"] == "a b"                    # tırnak soyuldu
    assert "NOEQ" not in d and "#" not in d        # geçersiz/yorum atlandı


def test_load_env_file_missing_returns_empty():
    assert load_env_file("/yok/olan/.env") == {}   # dosya yok → boş (çökme yok)


# ---- KÖK NEDEN: .env değeri env'de yoksa ETKİLİ olur ----
def test_env_file_value_used_when_absent_in_environ(tmp_path):
    path = _write_env(tmp_path, "LLM_ENABLED=true\n")
    cfg = Config(env_file=path, environ={})        # os.environ'da YOK
    assert cfg.get("LLM_ENABLED") == "true"        # .env'den okundu (eskiden None dönüyordu — BUG)
    assert cfg.get_bool("LLM_ENABLED") is True
    assert cfg.source_of("LLM_ENABLED") == "env_file"


# ---- öncelik: gerçek env, .env'i override eder ----
def test_environ_overrides_env_file(tmp_path):
    path = _write_env(tmp_path, "LLM_ENABLED=false\n")
    cfg = Config(env_file=path, environ={"LLM_ENABLED": "true"})
    assert cfg.get("LLM_ENABLED") == "true" and cfg.source_of("LLM_ENABLED") == "environ"


def test_overrides_win(tmp_path):
    path = _write_env(tmp_path, "X=a\n")
    cfg = Config(env_file=path, environ={"X": "b"}, overrides={"X": "c"})
    assert cfg.get("X") == "c" and cfg.source_of("X") == "overrides"


# ---- bool parse case-insensitive ----
@pytest.mark.parametrize("val,expect", [("true", True), ("TRUE", True), ("True", True), ("1", True),
                                        ("yes", True), ("on", True), ("false", False), ("0", False),
                                        ("no", False), ("off", False), ("", False)])
def test_get_bool_case_insensitive(val, expect):
    assert Config(env_file=None, environ={"K": val}).get_bool("K") is expect


def test_get_bool_default_when_absent():
    assert Config(env_file=None, environ={}).get_bool("MISSING", default=True) is True


# ---- sır maskeleme (diagnostics) ----
def test_diagnostics_redacts_secrets(tmp_path):
    path = _write_env(tmp_path, "OPENAI_API_KEY=sk-REAL\nLLM_ENABLED=true\n")
    diag = Config(env_file=path, environ={}).diagnostics()
    assert diag["env_file_loaded"] is True
    assert diag["keys"]["OPENAI_API_KEY"]["value"] == "***redacted***"   # sır asla görünmez
    assert diag["keys"]["LLM_ENABLED"]["value"] == "true"


# ---- as_dict birleşik görünüm ----
def test_as_dict_merged_priority(tmp_path):
    path = _write_env(tmp_path, "A=1\nB=2\n")
    cfg = Config(env_file=path, environ={"B": "9", "C": "3"})
    d = cfg.as_dict()
    assert d["A"] == "1" and d["B"] == "9" and d["C"] == "3"


# ---- TEK KAYNAK: runtime + connect + local_inference AYNI config (Interface Architecture) ----
def test_runtime_shares_single_config(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    path = _write_env(tmp_path, "LLM_ENABLED=true\n")
    cfg = Config(env_file=path, environ={})
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False, config=cfg)
    try:
        # runtime aynı config instance'ını tutar
        assert mio.config is cfg
        assert mio.config.get_bool("LLM_ENABLED") is True
        # config_diagnostics DTO'su llm_enabled'ı yansıtır
        assert appservice.config_diagnostics(mio)["llm_enabled"] is True
    finally:
        mio.close()


def test_boot_loads_env_file_and_connect_reads_it(tmp_path, monkeypatch):
    """Uçtan uca kök-neden regresyonu: .env'de LLM_ENABLED=true → connect ollama'yı bağlamayı DENER (config'ten)."""
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.connectors.adapters import register_from_env
    # register_from_env'i mock'la: hangi env geldiğini yakala (gerçek ağ yok)
    seen = {}

    def fake_register(manager, *, env=None, workspace=".mio"):
        seen["env"] = env
        return {"registered": (["ollama"] if str(env.get("LLM_ENABLED", "")).lower() == "true" else []),
                "skipped": [], "fs_root": workspace}

    monkeypatch.setattr("mio_core.connectors.adapters.register_from_env", fake_register)
    path = _write_env(tmp_path, "LLM_ENABLED=true\n")
    cfg = Config(env_file=path, environ={})
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False, config=cfg)
    try:
        summary = appservice.connect_env(mio)
        assert seen["env"]["LLM_ENABLED"] == "true"          # connect config'i okudu (.env'den)
        assert "ollama" in summary["registered"]             # LLM_ENABLED etkili
    finally:
        mio.close()
