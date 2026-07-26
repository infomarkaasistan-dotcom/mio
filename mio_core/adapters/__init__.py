"""MIO Core · Adaptörler — GERÇEK dünya kenarı (Ollama, donanım, MCP...).

Çekirdek (mio_core.executive/…) SAF ve stdlib-only kalır. Bu paket, çekirdeğin bekleyen arayüzlerini
(ModelProvider, MCPClient, keşif) GERÇEK sistemlere bağlar. Bağımlılıklar burada tutulur (şu an yalnız
stdlib urllib). Bir dış sistem erişilemezse adaptör dürüstçe başarısız olur; çekirdek çalışmaya devam eder.
"""

from .hardware import discover_hardware
from .native import (
    ReasoningExecutor,
    ShellExecutor,
    reasoning_capability,
    register_native,
    shell_capability,
)
from .mcp_client import MCPServerConfig, StdioMCPClient, StdioTransport, infer_risk
from .ollama import OllamaProvider, wire_ollama
from .reasoning import ReasoningSuite, reasoning_suite_capability, register_reasoning
from .transport import HttpTransport, TransportRegistry, build_transport

__all__ = [
    "OllamaProvider", "wire_ollama", "discover_hardware",
    "MCPServerConfig", "StdioMCPClient", "StdioTransport", "infer_risk",
    "HttpTransport", "TransportRegistry", "build_transport",
    "ReasoningExecutor", "ShellExecutor", "reasoning_capability", "register_native", "shell_capability",
    "ReasoningSuite", "reasoning_suite_capability", "register_reasoning",
]
