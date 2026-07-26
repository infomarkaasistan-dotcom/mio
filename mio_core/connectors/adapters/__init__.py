"""MIO Core · Connector adapters — GERÇEK dış sistem connector'ları (stdlib-only, enjekte-edilebilir transport).

4 kategori: System (filesystem/shell/git) · Communication (smtp/webhook) · AI (ollama/openai-uyumlu) ·
Productivity (caldav). Her biri `CallableConnector` fabrikasıdır → `manager.register(...)`. `register_from_env`
env'e göre yapılandırılmışları bağlar. Gerçek dış sistem erişimi ADAPTER'da; çekirdek framework-bağımsız kalır."""

from .bootstrap import register_from_env
from .caldav import caldav_connector
from .filesystem import filesystem_connector
from .git import git_connector
from .ollama import ollama_connector
from .openai_compat import openai_connector
from .shell import shell_connector
from .smtp import smtp_connector
from .webhook import webhook_connector

__all__ = [
    "register_from_env",
    "filesystem_connector", "shell_connector", "git_connector",
    "smtp_connector", "webhook_connector",
    "ollama_connector", "openai_connector",
    "caldav_connector",
]
