"""MIO Core · Simulation & Digital Twin Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class DigitalTwinEvents:
    TWIN_REGISTERED = "twin.registered"
    SIMULATED = "twin.simulated"
    NO_SIMULATOR = "twin.no_simulator"
    SIM_FAILED = "twin.sim_failed"
    RESULT_APPLIED = "twin.result_applied"


OPERATIONS = ("register_twin", "update_state", "simulate", "apply_result", "get_twin", "list_twins",
              "get_run", "list_runs", "simulators", "stats")


def digital_twin_contract() -> dict[str, Any]:
    return {
        "domain": "digital_twin",
        "version": CONTRACT_VERSION,
        "description": "Dijital ikiz (twin) registry + DETERMİNİSTİK durum/geçiş simülasyonu (state + adım/effect; "
                       "what-if) + senaryo çalıştırma kaydı. SİMÜLASYON ≠ GERÇEKLİK: simulate() ikizi mutate "
                       "etmez; sonuç ÖNERİDİR, yansıtma (apply_result) Madde 24 onayı ister. Dış fiziksel model "
                       "gerekli ikiz için adapter'a delege; yoksa no_simulator.",
        "operations": list(OPERATIONS),
        "events": [DigitalTwinEvents.TWIN_REGISTERED, DigitalTwinEvents.SIMULATED,
                   DigitalTwinEvents.NO_SIMULATOR, DigitalTwinEvents.SIM_FAILED,
                   DigitalTwinEvents.RESULT_APPLIED],
        "step_ops": ["set", "inc", "dec", "mul", "min", "max"],
        "sim_statuses": ["completed", "no_simulator", "failed"],
        "invariants": ["simulate() ikizi MUTATE ETMEZ (kopya üstünde çalışır) — sim ≠ gerçeklik",
                       "simülasyon sonucu ÖNERİDİR; ikize/gerçeğe yansıtma Madde 24 onayı ister (owner/Executive)",
                       "durum/geçiş simülasyonu DETERMİNİSTİK (LLM karar verici değil)",
                       "dış fiziksel model gerekli ikiz için adapter yoksa no_simulator (uydurma YOK — Madde 8)",
                       "gerçek varlık kontrolü çekirdekte YOK"],
    }
