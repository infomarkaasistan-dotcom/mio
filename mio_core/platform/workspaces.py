"""MIO Core · Platform · Business Workspace Manager — çoklu İZOLE işletme çalışma alanı (tek sahip), stdlib-only.

**Bu çoklu-kullanıcı/SaaS DEĞİL.** MIO'nun tek sahibi vardır; sahip birden çok İŞLETME işletebilir. Her Business
Workspace **tam izoledir** (agents/tasks/goals/memory/dashboards/metrics) çünkü kendi **ayrı dizininde** (kendi
SQLite state'i) yaşar. Platform servisleri (Executive/Brains/Registries/Engines = KOD) paylaşılır — çünkü bir
işletme `boot(workspace=<business_path>)` ile ayağa kalkar; kod aynı, state ayrık. **Yeni registry/workflow/memory
OLUŞTURMAZ** — mevcut `boot()` izolasyonunu kullanır (ürün bütünlüğü). Operasyonel state işletmeler arası SIZMAZ."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# İş tipi şablonları — önerilen departman/rol tohumu (deterministik; onboarding + CEO için ipucu, zorunlu değil).
BUSINESS_TEMPLATES = {
    "personal": {"label": "Kişisel Şirket", "departments": ["Operations", "Finance"]},
    "marketing_agency": {"label": "Pazarlama Ajansı",
                         "departments": ["Marketing", "Sales", "Content", "Analytics"]},
    "ecommerce": {"label": "E-Ticaret", "departments": ["Sales", "Marketing", "Operations", "Support"]},
    "factory": {"label": "Fabrika", "departments": ["Operations", "Supply", "Quality", "Finance"]},
    "restaurant": {"label": "Restoran", "departments": ["Operations", "Marketing", "Finance"]},
    "saas": {"label": "SaaS Girişimi", "departments": ["Engineering", "Product", "Sales", "Marketing"]},
}


class BusinessWorkspaceError(Exception):
    pass


class BusinessWorkspaceManager:
    """İşletme çalışma alanı kaydını (registry) ve izole dizinlerini yönetir. Bir platform servisidir (paylaşılır).

    Kayıt `<home>/businesses.json`; her işletme state'i `<home>/businesses/<id>/` altında (izole). Aktivasyon
    (bir işletmeye geçiş) `boot(workspace=path_for(id))` ile yapılır — yani gerçek izolasyon mevcut boot()'tur."""

    def __init__(self, home: str) -> None:
        self._home = home
        self._dir = os.path.join(home, "businesses")
        self._registry = os.path.join(home, "businesses.json")
        os.makedirs(self._dir, exist_ok=True)

    # -- registry I/O (write-through JSON) ------------------------------ #
    def _load(self) -> list:
        if not os.path.exists(self._registry):
            return []
        try:
            with open(self._registry, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:  # noqa: BLE001 — bozuk registry → boş (dürüst), çökmez
            return []

    def _save(self, items: list) -> None:
        tmp = self._registry + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self._registry)

    # -- işlemler -------------------------------------------------------- #
    def create(self, name: str, *, business_type: str = "personal", objectives: Optional[list] = None
               ) -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise BusinessWorkspaceError("işletme adı boş olamaz")
        if business_type not in BUSINESS_TEMPLATES:
            raise BusinessWorkspaceError(f"geçersiz iş tipi: {business_type} "
                                         f"(izinli: {sorted(BUSINESS_TEMPLATES)})")
        items = self._load()
        if any(b["name"].lower() == name.lower() for b in items):
            raise BusinessWorkspaceError(f"'{name}' zaten var")
        bid = uuid4().hex[:12]
        tpl = BUSINESS_TEMPLATES[business_type]
        path = os.path.join(self._dir, bid)
        os.makedirs(path, exist_ok=True)              # izole state dizini (kendi .db'leri burada)
        rec = {"id": bid, "name": name, "business_type": business_type,
               "label": tpl["label"], "departments": list(tpl["departments"]),
               "objectives": list(objectives or []), "path": path, "created_at": _now()}
        items.append(rec)
        self._save(items)
        return rec

    def list(self) -> list[dict[str, Any]]:
        return self._load()

    def get(self, business_id: str) -> Optional[dict[str, Any]]:
        return next((b for b in self._load() if b["id"] == business_id or b["name"] == business_id), None)

    def path_for(self, business_id: str) -> str:
        b = self.get(business_id)
        if b is None:
            raise BusinessWorkspaceError(f"işletme bulunamadı: {business_id}")
        return b["path"]

    def delete(self, business_id: str, *, purge: bool = False) -> dict[str, Any]:
        items = self._load()
        b = next((x for x in items if x["id"] == business_id or x["name"] == business_id), None)
        if b is None:
            raise BusinessWorkspaceError(f"işletme bulunamadı: {business_id}")
        items = [x for x in items if x["id"] != b["id"]]
        self._save(items)
        if purge and os.path.isdir(b["path"]):        # state'i de sil (geri-alınamaz)
            shutil.rmtree(b["path"], ignore_errors=True)
        return {"deleted": b["id"], "purged": purge}

    def set_objectives(self, business_id: str, objectives: list) -> dict[str, Any]:
        items = self._load()
        b = next((x for x in items if x["id"] == business_id or x["name"] == business_id), None)
        if b is None:
            raise BusinessWorkspaceError(f"işletme bulunamadı: {business_id}")
        b["objectives"] = list(objectives)
        self._save(items)
        return b

    def stats(self) -> dict[str, Any]:
        items = self._load()
        by_type: dict[str, int] = {}
        for b in items:
            by_type[b["business_type"]] = by_type.get(b["business_type"], 0) + 1
        return {"businesses": len(items), "by_type": by_type, "home": self._home,
                "templates": sorted(BUSINESS_TEMPLATES)}


__all__ = ["BusinessWorkspaceManager", "BusinessWorkspaceError", "BUSINESS_TEMPLATES"]
