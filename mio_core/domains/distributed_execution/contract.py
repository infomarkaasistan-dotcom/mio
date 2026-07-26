"""MIO Core · Distributed Execution Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class DistExecEvents:
    NODE_REGISTERED = "distexec.node_registered"
    NODE_STATUS_CHANGED = "distexec.node_status_changed"
    JOB_SUBMITTED = "distexec.job_submitted"
    JOB_DEDUPED = "distexec.job_deduped"
    JOB_SCHEDULED = "distexec.job_scheduled"
    JOB_COMPLETED = "distexec.job_completed"
    JOB_FAILED = "distexec.job_failed"
    NO_NODE = "distexec.no_node"
    NO_CONNECTOR = "distexec.no_connector"
    APPROVAL_REQUIRED = "distexec.approval_required"
    APPROVED = "distexec.approved"


OPERATIONS = ("register_node", "set_node_status", "submit", "approve_job", "get_job", "list_jobs",
              "list_nodes", "eligible_nodes", "executors", "stats")


def dist_exec_contract() -> dict[str, Any]:
    return {
        "domain": "distributed_execution",
        "version": CONTRACT_VERSION,
        "description": "Worker node registry + DETERMİNİSTİK iş dağıtım/zamanlama (yetenek + kapasite + öncelik) + "
                       "dağıtık iş durum makinesi + idempotency (effectively-once). Execution tek başına karar "
                       "vermez; dağıtım deterministik. Gerçek uzak çalıştırma adapter'a delege; düğüm yoksa "
                       "no_node, executor yoksa no_connector. Yüksek-risk iş onay ister (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [DistExecEvents.NODE_REGISTERED, DistExecEvents.NODE_STATUS_CHANGED,
                   DistExecEvents.JOB_SUBMITTED, DistExecEvents.JOB_DEDUPED, DistExecEvents.JOB_SCHEDULED,
                   DistExecEvents.JOB_COMPLETED, DistExecEvents.JOB_FAILED, DistExecEvents.NO_NODE,
                   DistExecEvents.NO_CONNECTOR, DistExecEvents.APPROVAL_REQUIRED, DistExecEvents.APPROVED],
        "node_statuses": ["healthy", "draining", "down"],
        "job_statuses": ["queued", "scheduled", "running", "completed", "failed", "no_node",
                         "no_connector", "requires_approval"],
        "scheduling_policy": "deterministik: HEALTHY + yetenek ⊇ gerekli + boş kapasite; skor (spare↑, name)",
        "invariants": ["iş dağıtımı DETERMİNİSTİK (LLM karar verici değil)",
                       "yalnız HEALTHY + yetenekli + boş kapasiteli düğüme dağıtılır",
                       "idempotency_key ile effectively-once (canlı/başarılı iş tekrarlanmaz)",
                       "uygun düğüm yoksa no_node; executor yoksa no_connector (uydurma sonuç YOK — Madde 8)",
                       "yüksek-risk/geri-alınamaz dağıtık iş onay ister (Madde 24); onaysız çalışmaz"],
    }
