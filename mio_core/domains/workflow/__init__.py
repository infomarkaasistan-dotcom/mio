"""MIO Core · Workflow Domain (bounded context). Public yüzey.

Görev grafı (DAG) + checkpoint/resume + human-approval + rollback. Domain ConnectorManager çağırmaz; her görev
CapabilityIntent taşır — Executive yürütür. Human-approval görevi onaysız çalışmaz (Madde 24)."""

from .contract import CONTRACT_VERSION, WorkflowEvents, workflow_contract
from .models import (
    DAGError,
    NotFoundError,
    TaskStatus,
    UnauthorizedError,
    ValidationError,
    Workflow,
    WorkflowConfig,
    WorkflowError,
    WorkflowStatus,
    WorkflowTask,
    topological_order,
    validate_dag,
)
from .repository import WorkflowRepository
from .service import WorkflowDomain

__all__ = [
    "WorkflowDomain", "WorkflowRepository", "Workflow", "WorkflowTask", "TaskStatus", "WorkflowStatus",
    "WorkflowConfig", "validate_dag", "topological_order",
    "WorkflowError", "ValidationError", "UnauthorizedError", "NotFoundError", "DAGError",
    "WorkflowEvents", "workflow_contract", "CONTRACT_VERSION",
]
