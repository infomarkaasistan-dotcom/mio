"""MIO Core · System Connector · Filesystem — GERÇEK dosya sistemi erişimi (stdlib), SANDBOX'lı.

capability: files.read/files.write/files.list/fs.read/fs.write. Tüm yollar `root` altına kısıtlanır (path
traversal reddedilir — güvenlik). Yerel + gerçek → canlı test edilebilir. fs.write/files.write yüksek-risk
(Connector Manager Madde 24 kapısı)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


def _resolve(root: Path, rel: str) -> Path:
    """rel yolunu root altında güvenle çözer (traversal reddedilir)."""
    if not rel or not str(rel).strip():
        raise ValidationError("path boş olamaz")
    target = (root / str(rel).lstrip("/\\")).resolve()
    root_res = root.resolve()
    if root_res != target and root_res not in target.parents:
        raise ValidationError(f"sandbox dışı yol reddedildi: {rel}")
    return target


def filesystem_connector(*, root: str, name: str = "filesystem", priority: int = 100) -> CallableConnector:
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)

    def _read(req: dict) -> dict[str, Any]:
        p = _resolve(base, req.get("path", ""))
        return {"path": str(p), "content": p.read_text(encoding="utf-8")}

    def _write(req: dict) -> dict[str, Any]:
        p = _resolve(base, req.get("path", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        content = req.get("content", "")
        p.write_text(content if isinstance(content, str) else str(content), encoding="utf-8")
        return {"path": str(p), "bytes": len(content)}

    def _list(req: dict) -> dict[str, Any]:
        p = _resolve(base, req.get("path", "."))
        if not p.exists():
            return {"path": str(p), "entries": []}
        entries = [{"name": c.name, "dir": c.is_dir(), "size": c.stat().st_size if c.is_file() else 0}
                   for c in sorted(p.iterdir())]
        return {"path": str(p), "entries": entries}

    return CallableConnector(
        name=name, category=ConnectorCategory.SYSTEM,
        handlers={Cap.FS_READ: _read, Cap.FILES_READ: _read,
                  Cap.FS_WRITE: _write, Cap.FILES_WRITE: _write,
                  Cap.FILES_LIST: _list},
        priority=priority, health_fn=lambda: base.exists())


__all__ = ["filesystem_connector"]
