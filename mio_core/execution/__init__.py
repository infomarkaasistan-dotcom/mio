"""MIO Core · Execution katmanı — Executive otoritesi altında YÜRÜTME.

Şu anki içerik: Tool Orchestrator (gerçek yürütme motoru). Hiçbir Brain doğrudan 3. taraf API kullanmaz;
her dış-dünya erişimi buradan geçer (ADR-0002 Madde 8). LLM de (X4 Model Gateway) buraya bir ToolExecutor
olarak bağlanır — araç/danışman, karar verici değil.
"""

from .capability_discovery import (
    CapabilityDiscovery,
    DiscoveredCapability,
    DiscoveryReport,
    capability_index,
)
from .mcp_hub import MCPClient, MCPHub, MCPServer, MCPTool, ServerStatus, TrustLevel
from .federation import CapabilityProvider, FederatedCapabilities, LocalProvider
from .insight import CapabilityAnalytics, MCPStore, SelfDiagnostics
from .marketplace import (
    AutoInstaller,
    CapabilityMarketplace,
    InstallResult,
    MarketEntry,
    RecommendationEngine,
    default_marketplace,
)
from .meta_mcp import CapabilityMetrics, CapabilityPolicyEngine, MetaMCPManager
from .policy_profiles import PolicyProfile, PolicyProfiles
from .sandbox import SandboxPipeline, SandboxReport, StageResult
from .version_manager import VersionInfo, VersionManager
from .model_gateway import (
    GatewayError,
    GatewayResult,
    ModelGateway,
    ModelProvider,
    ModelSpec,
    llm_capability,
)
from .orchestrator import (
    AuditEntry,
    SQLiteToolAuditStore,
    ToolAuditStore,
    ToolExecutor,
    ToolOrchestrator,
    ToolRequest,
    ToolResult,
)

__all__ = [
    "AuditEntry",
    "CapabilityDiscovery",
    "DiscoveredCapability",
    "DiscoveryReport",
    "GatewayError",
    "GatewayResult",
    "AutoInstaller",
    "CapabilityAnalytics",
    "CapabilityMarketplace",
    "CapabilityMetrics",
    "CapabilityPolicyEngine",
    "CapabilityProvider",
    "FederatedCapabilities",
    "InstallResult",
    "LocalProvider",
    "MCPClient",
    "MCPStore",
    "MarketEntry",
    "PolicyProfile",
    "PolicyProfiles",
    "RecommendationEngine",
    "SelfDiagnostics",
    "default_marketplace",
    "MCPHub",
    "MCPServer",
    "MCPTool",
    "MetaMCPManager",
    "ModelGateway",
    "SandboxPipeline",
    "SandboxReport",
    "StageResult",
    "VersionInfo",
    "VersionManager",
    "ModelProvider",
    "ModelSpec",
    "SQLiteToolAuditStore",
    "ServerStatus",
    "TrustLevel",
    "ToolAuditStore",
    "ToolExecutor",
    "ToolOrchestrator",
    "ToolRequest",
    "ToolResult",
    "capability_index",
    "llm_capability",
]
