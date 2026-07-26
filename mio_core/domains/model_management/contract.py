"""MIO Core · Model Management Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ModelEvents:
    MODEL_REGISTERED = "model.registered"
    MODEL_PROVISIONED = "model.provisioned"
    PROVISION_FAILED = "model.provision_failed"
    NO_CONNECTOR = "model.no_connector"
    MODEL_SELECTED = "model.selected"
    MODEL_DEPRECATED = "model.deprecated"
    MODEL_REACTIVATED = "model.reactivated"
    RETIRE_APPROVAL_REQUIRED = "model.retire_approval_required"
    MODEL_RETIRED = "model.retired"


OPERATIONS = ("register_model", "provision", "select", "deprecate", "reactivate", "retire",
              "get_model", "list_models", "providers", "stats")


def model_contract() -> dict[str, Any]:
    return {
        "domain": "model_management",
        "version": CONTRACT_VERSION,
        "description": "Model registry + sürüm + yaşam-döngüsü durum makinesi + DETERMİNİSTİK seçim politikası "
                       "(priority/context/cost) + sağlayıcı connector routing. LLM danışman; model seçimi "
                       "deterministik. Gerçek indirme/serve adapter'a delege; yoksa no_connector (model "
                       "available olmaz). Retire onay ister (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [ModelEvents.MODEL_REGISTERED, ModelEvents.MODEL_PROVISIONED, ModelEvents.PROVISION_FAILED,
                   ModelEvents.NO_CONNECTOR, ModelEvents.MODEL_SELECTED, ModelEvents.MODEL_DEPRECATED,
                   ModelEvents.MODEL_REACTIVATED, ModelEvents.RETIRE_APPROVAL_REQUIRED,
                   ModelEvents.MODEL_RETIRED],
        "model_kinds": ["llm", "embedding", "vision", "speech", "rerank"],
        "locations": ["local", "remote", "hosted"],
        "lifecycle": ["registered", "available", "deprecated", "retired"],
        "selection_policy": "deterministik: priority↑, context_window↑, cost↓, name (kararlı tie-break)",
        "invariants": ["model seçimi DETERMİNİSTİK politikadır; LLM karar verici DEĞİL",
                       "yalnız 'available' model seçilebilir",
                       "gerçek indirme/serve provider adapter'a delege; yoksa no_connector (available olmaz)",
                       "yaşam-döngüsü geçişleri kısıtlıdır (retired terminaldir)",
                       "retire (yetenek kaybı) onay ister (Madde 24; owner/Executive)"],
    }
