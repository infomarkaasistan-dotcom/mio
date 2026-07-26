"""MIO Core · GERÇEK connector adapters — 4 kategori. System=canlı; network=gerçek kod + enjekte transport.

Placeholder YOK. Filesystem/Shell/Git yerel gerçek; SMTP/Webhook/Ollama/OpenAI/CalDAV gerçek kod, transport
enjekte edilerek doğrulanır (canlı serviste config ile çalışır). bootstrap env'e göre bağlar."""

import shutil
import sys

import pytest

from mio_core.connectors import Cap, ConnectorManager, ConnectorRegistry, Outcome
from mio_core.connectors.adapters import (
    caldav_connector,
    filesystem_connector,
    git_connector,
    ollama_connector,
    openai_connector,
    register_from_env,
    shell_connector,
    smtp_connector,
    webhook_connector,
)


# ---- System · Filesystem (CANLI, gerçek fs, sandbox) ----
def test_filesystem_real_read_write_list_sandbox(tmp_path):
    c = filesystem_connector(root=str(tmp_path / "fsroot"))
    assert c.provides(Cap.FILES_WRITE) and c.health().ok
    c.execute(Cap.FILES_WRITE, {"path": "a/b.txt", "content": "merhaba"})
    assert c.execute(Cap.FS_READ, {"path": "a/b.txt"})["content"] == "merhaba"
    entries = c.execute(Cap.FILES_LIST, {"path": "a"})["entries"]
    assert any(e["name"] == "b.txt" for e in entries)
    # sandbox: traversal reddedilir
    from mio_core.connectors.models import ValidationError
    with pytest.raises(ValidationError):
        c.execute(Cap.FS_READ, {"path": "../../etc/passwd"})


# ---- System · Shell (CANLI, gerçek subprocess) ----
def test_shell_real_exec():
    c = shell_connector()
    out = c.execute(Cap.SHELL_EXEC, {"cmd": [sys.executable, "-c", "print('hi')"]})
    assert out["returncode"] == 0 and "hi" in out["stdout"]


# ---- System · Git (CANLI eğer git varsa, aksi skip) ----
@pytest.mark.skipif(shutil.which("git") is None, reason="git yok")
def test_git_real_status(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    c = git_connector()
    assert c.health().ok
    res = c.execute("git.status", {"cwd": str(tmp_path)})
    assert res["returncode"] == 0


def test_git_health_false_without_git(monkeypatch):
    monkeypatch.setattr("mio_core.connectors.adapters.git.shutil.which", lambda _n: None)
    assert git_connector().health().ok is False


# ---- Communication · SMTP (gerçek kod + enjekte SMTP) ----
def test_smtp_send_email_injected():
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30): captured["host"] = host; captured["port"] = port
        def starttls(self): captured["tls"] = True
        def login(self, u, p): captured["login"] = u
        def send_message(self, msg): captured["to"] = msg["To"]; captured["subj"] = msg["Subject"]
        def quit(self): captured["quit"] = True

    c = smtp_connector(host="smtp.example.com", user="me@x.com", password="pw", smtp_factory=FakeSMTP)
    r = c.execute(Cap.SEND_EMAIL, {"to": "a@b.com", "subject": "S", "body": "gövde"})
    assert r["sent"] and captured["to"] == "a@b.com" and captured["tls"] and captured["quit"]


# ---- Communication · Webhook (gerçek kod + enjekte urlopen; Slack/Discord/Telegram) ----
def test_webhook_send_message_injected():
    seen = {}

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok":true}'

    def fake_urlopen(req, timeout=30):
        seen["url"] = req.full_url; seen["body"] = req.data.decode(); return Resp()

    c = webhook_connector(url="https://hooks.slack.com/x", payload_style="slack", urlopen=fake_urlopen)
    r = c.execute(Cap.SEND_MESSAGE, {"text": "selam"})
    assert r["sent"] and '"text": "selam"' in seen["body"]


# ---- AI · Ollama (gerçek kod + enjekte urlopen) — DANIŞMAN ----
def test_ollama_advise_injected():
    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"response":"tavsiye: X yap","model":"llama3"}'

    c = ollama_connector(urlopen=lambda req, timeout=30: Resp())
    out = c.execute(Cap.AI_ADVISE, {"prompt": "ne yapmalı?"})
    assert out["advice"] == "tavsiye: X yap"                # danışman TAVSİYE döner (karar değil)


# ---- AI · OpenAI-uyumlu (gerçek kod + enjekte; anahtarsız health False) ----
def test_openai_advise_injected_and_health():
    assert openai_connector(api_key="").health().ok is False   # anahtar yok → sağlıksız

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return '{"choices":[{"message":{"content":"öneri"}}],"model":"gpt-4o-mini"}'.encode("utf-8")

    seen = {}
    def fake(req, timeout=30):
        seen["auth"] = req.headers.get("Authorization"); return Resp()

    c = openai_connector(api_key="sk-test", urlopen=fake)
    out = c.execute(Cap.AI_ADVISE, {"prompt": "x"})
    assert out["advice"] == "öneri" and seen["auth"] == "Bearer sk-test"   # anahtar header'da (loglanmaz)


# ---- Productivity · CalDAV (gerçek kod + enjekte) ----
def test_caldav_create_event_injected():
    seen = {}

    class Resp:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b""

    def fake(req, timeout=30):
        seen["method"] = req.get_method(); seen["ct"] = req.headers.get("Content-type"); return Resp()

    c = caldav_connector(url="https://dav.example.com/cal", user="u", password="p", urlopen=fake)
    r = c.execute(Cap.CALENDAR_CREATE, {"summary": "Toplantı", "start": "20260101T090000Z",
                                        "end": "20260101T100000Z"})
    assert r["created"] and seen["method"] == "PUT" and "calendar" in seen["ct"]


# ---- bootstrap: env'e göre bağlama ----
def test_register_from_env_selective():
    mgr = ConnectorManager(ConnectorRegistry())
    summary = register_from_env(mgr, env={"SMTP_HOST": "smtp.x.com", "OPENAI_API_KEY": "k"},
                                workspace="/tmp/ws")
    reg = set(summary["registered"])
    assert {"filesystem", "git", "smtp", "openai"} <= reg     # yapılandırılmışlar bağlandı
    assert "shell" not in reg                                 # MIO_SHELL_ENABLED kapalı → atlandı
    assert any("caldav" in s for s in summary["skipped"])     # config yok → atlandı


# ---- entegrasyon: manager üzerinden gerçek filesystem (Madde 24: fs.write high-risk) ----
def test_manager_dispatch_to_real_filesystem(tmp_path):
    mgr = ConnectorManager(ConnectorRegistry())
    register_from_env(mgr, env={}, workspace=str(tmp_path / "ws"))
    # fs.write YÜKSEK-RİSK → onaysız requires_approval (Madde 24)
    assert mgr.execute("fs.write", {"path": "x.txt", "content": "hi"})["status"] == Outcome.REQUIRES_APPROVAL
    # onaylı → gerçek dosya yazılır, sonra fs.read (düşük-risk) okur
    w = mgr.execute("fs.write", {"path": "x.txt", "content": "hi"}, user_approved=True)
    assert w["ok"] and w["status"] == Outcome.EXECUTED
    assert mgr.execute("fs.read", {"path": "x.txt"})["result"]["content"] == "hi"
