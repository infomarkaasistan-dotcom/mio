"""MIO Core · X4 Model Gateway — LLM = Tool Orchestrator'a bağlı BİR ARAÇ (ADR-0002), çekirdek LLM-BAĞIMSIZ.

Çekirdek ilke: LLM hiçbir zaman beyin/karar-verici değildir; gerektiğinde çağrılan, DEĞİŞTİRİLEBİLİR bir
danışmandır. Model Gateway bir `ToolExecutor`'dur: "llm" yeteneği olarak Tool Orchestrator'a bağlanır →
hiçbir Brain LLM'i doğrudan çağırmaz, hepsi orchestrator üzerinden geçer (izin/governance/audit dahil).

Sağlayıcılar (Ollama/OpenAI/…) enjekte edilen `ModelProvider` adaptörleridir. Hiç sağlayıcı yoksa "llm"
yeteneği bağlı değildir (dürüst) ve MIO'nun deterministik çekirdeği LLM olmadan çalışmaya devam eder.
Routing çoklu-model + FAILOVER'dır; MIO hiçbir tek modele bağımlı değildir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol

from mio_core.capability import Capability, RiskLevel

__all__ = ["ModelSpec", "ModelProvider", "GatewayResult", "GatewayError",
           "ModelGateway", "llm_capability"]


@dataclass
class ModelSpec:
    name: str
    provider: str
    quality: float = 0.5
    speed: float = 0.5
    cost: float = 0.0            # USD / 1K token (0 = yerel/ücretsiz)
    context: int = 8192
    local: bool = False
    vision: bool = False
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "provider": self.provider, "quality": self.quality,
                "speed": self.speed, "cost": self.cost, "context": self.context,
                "local": self.local, "vision": self.vision, "available": self.available}


class ModelProvider(Protocol):
    """GERÇEK sağlayıcı adaptörü. Başarıda metin döner, başarısızlıkta EXCEPTION fırlatır."""
    def generate(self, model: ModelSpec, prompt: str, system: Optional[str], max_tokens: int) -> str: ...


@dataclass
class GatewayResult:
    text: str
    model: str
    provider: str
    attempts: int

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "model": self.model, "provider": self.provider, "attempts": self.attempts}


class GatewayError(Exception):
    pass


class ModelGateway:
    """Çoklu-model routing + FAILOVER. `ToolExecutor` olarak orchestrator'a "llm" yeteneğiyle bağlanır."""

    def __init__(self) -> None:
        self._models: list[ModelSpec] = []
        self._providers: dict[str, ModelProvider] = {}

    def register_model(self, spec: ModelSpec, provider: ModelProvider) -> ModelSpec:
        self._models.append(spec)
        self._providers[spec.provider] = provider
        return spec

    def connected_models(self) -> list[str]:
        return [m.name for m in self._models if m.available and m.provider in self._providers]

    # -- routing ------------------------------------------------------------ #
    def _candidates(self, priority: str, privacy: bool, min_quality: float) -> list[ModelSpec]:
        cands = [m for m in self._models
                 if m.available and m.provider in self._providers and m.quality >= min_quality
                 and (m.local if privacy else True)]

        def cost_norm(m: ModelSpec) -> float:
            return min(1.0, (m.cost or 0.0) / 0.01)

        if priority == "quality":
            cands.sort(key=lambda m: m.quality, reverse=True)
        elif priority == "speed":
            cands.sort(key=lambda m: m.speed, reverse=True)
        elif priority == "cost":
            cands.sort(key=lambda m: (m.cost, -m.quality))
        elif priority == "privacy":
            cands.sort(key=lambda m: (0 if m.local else 1, -m.quality))
        else:  # balanced
            cands.sort(key=lambda m: m.quality * 0.5 + m.speed * 0.3 + (1 - cost_norm(m)) * 0.2,
                       reverse=True)
        return cands

    def generate(self, prompt: str, *, system: Optional[str] = None, max_tokens: int = 500,
                 priority: str = "balanced", privacy: bool = False,
                 min_quality: float = 0.0) -> GatewayResult:
        cands = self._candidates(priority, privacy, min_quality)
        if not cands:
            raise GatewayError("Uygun/kullanılabilir model yok (Model Gateway).")
        attempts, last = 0, None
        for m in cands:
            provider = self._providers.get(m.provider)
            if provider is None:
                continue
            attempts += 1
            try:
                text = provider.generate(m, prompt, system, max_tokens)
                return GatewayResult(text=text, model=m.name, provider=m.provider, attempts=attempts)
            except Exception as e:  # noqa: BLE001 — failover için tüm hatalar yakalanır
                last = e
                continue
        raise GatewayError(f"Tüm modeller başarısız (failover tükendi): {last}")

    # -- ToolExecutor arayüzü (orchestrator'a "llm" yeteneği olarak bağlanır) -- #
    def execute(self, capability: Capability, action: str, args: dict[str, Any]) -> Any:
        if action != "generate":
            raise ValueError(f"Model Gateway desteklemiyor: '{action}' (yalnız 'generate').")
        r = self.generate(
            str(args.get("prompt", "")), system=args.get("system"),
            max_tokens=int(args.get("max_tokens", 500)), priority=str(args.get("priority", "balanced")),
            privacy=bool(args.get("privacy", False)), min_quality=float(args.get("min_quality", 0.0)))
        return r.to_dict()


def llm_capability() -> Capability:
    """"llm" yetenek tanımı — LLM bir ARAÇTIR (Tool Orchestrator üzerinden). connected, bir Model Gateway
    executor'ı register_executor ile bağlanınca True olur."""
    return Capability(
        name="llm", description="LLM danışman (metin üretimi/muhakeme) — Tool Orchestrator üzerinden",
        can_do=["metin üret", "özetle", "sınıflandır", "muhakeme et", "öneri sun"],
        cannot_do=["karar vermek (karar Executive'indir)", "sistemi doğrudan değiştirmek"],
        risk_level=RiskLevel.LOW, source="tool")
