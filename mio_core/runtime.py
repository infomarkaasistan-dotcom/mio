"""MIO Core · Production Runtime — gerçek, çalışan MIO Executive OS montajı (DEMO DEĞİL).

`boot()` tüm çekirdeği KALICI depolarla (SQLite, bir çalışma alanında) kurar, MIO'yu `birth()` ile yetenekli
doğurur, GERÇEK Ollama'yı (varsa) bağlar ve donanımı keşfeder; canlı bir `MIORuntime` döner. Bu bir gösterim
betiği değil, üretim fabrikasıdır: bir servis (API), zamanlayıcı ya da başka bir süreç bunu kullanır.

Dış sistem (Ollama/donanım) yoksa dürüstçe atlanır — MIO yine yetenekli doğar ve deterministik çekirdek
LLM-siz çalışır. Hiçbir Brain LLM'i ya da dış aracı doğrudan çağırmaz: her şey Tool Orchestrator üzerinden.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from mio_core.adapters import (
    MCPServerConfig,
    StdioMCPClient,
    discover_hardware,
    register_reasoning,
    wire_ollama,
)
from mio_core.born import birth
from mio_core.brain_runtime import BrainResult, DomainBrainRuntime
from mio_core.brains import BrainRegistry
from mio_core.capability import CapabilityRegistry
from mio_core.domains.capability_mgmt import CapabilityManagementDomain, CapabilityRepository
from mio_core.domains.audit import AuditComplianceDomain, AuditRepository
from mio_core.domains.business_operations import BusinessOperationsDomain, BusinessRepository
from mio_core.domains.communication import CommunicationDomain, ConversationRepository, Intent
from mio_core.domains.customer_success import CustomerRepository, CustomerSuccessDomain
from mio_core.domains.data_analytics import DataAnalyticsDomain, DataRepository
from mio_core.domains.device import DeviceNativeDomain, DeviceRepository
from mio_core.domains.iot import IoTDomain, IoTRepository
from mio_core.domains.model_management import ModelManagementDomain, ModelRepository
from mio_core.domains.multi_agent import MultiAgentDomain, MultiAgentRepository
from mio_core.domains.marketplace import MarketplaceDomain, MarketplaceRepository
from mio_core.domains.knowledge_marketplace import KnowledgeMarketplaceDomain, KnowledgeMarketRepository
from mio_core.domains.federation import FederationDomain, FederationRepository
from mio_core.domains.distributed_execution import DistributedExecutionDomain, DistExecRepository
from mio_core.domains.autonomous_ops import AutonomousOperationsDomain, AutoOpsRepository
from mio_core.domains.digital_twin import DigitalTwinDomain, DigitalTwinRepository
from mio_core.domains.extension_sdk import ExtensionSDKDomain, ExtensionRepository
from mio_core.domains.presentation import PresentationDomain, PresentationRepository
from mio_core.domains.conversation import ConversationDomain
from mio_core.domains.conversation import ConversationRepository as LiveConversationRepository
from mio_core.connectors import Advisor, ConnectorManager, ConnectorRegistry
from mio_core.monitoring import MonitoringAdapter
from mio_core.platform.config import Config
from mio_core.platform.hardware import HardwareDiagnostics
from mio_core.platform.local_inference import LocalInferenceManager
from mio_core.domains.document_intelligence import DocumentIntelligenceDomain, DocumentRepository
from mio_core.domains.execution import ExecutionDomain, ExecutionRepository
from mio_core.domains.executive import ExecutiveDomain
from mio_core.domains.finance import FinanceDomain, FinanceRepository
from mio_core.domains.goal_management import GoalManagementDomain
from mio_core.domains.knowledge import KnowledgeDomain, KnowledgeRepository
from mio_core.domains.learning import LearningDomain, LearningRepository
from mio_core.domains.marketing import MarketingDomain, MarketingRepository
from mio_core.domains.mcp_mgmt import MCPManagementDomain, MCPRepository
from mio_core.domains.media import MediaGenerationDomain, MediaRepository
from mio_core.domains.memory import MemoryDomain, MemoryRepository
from mio_core.domains.observability import ObservabilityDomain, TelemetryRepository
from mio_core.domains.perception import PerceptionDomain, PerceptionRepository
from mio_core.domains.planning import PlanningDomain, PlanRepository
from mio_core.domains.policy import PolicyDomain, PolicyRepository
from mio_core.domains.reasoning import ReasoningDomain, ReasoningRepository
from mio_core.domains.research import ResearchDomain, ResearchRepository
from mio_core.domains.resources import ResourceRepository, ResourceRuntimeDomain
from mio_core.domains.sales import SalesCRMDomain, SalesRepository
from mio_core.domains.scheduler import ScheduleRepository, SchedulerDomain
from mio_core.domains.security import SecurityDomain, SecurityRepository
from mio_core.domains.software_engineering import SoftwareEngineeringDomain, SoftwareRepository
from mio_core.domains.verticals import AdviceRepository, VerticalBrains
from mio_core.domains.vision import VisionDomain, VisionRepository
from mio_core.domains.voice import VoiceDomain, VoiceRepository
from mio_core.domains.web_intelligence import WebIntelligenceDomain, WebRepository
from mio_core.events import EventBus
from mio_core.platform.resilience import Backoff, ResiliencePolicy
from mio_core.execution import (
    CapabilityAnalytics,
    CapabilityDiscovery,
    CapabilityMarketplace,
    DiscoveryReport,
    MCPHub,
    MCPStore,
    MetaMCPManager,
    ModelGateway,
    PolicyProfiles,
    RecommendationEngine,
    SQLiteToolAuditStore,
    SelfDiagnostics,
    ToolOrchestrator,
    ToolRequest,
    ToolResult,
    VersionManager,
    capability_index,
    default_marketplace,
    llm_capability,
)
from mio_core.executive import (
    CognitiveEngine,
    CognitiveIdentity,
    ExecutiveReview,
    ExecutiveState,
    GoalManager,
    GoalProgressSignals,
    GovernanceEngine,
    SQLiteBeliefStore,
    SQLiteExecutiveStateStore,
    SQLiteGoalStore,
)
from mio_core.knowledge import KnowledgeBase
from mio_core.persistence import JsonKVStore
from mio_core.self_awareness import SelfAwareness

__all__ = ["MIORuntime", "boot"]


# --- Operational Readiness yardımcıları (DETERMİNİSTİK, dış bağımlılıksız) --------------------------- #
# readiness() tarafından sorgulanan sözleşmeli domainler (Faz 3-5). Her biri versiyonlu contract() sunar.
_READINESS_DOMAINS = (
    "software_engineering", "research", "document_intelligence", "data_analytics", "business_operations",
    "finance", "sales", "marketing", "customer_success",
    "vision", "voice", "media", "web", "device", "iot",
    "model_management", "multi_agent", "marketplace_domain", "knowledge_marketplace", "federation",
    "distributed_execution", "autonomous_operations", "digital_twin", "extension_sdk", "presentation",
    "conversation",
)


def _resilience_available() -> bool:
    """Resilience katmanı (Madde 28) yüklenebilir mi?"""
    try:
        from mio_core.platform.resilience import ResiliencePolicy  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _workspace_writable(workspace: str) -> dict[str, Any]:
    """Workspace dizini yazılabilir mi (deterministik config doğrulaması)."""
    if not workspace:
        return {"ok": True, "detail": "in-memory/unset"}
    import os
    import tempfile
    try:
        os.makedirs(workspace, exist_ok=True)
        fd, path = tempfile.mkstemp(dir=workspace, prefix=".readiness_", suffix=".tmp")
        os.close(fd)
        os.remove(path)
        return {"ok": True, "detail": workspace}
    except Exception as exc:  # noqa: BLE001 — yazılamayan workspace hazır DEĞİL (dürüst)
        return {"ok": False, "detail": f"{workspace}: {str(exc)[:120]}"}


class MIORuntime:
    """Canlı, montajı yapılmış MIO Executive OS. Tüm katmanlar bağlı ve kullanılabilir."""

    def __init__(self, **components: Any) -> None:
        self.state: ExecutiveState = components["state"]
        self.cognitive: CognitiveEngine = components["cognitive"]
        self.knowledge: KnowledgeBase = components["knowledge"]
        self.brains: BrainRegistry = components["brains"]
        self.capabilities: CapabilityRegistry = components["capabilities"]
        self.gateway: ModelGateway = components["gateway"]
        self.orchestrator: ToolOrchestrator = components["orchestrator"]
        self.governance: GovernanceEngine = components["governance"]
        self.goals: GoalManager = components["goals"]
        self.review: ExecutiveReview = components["review"]
        self.cognitive_identity: CognitiveIdentity = components["cognitive_identity"]
        self.self_awareness: SelfAwareness = components["self_awareness"]
        self.brain_runtime: DomainBrainRuntime = components["brain_runtime"]
        self.discovery: CapabilityDiscovery = components["discovery"]
        self.meta: MetaMCPManager = components["meta"]
        self.executive: ExecutiveDomain = components["executive"]
        self.memory: MemoryDomain = components["memory"]
        self.knowledge_domain: KnowledgeDomain = components["knowledge_domain"]
        self.reasoning: ReasoningDomain = components["reasoning"]
        self.planning: PlanningDomain = components["planning"]
        self.learning: LearningDomain = components["learning"]
        self.goal_management: GoalManagementDomain = components["goal_management"]
        self.communication: CommunicationDomain = components["communication"]
        self.execution: ExecutionDomain = components["execution"]
        self.perception: PerceptionDomain = components["perception"]
        self.verticals: VerticalBrains = components["verticals"]
        self.scheduler: SchedulerDomain = components["scheduler"]
        self.observability_domain: ObservabilityDomain = components["observability_domain"]
        self.policy: PolicyDomain = components["policy"]
        self.security: SecurityDomain = components["security"]
        self.capability_management: CapabilityManagementDomain = components["capability_management"]
        self.mcp_management: MCPManagementDomain = components["mcp_management"]
        self.audit: AuditComplianceDomain = components["audit"]
        self.resources: ResourceRuntimeDomain = components["resources"]
        self.software_engineering: SoftwareEngineeringDomain = components["software_engineering"]
        self.research: ResearchDomain = components["research"]
        self.document_intelligence: DocumentIntelligenceDomain = components["document_intelligence"]
        self.data_analytics: DataAnalyticsDomain = components["data_analytics"]
        self.business_operations: BusinessOperationsDomain = components["business_operations"]
        self.finance: FinanceDomain = components["finance"]
        self.sales: SalesCRMDomain = components["sales"]
        self.marketing: MarketingDomain = components["marketing"]
        self.customer_success: CustomerSuccessDomain = components["customer_success"]
        self.vision: VisionDomain = components["vision"]
        self.voice: VoiceDomain = components["voice"]
        self.media: MediaGenerationDomain = components["media"]
        self.web: WebIntelligenceDomain = components["web"]
        self.device: DeviceNativeDomain = components["device"]
        self.iot: IoTDomain = components["iot"]
        self.model_management: ModelManagementDomain = components["model_management"]
        self.multi_agent: MultiAgentDomain = components["multi_agent"]
        self.marketplace_domain: MarketplaceDomain = components["marketplace_domain"]
        self.knowledge_marketplace: KnowledgeMarketplaceDomain = components["knowledge_marketplace"]
        self.federation: FederationDomain = components["federation"]
        self.distributed_execution: DistributedExecutionDomain = components["distributed_execution"]
        self.autonomous_operations: AutonomousOperationsDomain = components["autonomous_operations"]
        self.digital_twin: DigitalTwinDomain = components["digital_twin"]
        self.extension_sdk: ExtensionSDKDomain = components["extension_sdk"]
        self.presentation: PresentationDomain = components["presentation"]
        self.conversation: ConversationDomain = components["conversation"]
        # Capability Adapter Layer (Connector): Executive yalnız execute(capability, request) bilir.
        self.connector_registry: ConnectorRegistry = components["connector_registry"]
        self.connectors: ConnectorManager = components["connectors"]
        self.advisor: Advisor = components["advisor"]
        # Monitoring Adapter: çekirdek metriklerini Prometheus/OTLP'ye aktarır (çekirdek framework-bağımsız).
        # self.metrics/self.readiness metodlarına bağlanır (lazy — yalnız çağrıldığında okur).
        self.monitoring: MonitoringAdapter = MonitoringAdapter(self.metrics, readiness_fn=self.readiness)
        # Hardware Diagnostics & Awareness (lazy — yalnız report() çağrılınca sistem taranır).
        self.hardware: HardwareDiagnostics = HardwareDiagnostics()
        # Local Inference Manager: MIO çalışacağı ortamı yönetir (Ollama+modeller; analyze/ensure_ready).
        self.local_inference: LocalInferenceManager = LocalInferenceManager(self.hardware)
        # Açılışta otomatik hazırlık sonucu (prepare_inference/MIO_AUTO_INFERENCE açıksa dolar; aksi None).
        self.inference_status: Optional[dict[str, Any]] = None
        self._http_handle = None             # gömülü HTTP sunucusu yaşam-döngüsü (lazy; CLI'dan yönetilir)
        self.bus: EventBus = components["bus"]
        self.versions: VersionManager = components["versions"]
        self.marketplace: CapabilityMarketplace = components["marketplace"]
        self.recommendation: RecommendationEngine = components["recommendation"]
        self.policy_profiles: PolicyProfiles = components["policy_profiles"]
        self._store: MCPStore = components["store"]
        self._diag: SelfDiagnostics = components["diagnostics"]
        self._analytics: CapabilityAnalytics = components["analytics"]
        self.mcp_hub: Optional[MCPHub] = components.get("mcp_hub")
        self.birth_summary: dict[str, Any] = components["birth_summary"]
        self._stores: list = components["stores"]
        self._closeables: list = components.get("closeables", [])
        self._kv: Optional[JsonKVStore] = components.get("kv")
        self._workspace: str = components.get("workspace", "")
        self._closed: bool = False           # graceful shutdown idempotency (Operational Readiness)
        # TEK yapılandırma kaynağı (.env + os.environ). Tüm arayüzler bunu tüketir (Interface Architecture).
        self.config: Config = components.get("config") or Config(env_file=None)

    # -- production kullanım yüzeyi (gerçek, demo değil) -------------------- #
    def who_am_i(self) -> dict[str, Any]:
        """MIO'nun tam öz-modeli (kimlik/purpose/hedef/brain/capability/model/donanım/kısıt)."""
        return self.self_awareness.self_model()

    def ask_llm(self, prompt: str, *, requester: str = "executive", system: Optional[str] = None,
                max_tokens: int = 500, priority: str = "balanced") -> ToolResult:
        """LLM'i YALNIZ Tool Orchestrator üzerinden kullanır (danışman). 'llm' bağlı değilse dürüst blok."""
        return self.orchestrator.execute(ToolRequest(
            "llm", "generate",
            {"prompt": prompt, "system": system, "max_tokens": max_tokens, "priority": priority},
            requester=requester))

    def recommend(self, context_tags: set[str]) -> list:
        """Innate bilgiden deterministik öneri (LLM'siz karar üretimi)."""
        return self.knowledge.apply(context_tags)

    def perform(self, brain: str, task: str, *, context_tags: Optional[set] = None) -> BrainResult:
        """Bir Domain Brain'in görevi alanında nasıl ele alacağını üretir (yürütmez)."""
        return self.brain_runtime.perform(brain, task, context_tags=context_tags)

    def discover_mcp(self, configs, *, transport_factory=None) -> DiscoveryReport:
        """ÇALIŞMA ANINDA yeni MCP sunucu(lar)ı ekler — SIFIR KOD. MIO otomatik keşfeder, capability'ye
        çevirir, Executive'e raporlar; ardından Brain'ler yeni yeteneği kullanabilir. `configs` tek
        MCPServerConfig ya da liste olabilir."""
        from mio_core.adapters import StdioMCPClient
        cfg_list = configs if isinstance(configs, list) else [configs]
        client = StdioMCPClient(cfg_list, transport_factory=transport_factory)
        self._closeables.append(client)
        return self.discovery.discover(client)

    def capability_index(self) -> list:
        """Meta katalog: MIO'nun TÜM yetenekleri (ne / kaynak / risk / bağlı / izin / kim kullanır)."""
        return capability_index(self.capabilities)

    def capability_catalog(self) -> list:
        """Meta MCP zengin katalog: statik + dinamik (trust/health/metrik) her yetenek için."""
        return self.meta.catalog()

    def select_best(self, category: str, *, requester: Optional[str] = None) -> Optional[str]:
        """Bir kategoride en iyi alternatifi seç (load-balance + cost-optimize)."""
        return self.meta.select_best(category, requester=requester)

    def diagnostics(self) -> dict:
        """MIO kendi sağlığını analiz eder (Self Diagnostics)."""
        return self._diag.run()

    def analytics(self) -> dict:
        """Yetenek kullanım analizi (en çok/hızlı/güvenilir...)."""
        return self._analytics.report()

    def mcp_store(self) -> list:
        """Kurulu MCP'lerin gerçek-zamanlı durumu."""
        return self._store.state()

    def recommend_capability(self, query: str) -> list:
        """Görev için eksik yeteneği Marketplace'ten öner (Recommendation Engine)."""
        return self.recommendation.recommend(query)

    def activate_policy(self, profile: str):
        """Policy profili değiştir (Safe/Developer/Business/Autonomous/ReadOnly/Offline/HighSecurity)."""
        return self.policy_profiles.activate(profile)

    def health(self) -> dict:
        """Genel sağlık durumu (Area 6 — production ops)."""
        d = self._diag.run()
        connected, dead = d["connected"], len(d["dead_capabilities"])
        status = "operational" if connected > 0 and not dead else ("degraded" if dead else "booting")
        return {"status": status, "connected_capabilities": connected, "dead": dead,
                "trust_avg": d["trust_avg"], "outdated": len(d["outdated"])}

    @property
    def http_server(self):
        """Gömülü HTTP API sunucusunun yaşam-döngüsü kolu (start/stop/status). Lazy — tek süreç içi."""
        if self._http_handle is None:
            from mio_core.platform.http_lifecycle import HTTPServerHandle
            self._http_handle = HTTPServerHandle(self)
        return self._http_handle

    def readiness(self) -> dict:
        """Operational Readiness self-check (DETERMİNİSTİK; dış adapter gerektirmez).

        Her bileşen için ok/fail döndürür: event bus, kalıcılık store'ları, resilience katmanı, workspace
        yazılabilirliği ve tüm sözleşmeli domainlerin `contract()` sorgulanabilirliği. Kubernetes-tarzı
        readiness probe'un çekirdek muadili. İş mantığı yok — yalnız hazırlık doğrulaması."""
        checks: dict[str, Any] = {}
        checks["not_closed"] = {"ok": not self._closed,
                                "detail": "closed" if self._closed else "open"}
        checks["event_bus"] = {"ok": self.bus is not None and hasattr(self.bus, "publish"),
                               "detail": type(self.bus).__name__ if self.bus is not None else None}
        checks["persistence_stores"] = {"ok": len(self._stores) > 0, "count": len(self._stores)}
        checks["resilience"] = {"ok": _resilience_available(), "detail": "mio_core.platform.resilience"}
        checks["workspace_writable"] = _workspace_writable(self._workspace)

        results, ready_count = {}, 0
        for name in _READINESS_DOMAINS:
            obj = getattr(self, name, None)
            ok = False
            if obj is not None:
                try:
                    ok = bool(obj.contract().get("version")) if hasattr(obj, "contract") else True
                except Exception:  # noqa: BLE001 — okunamayan domain hazır DEĞİL sayılır (dürüst)
                    ok = False
            results[name] = ok
            ready_count += 1 if ok else 0
        failed = [n for n, ok in results.items() if not ok]
        checks["domains"] = {"ok": not failed, "ready": ready_count,
                             "total": len(_READINESS_DOMAINS), "failed": failed}

        # Yerel çıkarım hazırlığı yapıldıysa bilgi olarak ekle (readiness'i BLOKLAMAZ — opsiyonel yetenek).
        if self.inference_status is not None:
            checks["local_inference"] = {"ok": True, "prepared": bool(self.inference_status.get("ready")),
                                         "model": self.inference_status.get("selected_model")}

        ready = all(c["ok"] for c in checks.values())
        return {"ready": ready, "checks": checks}

    def metrics(self) -> dict:
        """Birleşik metrik snapshot'ı (Observability): tüm sözleşmeli domainlerin `stats()`'ı + event bus
        sağlığı, tek deterministik görünümde. İş mantığı yok — makine-okur toplama/dashboard için."""
        domains: dict[str, Any] = {}
        for name in _READINESS_DOMAINS:
            obj = getattr(self, name, None)
            if obj is not None and hasattr(obj, "stats"):
                try:
                    domains[name] = obj.stats()
                except Exception as exc:  # noqa: BLE001 — okunamayan stats görünür kılınır (dürüst)
                    domains[name] = {"error": str(exc)[:120]}
        bus_health = {"subscriber_errors": self.bus.subscriber_errors()} if self.bus is not None else {}
        return {"domain_count": len(domains), "domains": domains, "event_bus": bus_health,
                "connectors": self.connectors.stats(), "closed": self._closed}

    def observability(self) -> dict:
        """Tek üretim-görünümü: sağlık + diagnostics + analytics + MCP store + son olaylar (Area 6).
        İş mantığı yok — yalnız gözlem (Dashboard bunu subscribe/okur)."""
        return {
            "health": self.health(),
            "analytics": self.analytics(),
            "mcp_store": self.mcp_store(),
            "capability_index": self.capability_index(),
            "recent_events": self.bus.history(limit=50),
            "policy_profile": self.policy_profiles.active.name,
        }

    def persist(self) -> None:
        """Yaşayarak öğrenilen bilgi + kullanım metriklerini kalıcılığa yazar (Area 3)."""
        if self._kv is not None:
            self._kv.put("knowledge_learned", [i.to_dict() for i in self.knowledge.learned()])
            self._kv.put("meta_metrics", self.meta.export_metrics())

    def close(self) -> dict:
        """Graceful shutdown — IDEMPOTENT + hataları GÖRÜNÜR kılan yapılandırılmış rapor (Madde 27).

        Best-effort: bir bileşen kapanmazsa raise ETMEZ ama hatayı raporda yüzeye çıkarır (sessiz yutma yok).
        İkinci çağrı no-op'tur (idempotent). Backward-compat: dönüş değeri artık bir rapor sözlüğü (eski
        çağrılar dönüşü yok saysa da çalışır)."""
        report: dict[str, Any] = {"already_closed": self._closed, "closed": [], "errors": []}
        if self._closed:
            return report
        self._closed = True

        def _try(component: str, fn) -> None:
            try:
                fn()
                report["closed"].append(component)
            except Exception as exc:  # noqa: BLE001 — kapanış hatası GÖRÜNÜR olur, süreci durdurmaz
                report["errors"].append({"component": component, "error": str(exc)[:200]})

        if self._http_handle is not None and self._http_handle.is_running():
            _try("http_server", self._http_handle.stop)   # gömülü HTTP sunucusunu durdur (graceful)
        _try("persist", self.persist)
        if self._kv is not None:
            _try("kv", self._kv.close)
        for c in self._closeables:
            _try(type(c).__name__, c.close)
        for s in self._stores:
            _try(type(s).__name__, s.close)
        return report


def boot(*, workspace: str = ".mio", identity_name: str = "MIO", connect_ollama: bool = True,
         ollama_base_url: str = "http://localhost:11434", discover_hw: bool = True,
         mcp_servers: Optional[list[MCPServerConfig]] = None,
         mcp_transport_factory: Optional[Any] = None,
         prepare_inference: Optional[bool] = None,
         env_file: Optional[str] = ".env", config: Optional[Config] = None) -> MIORuntime:
    """Gerçek MIO Executive OS'u ayağa kaldırır (kalıcı depolar + birth + gerçek adaptörler).

    `env_file`/`config`: TEK yapılandırma kaynağı. `.env` (+ os.environ) `Config`'e yüklenir; tüm arayüzler ve
    runtime aynı `mio.config`'i tüketir. `config` verilirse o kullanılır (test/izolasyon).

    `prepare_inference`: MIO açılışta çalışacağı yerel çıkarım ortamını KENDİSİ hazırlasın mı. None → `config`'ten
    `MIO_AUTO_INFERENCE` (varsayılan KAPALI). Güvenli işler otomatik; model SİLME/Ollama KURULUMU onaysız YAPILMAZ
    (Madde 24)."""
    cfg = config if config is not None else Config(env_file=env_file)
    os.makedirs(workspace, exist_ok=True)

    def _p(name: str) -> str:
        return os.path.join(workspace, name)

    # --- Kalıcı depolar ---
    exec_store = SQLiteExecutiveStateStore(_p("executive_state.db"))
    belief_store = SQLiteBeliefStore(_p("cognitive.db"))
    goal_store = SQLiteGoalStore(_p("goals.db"))
    audit_store = SQLiteToolAuditStore(_p("tool_audit.db"))

    # --- Çekirdek bileşenler ---
    state = ExecutiveState(exec_store)
    cognitive = CognitiveEngine(belief_store)
    knowledge = KnowledgeBase()
    brains = BrainRegistry()
    capabilities = CapabilityRegistry()
    gateway = ModelGateway()
    governance = GovernanceEngine(state)
    # Madde 28 (Resilience): üretim policy — retry + exponential backoff + circuit breaker. Yalnız GERÇEK
    # yürütücü başarısızlıklarında devreye girer (başarı yolu ve mevcut davranış korunur).
    resilience_policy = ResiliencePolicy(
        retries=1, backoff=Backoff(base=0.05, factor=2.0, max_delay=5.0, jitter=0.2),
        failure_threshold=5, reset_timeout=30.0)
    orchestrator = ToolOrchestrator(capabilities, governance=governance, audit_store=audit_store,
                                    resilience=resilience_policy)
    goals = GoalManager(goal_store, executive_state=state)
    review = ExecutiveReview(state, governance, belief_source=cognitive,
                             signals=GoalProgressSignals(goals))
    cognitive_identity = CognitiveIdentity(state, cognitive=cognitive)

    # --- BIRTH: yetenekli doğ (kimlik+misyon+purpose+brain+capability+innate belief+innate knowledge) ---
    birth_summary = birth(state, brains, capabilities, cognitive=cognitive, knowledge=knowledge,
                          identity_name=identity_name)
    capabilities.register(llm_capability())         # "llm" yetenek tanımı (henüz bağlı değil)
    register_reasoning(orchestrator, capabilities)  # doğuştan LLM-bağımsız karar-destek (native)

    # --- GERÇEK Ollama (varsa) — 'llm' yeteneğini bağlar; hiçbir Brain doğrudan çağırmaz ---
    ollama_models = 0
    if connect_ollama:
        try:
            ollama_models = wire_ollama(gateway, base_url=ollama_base_url)
            if ollama_models > 0:
                orchestrator.register_executor("llm", gateway)   # 'llm' artık bağlı
        except Exception:  # noqa: BLE001 — Ollama yoksa 'llm' bağlanmaz (dürüst)
            ollama_models = 0
    birth_summary["ollama_models"] = ollama_models

    # --- GERÇEK MCP sunucuları (varsa) — keşfet → capability → orchestrator (hiçbir Brain doğrudan API) ---
    # MCPHub HER ZAMAN var (MCP Management Domain onu yönetir); istemci yalnız sunucu yapılandırılınca bağlanır.
    mcp_hub = MCPHub(None)
    mcp_client: Optional[StdioMCPClient] = None
    mcp_bound = 0
    if mcp_servers:
        mcp_client = StdioMCPClient(mcp_servers, transport_factory=mcp_transport_factory)
        mcp_hub.register_client(mcp_client)
        try:
            mcp_bound = mcp_hub.activate(capabilities, orchestrator)["bound_capabilities"]
        except Exception:  # noqa: BLE001 — MCP sunucusu yoksa/çökerse dürüstçe atlanır
            mcp_bound = 0
    birth_summary["mcp_capabilities"] = mcp_bound

    # --- Donanım keşfi (kurulum katmanı 2) → Self Awareness ---
    hardware: dict[str, Any] = {}
    if discover_hw:
        try:
            hardware = discover_hardware()
        except Exception:  # noqa: BLE001
            hardware = {}

    self_awareness = SelfAwareness(state, brains, capabilities,
                                   available_models=gateway.connected_models(), hardware=hardware)
    brain_runtime = DomainBrainRuntime(brains, capabilities, knowledge, orchestrator)
    discovery = CapabilityDiscovery(capabilities, orchestrator, state=state)
    meta = MetaMCPManager(capabilities)
    meta.attach(orchestrator)                       # gerçek çağrılardan health/trust/benchmark

    # --- Ekosistem servisleri (event-driven; çekirdeği büyütmez) ---
    bus = EventBus(record=True)
    versions = VersionManager(bus=bus)
    marketplace = CapabilityMarketplace()
    marketplace.add_all(default_marketplace())
    store = MCPStore(capabilities, meta, versions=versions)
    diagnostics = SelfDiagnostics(capabilities, meta, versions=versions, bus=bus)
    analytics = CapabilityAnalytics(capabilities, meta, bus=bus)
    recommendation = RecommendationEngine(marketplace, capabilities, bus=bus)
    policy_profiles = PolicyProfiles(bus=bus)
    executive = ExecutiveDomain(state=state, goals=goals, governance=governance, review=review,
                                cognitive_identity=cognitive_identity, bus=bus)
    memory_repo = MemoryRepository(_p("memory.db"))
    memory = MemoryDomain(memory_repo, bus=bus)
    knowledge_repo = KnowledgeRepository(_p("knowledge.db"))
    knowledge_domain = KnowledgeDomain(knowledge, knowledge_repo, bus=bus)
    reasoning_repo = ReasoningRepository(_p("reasoning.db"))
    reasoning = ReasoningDomain(knowledge_domain, reasoning_repo, cognitive=cognitive, bus=bus)
    plan_repo = PlanRepository(_p("plans.db"))
    planning = PlanningDomain(plan_repo, capabilities=capabilities, reasoning=reasoning, bus=bus)
    learning_repo = LearningRepository(_p("learning.db"))
    learning = LearningDomain(learning_repo, knowledge=knowledge_domain, cognitive=cognitive, bus=bus)
    goal_management = GoalManagementDomain(goals, goal_store, bus=bus)

    # --- Communication (Faz 2): deterministik diyalog + niyet yönlendirme; LLM opsiyonel danışman ---
    def _status_handler(text: str, ctx: dict) -> str:
        m = self_awareness.self_model()
        ident = m.get("who_am_i") or {}
        name = ident.get("name", "MIO") if isinstance(ident, dict) else "MIO"
        purpose = m.get("purpose") or {}
        primary = purpose.get("primary_objective", "") if isinstance(purpose, dict) else ""
        goals_n = len(m.get("current_goals") or [])
        brains_n = len(m.get("brains") or [])
        caps_n = len((m.get("capabilities") or {}).get("connected") or [])
        return (f"Ben {name}. Amacım: {primary or 'uzun-vadeli hedef yönetimi'}. "
                f"Şu an {goals_n} aktif hedef, {brains_n} alan beyni ve {caps_n} bağlı yeteneğim var.")

    def _knowledge_handler(text: str, ctx: dict) -> str:
        hits = knowledge_domain.what_do_i_know(ctx["actor"], text, limit=3)
        if not hits:
            return ""                                  # bilgi yok → advisor/fallback'e düş
        return " ".join(h["statement"] for h in hits if h.get("statement"))

    def _goal_handler(text: str, ctx: dict) -> str:
        active = goal_management.list_goals(ctx["actor"], status="active")
        if not active:
            return "Şu an aktif bir hedefin yok. Bir uzun-vadeli hedef tanımlamak ister misin?"
        titles = ", ".join(g["text"] for g in active[:5])
        return f"{len(active)} aktif hedefin var: {titles}."

    def _plan_handler(text: str, ctx: dict) -> str:
        plans = planning.list_plans(ctx["actor"])
        return (f"Toplam {len(plans)} planın kayıtlı." if plans
                else "Kayıtlı planın yok. Bir amaç için plan taslağı oluşturabilirim.")

    def _llm_advisor(prompt: str):
        """LLM'i YALNIZ orchestrator üzerinden danışman olarak kullanır; bağlı değilse None (fallback)."""
        res = orchestrator.execute(ToolRequest(
            "llm", "generate", {"prompt": prompt, "max_tokens": 300, "priority": "balanced"},
            requester="Communication"))
        if getattr(res, "success", False) and res.output:
            out = res.output
            if isinstance(out, dict):
                return out.get("text") or out.get("content") or None
            return str(out)
        return None

    conversation_repo = ConversationRepository(_p("conversations.db"))
    communication = CommunicationDomain(conversation_repo, advisor=_llm_advisor, bus=bus)
    communication.register_handler(Intent.STATUS, _status_handler)
    communication.register_handler(Intent.QUERY_KNOWLEDGE, _knowledge_handler)
    communication.register_handler(Intent.GOAL, _goal_handler)
    communication.register_handler(Intent.PLAN, _plan_handler)

    # --- Execution (Faz 2): onaylı plan/kararı gerçek araçlarla yürütür (Execution tek başına karar vermez) ---
    execution_repo = ExecutionRepository(_p("execution.db"))
    execution = ExecutionDomain(orchestrator, execution_repo, planning=planning, learning=learning, bus=bus)

    # --- Perception (Faz 2): dış sinyalleri normalize eder → E5 belief / Memory epizodik / Attention ---
    perception_repo = PerceptionRepository(_p("perception.db"))
    perception = PerceptionDomain(perception_repo, memory=memory, cognitive=cognitive, bus=bus)

    # --- Vertical Domain Brains (Faz 3): 8 alan beyni — tavsiye üretir, KARAR VERMEZ (Executive'e gider) ---
    advice_repo = AdviceRepository(_p("verticals.db"))
    verticals = VerticalBrains(knowledge_domain, advice_repo, reasoning=reasoning, bus=bus)

    # --- Scheduler/Lifecycle (Faz 4): otonom döngü motoru; DETERMİNİSTİK tick (duvar-saati thread YOK) ---
    schedule_repo = ScheduleRepository(_p("scheduler.db"))
    scheduler = SchedulerDomain(schedule_repo, bus=bus)
    scheduler.reap_zombies("owner")                     # başlangıçta önceki çökmüş süreçten kalanı toparla
    # Doğuştan öz-bakım işleri (yalnız tick çağrılınca çalışır — otomatik arka-plan yok):
    scheduler.register_job("owner", "memory_consolidation",
                           lambda: memory.consolidate("Memory"), interval=10)
    scheduler.register_job("owner", "executive_review",
                           lambda: executive.review("periodic"), interval=20)
    scheduler.register_job("owner", "learning_consolidation",
                           lambda: learning.consolidate("Learning"), interval=15)

    # --- Observability (Faz 4): EventBus'ı PASİF dinler → metrik/sağlık/telemetri (tüm domainleri kapsar) ---
    observability_repo = TelemetryRepository(_p("observability.db"))
    observability = ObservabilityDomain(observability_repo, bus=bus)

    # Madde 27: EventBus abone hataları artık sessizce yutulmaz → observability sayacına akar (görünür).
    def _bus_subscriber_error(_ev, _handler, _exc):
        try:
            observability.incr("owner", "platform.bus_subscriber_errors")
        except Exception:  # noqa: BLE001 — son çare; hata dinleyicisi bus'ı kıramaz
            pass
    bus.set_error_handler(_bus_subscriber_error)

    # --- Policy (Faz 4): deterministik Policy Decision Point; anayasal innate politikalarla doğar ---
    policy_repo = PolicyRepository(_p("policy.db"))
    policy = PolicyDomain(policy_repo, bus=bus)

    # --- Security (Faz 4): merkezî RBAC + güvenlik denetimi + secret redaksiyonu; doğuştan kimlikler ---
    security_repo = SecurityRepository(_p("security.db"))
    security = SecurityDomain(security_repo, bus=bus)

    # --- Capability Management (Constitution Faz 2): CapabilityRegistry'yi sarar (maturity/§7, seçim) ---
    capability_repo = CapabilityRepository(_p("capabilities.db"))
    capability_management = CapabilityManagementDomain(capabilities, capability_repo, bus=bus)
    capability_management.restore("owner")              # kalıcı maturity override'larını geri uygula

    # --- MCP Management (Constitution Faz 2 #9): MCPHub'ı sarar (trust yaşam-döngüsü + kalıcı kayıt) ---
    mcp_repo = MCPRepository(_p("mcp.db"))
    mcp_management = MCPManagementDomain(mcp_hub, mcp_repo, capabilities=capabilities,
                                         orchestrator=orchestrator, meta=meta, bus=bus)
    mcp_management.restore("owner")                     # kalıcı MCP sunucu kaydını hub'a geri yükle

    # --- Audit & Compliance (Constitution Faz 2 #12): değişmez audit ledger + uyum kaydı (Madde 36/§10) ---
    audit_repo = AuditRepository(_p("audit.db"))
    audit = AuditComplianceDomain(audit_repo, bus=bus)

    # --- Resource & Runtime (Constitution Faz 2 #13): Resource Awareness (Madde 30) ---
    def _resource_probe() -> dict:
        info = discover_hardware()                      # GERÇEK donanım (uydurma yok)
        try:
            import shutil
            du = shutil.disk_usage(workspace)
            info["disk_free_gb"] = round(du.free / 1e9, 1)
            info["disk_total_gb"] = round(du.total / 1e9, 1)
        except Exception:  # noqa: BLE001 — disk okunamazsa alan atlanır (dürüst)
            pass
        return info
    resource_repo = ResourceRepository(_p("resources.db"))
    resources = ResourceRuntimeDomain(resource_repo, probe=_resource_probe, bus=bus)

    # --- Software Engineering (Faz 3 #17): deterministik statik analiz + Anayasa quality gate ---
    software_repo = SoftwareRepository(_p("software.db"))
    software_engineering = SoftwareEngineeringDomain(software_repo, bus=bus)

    # --- Research (Faz 3 #18): deterministik soruşturma + sentez (corroboration/doğrulama) ---
    research_repo = ResearchRepository(_p("research.db"))
    research = ResearchDomain(research_repo, bus=bus)

    # --- Document Intelligence (Faz 3 #19): deterministik analiz + sınıflandırma + extractive özet ---
    document_repo = DocumentRepository(_p("documents.db"))
    document_intelligence = DocumentIntelligenceDomain(document_repo, bus=bus)

    # --- Data Analytics (Faz 3 #20): deterministik tablo analitiği (stdlib) ---
    data_repo = DataRepository(_p("data.db"))
    data_analytics = DataAnalyticsDomain(data_repo, bus=bus)

    # --- Business & Operations (Faz 3 #21): deterministik süreç + iş kuralı motoru ---
    business_repo = BusinessRepository(_p("business.db"))
    business_operations = BusinessOperationsDomain(business_repo, bus=bus)

    # --- Finance Operations (Faz 3 #22): deterministik defter + Financial Rule (Madde 4) ---
    finance_repo = FinanceRepository(_p("finance.db"))
    finance = FinanceDomain(finance_repo, bus=bus)

    # --- Sales & CRM (Faz 3 #23): deterministik pipeline + lead qualification ---
    sales_repo = SalesRepository(_p("sales.db"))
    sales = SalesCRMDomain(sales_repo, bus=bus)

    # --- Marketing & Growth (Faz 3 #24): deterministik kampanya KPI (CTR/CVR/CPA/ROAS) ---
    marketing_repo = MarketingRepository(_p("marketing.db"))
    marketing = MarketingDomain(marketing_repo, bus=bus)

    # --- Customer Success (Faz 3 #25): deterministik health score + churn-risk ---
    customer_repo = CustomerRepository(_p("customer.db"))
    customer_success = CustomerSuccessDomain(customer_repo, bus=bus)

    # --- Vision (Faz 4 #26): deterministik orkestrasyon; gerçek analiz connector'a delege (yoksa no_connector) ---
    vision_repo = VisionRepository(_p("vision.db"))
    vision = VisionDomain(vision_repo, bus=bus)

    # --- Voice (Faz 4 #27): deterministik orkestrasyon; STT/TTS connector'a delege (yoksa no_connector) ---
    voice_repo = VoiceRepository(_p("voice.db"))
    voice = VoiceDomain(voice_repo, bus=bus)

    # --- Media Generation (Faz 4 #28): deterministik orkestrasyon; üretim modeli adapter'a delege ---
    media_repo = MediaRepository(_p("media.db"))
    media = MediaGenerationDomain(media_repo, bus=bus)

    # --- Web Intelligence (Faz 4 #29): deterministik orkestrasyon + allowlist; ağ adapter'a delege ---
    web_repo = WebRepository(_p("web.db"))
    web = WebIntelligenceDomain(web_repo, bus=bus)

    # --- Device & Native Integration (Faz 4 #30): orkestrasyon + risk-onay; OS/donanım adapter'a delege ---
    device_repo = DeviceRepository(_p("device.db"))
    device = DeviceNativeDomain(device_repo, bus=bus)

    # --- IoT (Faz 4 #31): thing registry + telemetri/eşik-uyarı + aktüatör risk-onay; protokol adapter'a delege ---
    iot_repo = IoTRepository(_p("iot.db"))
    iot = IoTDomain(iot_repo, bus=bus)

    # --- Model Management (Faz 5 #32): registry + yaşam-döngüsü + DETERMİNİSTİK seçim; provider adapter'a delege ---
    model_repo = ModelRepository(_p("models.db"))
    model_management = ModelManagementDomain(model_repo, bus=bus)

    # --- Multi-Agent (Faz 5 #33): agent registry + DETERMİNİSTİK görev atama + koordinasyon; executor adapter'a delege ---
    multi_agent_repo = MultiAgentRepository(_p("multi_agent.db"))
    multi_agent = MultiAgentDomain(multi_agent_repo, bus=bus)

    # --- Marketplace/Ecosystem (Faz 5 #34): listing registry + DETERMİNİSTİK uyumluluk/allowlist + Madde 24 kurulum onayı ---
    marketplace_repo = MarketplaceRepository(_p("marketplace.db"))
    marketplace_domain = MarketplaceDomain(marketplace_repo, bus=bus)

    # --- Knowledge Marketplace (Faz 5 #35): bilgi paketi registry + DETERMİNİSTİK lisans/allowlist + provenance + Madde 24 import onayı ---
    knowledge_market_repo = KnowledgeMarketRepository(_p("knowledge_market.db"))
    knowledge_marketplace = KnowledgeMarketplaceDomain(knowledge_market_repo, bus=bus)

    # --- Federation (Faz 5 #36): peer registry + DETERMİNİSTİK host allowlist/scope + Madde 24 paylaşım onayı (egemenlik) ---
    federation_repo = FederationRepository(_p("federation.db"))
    federation = FederationDomain(federation_repo, bus=bus)

    # --- Distributed Execution (Faz 5 #37): worker node registry + DETERMİNİSTİK dağıtım/idempotency + Madde 24 onay ---
    dist_exec_repo = DistExecRepository(_p("dist_exec.db"))
    distributed_execution = DistributedExecutionDomain(dist_exec_repo, bus=bus)

    # --- Autonomous Operations (Faz 5 #38): kural registry + deterministik tetik + ÖNERİ (Madde 24); kapalı-döngü opt-in ---
    auto_ops_repo = AutoOpsRepository(_p("autonomous_ops.db"))
    autonomous_operations = AutonomousOperationsDomain(auto_ops_repo, bus=bus)

    # --- Simulation & Digital Twin (Faz 5 #39): twin registry + deterministik what-if simülasyon; sim ≠ gerçeklik (Madde 24 yansıtma) ---
    digital_twin_repo = DigitalTwinRepository(_p("digital_twin.db"))
    digital_twin = DigitalTwinDomain(digital_twin_repo, bus=bus)

    # --- Extension SDK (Faz 5 #40, SON ana domain): uzantı manifest + DETERMİNİSTİK izin-scope doğrulama + Madde 24 etkinleştirme ---
    extension_repo = ExtensionRepository(_p("extensions.db"))
    extension_sdk = ExtensionSDKDomain(extension_repo, bus=bus)

    # --- Presentation Domain: sunum mantığı (konuşma/podcast/video/webinar/... senaryo+akış+slayt). Dış sistemi
    #     BİLMEZ; yalnız CapabilityIntent üretir. Yürütmeye Executive karar verir (ConnectorManager Executive'te). ---
    presentation_repo = PresentationRepository(_p("presentation.db"))
    presentation = PresentationDomain(presentation_repo, bus=bus)

    # --- Conversation Domain: gerçek zamanlı etkileşim mantığı (mesaj/moderasyon/öncelik/sıra). Platformu BİLMEZ;
    #     yalnız CapabilityIntent üretir. Moderasyon KARAR VERMEZ (Executive'e öneri). ---
    live_conversation_repo = LiveConversationRepository(_p("conversation.db"))
    conversation = ConversationDomain(live_conversation_repo, bus=bus)

    # --- Capability Adapter Layer (Connector): Executive→Manager→[AI/Comm/Productivity/System/Media]. Connector'lar
    #     runtime.connectors.register(...) ile bağlanır; hiçbiri yoksa dürüst connector_unavailable (çökmez). ---
    connector_registry = ConnectorRegistry()
    connectors = ConnectorManager(connector_registry, bus=bus)
    advisor = Advisor(connectors)

    # --- Kalıcılık (Area 3): önceki öğrenilen bilgi + metrikleri geri yükle ---
    kv = JsonKVStore(_p("ecosystem.db"))
    knowledge.import_items(kv.get("knowledge_learned", []))          # eski kv yolu (geriye-uyum/migrasyon)
    knowledge.import_items([i.to_dict() for i in knowledge_repo.all()])  # write-through kalıcı depo (yetkili)
    meta.import_metrics(kv.get("meta_metrics", {}))

    mio = MIORuntime(
        kv=kv,
        state=state, cognitive=cognitive, knowledge=knowledge, brains=brains,
        capabilities=capabilities, gateway=gateway, orchestrator=orchestrator, governance=governance,
        goals=goals, review=review, cognitive_identity=cognitive_identity, self_awareness=self_awareness,
        brain_runtime=brain_runtime, discovery=discovery, meta=meta, executive=executive,
        memory=memory, knowledge_domain=knowledge_domain, reasoning=reasoning, planning=planning,
        learning=learning, goal_management=goal_management, communication=communication,
        execution=execution, perception=perception, verticals=verticals, scheduler=scheduler,
        observability_domain=observability, policy=policy, security=security,
        capability_management=capability_management, mcp_management=mcp_management, audit=audit,
        resources=resources, software_engineering=software_engineering, research=research,
        document_intelligence=document_intelligence, data_analytics=data_analytics,
        business_operations=business_operations, finance=finance, sales=sales, marketing=marketing,
        customer_success=customer_success, vision=vision, voice=voice, media=media, web=web,
        device=device, iot=iot, model_management=model_management, multi_agent=multi_agent,
        marketplace_domain=marketplace_domain, knowledge_marketplace=knowledge_marketplace,
        federation=federation, distributed_execution=distributed_execution,
        autonomous_operations=autonomous_operations, digital_twin=digital_twin,
        extension_sdk=extension_sdk, presentation=presentation, conversation=conversation,
        connector_registry=connector_registry, connectors=connectors,
        advisor=advisor, mcp_hub=mcp_hub,
        bus=bus, versions=versions, marketplace=marketplace, recommendation=recommendation,
        workspace=workspace, config=cfg,
        policy_profiles=policy_profiles, store=store, diagnostics=diagnostics, analytics=analytics,
        birth_summary=birth_summary,
        stores=[exec_store, belief_store, goal_store, audit_store, memory_repo, knowledge_repo,
                reasoning_repo, plan_repo, learning_repo, conversation_repo, execution_repo,
                perception_repo, advice_repo, schedule_repo, observability_repo, policy_repo,
                security_repo, capability_repo, mcp_repo, audit_repo, resource_repo, software_repo,
                research_repo, document_repo, data_repo, business_repo, finance_repo, sales_repo,
                marketing_repo, customer_repo, vision_repo, voice_repo, media_repo, web_repo, device_repo,
                iot_repo, model_repo, multi_agent_repo, marketplace_repo, knowledge_market_repo,
                federation_repo, dist_exec_repo, auto_ops_repo, digital_twin_repo, extension_repo,
                presentation_repo, live_conversation_repo],
        closeables=[c for c in (mcp_client,) if c is not None],
    )

    # --- Opsiyonel: MIO açılışta çalışacağı yerel çıkarım ortamını KENDİSİ hazırlar (varsayılan KAPALI) ---
    # config'ten okunur (tek kaynak) — .env'deki MIO_AUTO_INFERENCE artık ETKİLİ (kök neden düzeltmesi).
    _auto = prepare_inference if prepare_inference is not None else cfg.get_bool("MIO_AUTO_INFERENCE", False)
    if _auto:
        try:
            status = mio.local_inference.ensure_ready()   # güvenli işler otomatik; silme/kurulum onay bekler
            mio.inference_status = status                 # açılış sonucu (mio.inference_status)
            bus.publish("inference.prepared", {"ready": status.get("ready"),
                        "model": status.get("selected_model"), "message": status.get("message")})
        except Exception as exc:  # noqa: BLE001 — hazırlık hatası boot'u ÇÖKERTMEZ (dürüst), görünür kalır
            mio.inference_status = {"ready": False, "error": str(exc)[:200]}

    return mio
