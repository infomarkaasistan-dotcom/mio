"""MIO Core · Device & Native Integration Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class DeviceEvents:
    DEVICE_REGISTERED = "device.registered"
    COMMAND_CREATED = "device.command_created"
    COMMAND_COMPLETED = "device.command_completed"
    COMMAND_FAILED = "device.command_failed"
    NO_CONNECTOR = "device.no_connector"
    APPROVAL_REQUIRED = "device.approval_required"
    APPROVED = "device.approved"


OPERATIONS = ("register_device", "execute", "approve_command", "get_job", "list_jobs", "list_devices",
              "connectors", "stats")


def device_contract() -> dict[str, Any]:
    return {
        "domain": "device_native",
        "version": CONTRACT_VERSION,
        "description": "Deterministik native ORKESTRASYON: device registry + komut durum makinesi + connector "
                       "routing + risk sınıflandırma (yüksek-risk onay ister, Madde 24). Gerçek OS/donanım "
                       "adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [DeviceEvents.DEVICE_REGISTERED, DeviceEvents.COMMAND_CREATED,
                   DeviceEvents.COMMAND_COMPLETED, DeviceEvents.COMMAND_FAILED, DeviceEvents.NO_CONNECTOR,
                   DeviceEvents.APPROVAL_REQUIRED, DeviceEvents.APPROVED],
        "device_kinds": ["os", "filesystem", "peripheral"],
        "op_statuses": ["pending", "running", "completed", "failed", "no_connector", "requires_approval"],
        "invariants": ["gerçek OS/donanım adapter'a delege edilir (çekirdek erişim yapmaz)",
                       "yüksek-risk/geri-alınamaz komut onay ister (Madde 24); onaysız çalışmaz",
                       "handler yoksa no_connector (uydurma sonuç YOK — Madde 8)"],
    }
