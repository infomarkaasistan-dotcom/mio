"""MIO Core · Multi-Agent Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class MultiAgentEvents:
    AGENT_REGISTERED = "agent.registered"
    TASK_SUBMITTED = "agent.task_submitted"
    TASK_ASSIGNED = "agent.task_assigned"
    TASK_COMPLETED = "agent.task_completed"
    TASK_FAILED = "agent.task_failed"
    NO_AGENT = "agent.no_agent"
    NO_CONNECTOR = "agent.no_connector"
    APPROVAL_REQUIRED = "agent.approval_required"
    APPROVED = "agent.approved"


OPERATIONS = ("register_agent", "submit_task", "approve_task", "get_task", "list_tasks", "list_agents",
              "eligible_agents", "executors", "stats")


def multi_agent_contract() -> dict[str, Any]:
    return {
        "domain": "multi_agent",
        "version": CONTRACT_VERSION,
        "description": "Agent registry + DETERMİNİSTİK görev atama (yetenek + güven + boş kapasite) + koordinasyon "
                       "durum makinesi. Executive tek karar verici; agent iş yürütür, tek başına karar vermez. "
                       "Gerçek uzak agent çağrısı adapter'a delege; yoksa no_connector. Yüksek-risk görev onay "
                       "ister (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [MultiAgentEvents.AGENT_REGISTERED, MultiAgentEvents.TASK_SUBMITTED,
                   MultiAgentEvents.TASK_ASSIGNED, MultiAgentEvents.TASK_COMPLETED,
                   MultiAgentEvents.TASK_FAILED, MultiAgentEvents.NO_AGENT, MultiAgentEvents.NO_CONNECTOR,
                   MultiAgentEvents.APPROVAL_REQUIRED, MultiAgentEvents.APPROVED],
        "task_statuses": ["pending", "assigned", "working", "completed", "failed", "no_agent",
                          "no_connector", "requires_approval"],
        "assignment_policy": "deterministik: yetenek ⊇ gerekli + boş kapasite; skor (trust↑, spare↑, name)",
        "invariants": ["Executive tek karar verici; agent iş yürütür, tek başına karar VERMEZ",
                       "görev ataması DETERMİNİSTİK (LLM karar verici değil)",
                       "uygun agent yoksa no_agent; executor yoksa no_connector (uydurma sonuç YOK — Madde 8)",
                       "yüksek-risk/geri-alınamaz görev onay ister (Madde 24); onaysız çalışmaz"],
    }
