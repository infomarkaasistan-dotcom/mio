"""MIO Core · Workflow Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class WorkflowEvents:
    CREATED = "workflow.created"
    STARTED = "workflow.started"
    TASK_READY = "workflow.task_ready"
    TASK_COMPLETED = "workflow.task_completed"
    TASK_FAILED = "workflow.task_failed"
    APPROVAL_REQUIRED = "workflow.approval_required"
    ROLLED_BACK = "workflow.rolled_back"
    COMPLETED = "workflow.completed"
    FAILED = "workflow.failed"


OPERATIONS = ("create_workflow", "start", "ready_tasks", "complete_task", "fail_task", "approve_task",
              "rollback", "plan", "get_workflow", "list_workflows", "stats")


def workflow_contract() -> dict[str, Any]:
    return {
        "domain": "workflow",
        "version": CONTRACT_VERSION,
        "description": "Görev grafı (DAG) + yürütme planı + checkpoint/resume + human-approval + rollback. "
                       "İş mantığı (bağımlılık/döngü/topolojik sıra/checkpoint) burada; her görev CapabilityIntent "
                       "taşır — yürütmeye EXECUTIVE karar verir (ConnectorManager Executive'te). Human-approval "
                       "görevi onaysız yürütülmez (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [WorkflowEvents.CREATED, WorkflowEvents.STARTED, WorkflowEvents.TASK_READY,
                   WorkflowEvents.TASK_COMPLETED, WorkflowEvents.TASK_FAILED,
                   WorkflowEvents.APPROVAL_REQUIRED, WorkflowEvents.ROLLED_BACK, WorkflowEvents.COMPLETED,
                   WorkflowEvents.FAILED],
        "task_statuses": ["pending", "ready", "running", "completed", "failed", "skipped",
                          "blocked_approval"],
        "workflow_statuses": ["draft", "running", "paused", "completed", "failed"],
        "invariants": ["görev grafı DAG'dir (döngü reddedilir — deterministik tespit)",
                       "bir görev yalnız TÜM bağımlılıkları completed olunca ready olur",
                       "human-approval görevi ready olsa bile onaysız çalışmaz (Madde 24; blocked_approval)",
                       "checkpoint: tamamlanan görevler kalıcı → resume kaldığı yerden",
                       "rollback bir görevi + ardıllarını pending yapar (deterministik descendant)",
                       "domain ConnectorManager çağırmaz; görev CapabilityIntent taşır (Executive yürütür)"],
    }
