"""MIO Core · MCP Store + Self Diagnostics + Capability Analytics (Öncelik 6, 8, 9), LLM-BAĞIMSIZ.

Hepsi mevcut veriden (CapabilityRegistry + MetaMCPManager + VersionManager) TÜRETİR — yeni state tutmaz,
çekirdeği büyütmez. MIO kendi ekosistemini izler, sağlığını analiz eder, kullanımını öğrenir."""

from __future__ import annotations

from typing import Optional

from mio_core.capability import CapabilityRegistry
from mio_core.events import Ev
from mio_core.execution.meta_mcp import MetaMCPManager

__all__ = ["MCPStore", "SelfDiagnostics", "CapabilityAnalytics"]


class MCPStore:
    """Kurulu MCP'lerin GERÇEK-ZAMANLI durumu (provenance/sunucu bazında)."""

    def __init__(self, capabilities: CapabilityRegistry, meta: MetaMCPManager, *, versions=None) -> None:
        self._caps = capabilities
        self._meta = meta
        self._versions = versions

    def state(self) -> list[dict]:
        by_server: dict[str, list] = {}
        for c in self._caps.list():
            if c.source == "mcp":
                by_server.setdefault(c.provenance or "?", []).append(c)
        out = []
        for server, caps in by_server.items():
            trusts = [self._meta.trust_score(c.name) for c in caps]
            calls = sum(self._meta.metrics(c.name).calls for c in caps)
            errors = sum(self._meta.metrics(c.name).errors for c in caps)
            healths = [self._meta.health_state(c.name) for c in caps]
            vi = self._versions.get(server) if self._versions else None
            out.append({
                "server": server, "capability_count": len(caps),
                "connected": sum(1 for c in caps if c.connected),
                "trust_avg": round(sum(trusts) / len(trusts)) if trusts else 0,
                "health": "down" if all(h == "down" for h in healths) else
                          ("degraded" if any(h in ("down", "degraded") for h in healths) else "healthy"),
                "calls": calls, "error_rate": round(errors / calls, 3) if calls else 0.0,
                "version": vi.to_dict() if vi else None,
            })
        return sorted(out, key=lambda d: d["server"])


class SelfDiagnostics:
    """MIO kendi sağlığını analiz eder (unused/dead/outdated/slow/most-error)."""

    def __init__(self, capabilities: CapabilityRegistry, meta: MetaMCPManager, *,
                 versions=None, bus=None) -> None:
        self._caps = capabilities
        self._meta = meta
        self._versions = versions
        self._bus = bus

    def run(self) -> dict:
        caps = self._caps.list()
        connected = [c for c in caps if c.connected]
        used = [(c, self._meta.metrics(c.name)) for c in caps]
        unused = [c.name for c, m in used if c.connected and m.calls == 0]
        dead = [c.name for c, m in used if (m.successes + m.errors) >= 3 and (m.error_rate or 0) == 1.0]
        errored = sorted(((m.errors, c.name) for c, m in used if m.errors), reverse=True)
        slow = sorted(((m.avg_latency_ms or 0, c.name) for c, m in used if m.avg_latency_ms), reverse=True)
        trusts = [self._meta.trust_score(c.name) for c in connected]
        report = {
            "total_capabilities": len(caps), "connected": len(connected),
            "disconnected": len(caps) - len(connected),
            "categories": len({c.category for c in connected}),
            "trust_avg": round(sum(trusts) / len(trusts)) if trusts else 0,
            "unused_capabilities": unused, "dead_capabilities": dead,
            "most_error": errored[0][1] if errored else None,
            "slowest": slow[0][1] if slow else None,
            "outdated": [v.name for v in self._versions.outdated()] if self._versions else [],
        }
        if self._bus:
            self._bus.publish(Ev.DIAGNOSTIC, report)
        return report


class CapabilityAnalytics:
    """Log değil GERÇEK analiz: en çok/hızlı/güvenilir/pahalı yetenek + başarı oranı."""

    def __init__(self, capabilities: CapabilityRegistry, meta: MetaMCPManager, *, bus=None) -> None:
        self._caps = capabilities
        self._meta = meta
        self._bus = bus

    def report(self) -> dict:
        rows = [(c, self._meta.metrics(c.name)) for c in self._caps.list()]
        used = [(c, m) for c, m in rows if m.calls > 0]

        def _top(key, reverse=True):
            cand = [(key(c, m), c.name) for c, m in used if key(c, m) is not None]
            return max(cand)[1] if (cand and reverse) else (min(cand)[1] if cand else None)

        total_calls = sum(m.calls for _, m in used)
        total_succ = sum(m.successes for _, m in used)
        report = {
            "total_calls": total_calls,
            "overall_success_rate": round(total_succ / max(1, sum(m.successes + m.errors for _, m in used)), 3)
                                    if used else None,
            "most_used": _top(lambda c, m: m.calls),
            "fastest": _top(lambda c, m: -(m.avg_latency_ms or 10 ** 9)),
            "slowest": _top(lambda c, m: (m.avg_latency_ms or 0)),
            "most_reliable": _top(lambda c, m: (m.success_rate if m.success_rate is not None else -1)),
            "most_expensive": _top(lambda c, m: (1 if c.incurs_cost else 0, m.calls)),
        }
        if self._bus:
            self._bus.publish(Ev.ANALYTICS, report)
        return report
