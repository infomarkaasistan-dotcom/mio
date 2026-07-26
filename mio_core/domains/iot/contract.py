"""MIO Core · IoT Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class IoTEvents:
    THING_REGISTERED = "iot.thing_registered"
    TELEMETRY_INGESTED = "iot.telemetry_ingested"
    ALERT_RULE_ADDED = "iot.alert_rule_added"
    ALERT_TRIGGERED = "iot.alert_triggered"
    COMMAND_CREATED = "iot.command_created"
    COMMAND_COMPLETED = "iot.command_completed"
    COMMAND_FAILED = "iot.command_failed"
    NO_CONNECTOR = "iot.no_connector"
    APPROVAL_REQUIRED = "iot.approval_required"
    APPROVED = "iot.approved"


OPERATIONS = ("register_thing", "ingest", "add_alert_rule", "send_command", "approve_command",
              "readings", "latest", "alerts", "get_command", "list_commands", "list_things",
              "connectors", "stats")


def iot_contract() -> dict[str, Any]:
    return {
        "domain": "iot",
        "version": CONTRACT_VERSION,
        "description": "Deterministik IoT ORKESTRASYON: thing registry + telemetri alım + eşik-tabanlı uyarı "
                       "(deterministik) + aktüatör komut durum makinesi + connector routing + risk "
                       "sınıflandırma (yüksek-risk komut onay ister, Madde 24). Gerçek protokol/cihaz "
                       "adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [IoTEvents.THING_REGISTERED, IoTEvents.TELEMETRY_INGESTED, IoTEvents.ALERT_RULE_ADDED,
                   IoTEvents.ALERT_TRIGGERED, IoTEvents.COMMAND_CREATED, IoTEvents.COMMAND_COMPLETED,
                   IoTEvents.COMMAND_FAILED, IoTEvents.NO_CONNECTOR, IoTEvents.APPROVAL_REQUIRED,
                   IoTEvents.APPROVED],
        "thing_kinds": ["sensor", "actuator", "gateway"],
        "protocols": ["mqtt", "coap", "http", "zigbee"],
        "comparators": [">", ">=", "<", "<=", "==", "!="],
        "op_statuses": ["pending", "running", "completed", "failed", "no_connector", "requires_approval"],
        "invariants": ["gerçek protokol/cihaz adapter'a delege edilir (çekirdek erişim yapmaz)",
                       "sensör komut kabul etmez; yalnız actuator/gateway komutlanır",
                       "yüksek-risk/geri-alınamaz aktüatör komutu onay ister (Madde 24); onaysız çalışmaz",
                       "connector yoksa no_connector (uydurma sonuç YOK — Madde 8)",
                       "telemetri eşik değerlendirmesi deterministiktir (LLM'siz)"],
    }
