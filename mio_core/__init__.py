"""MIO Executive OS — Core.

MIO bağımsız bir Executive Operating System'dir; OpenJarvis / MIO Beyin / MarkaAsistan yalnızca
referans kod tabanlarıdır. Bu paket MIO Core'un LLM-BAĞIMSIZ Executive çekirdeğini içerir.

Çekirdek ilkeler (bkz. mimari sözleşmeler):
- Executive ≠ Execution. Execution tek başına karar vermez.
- LLM asla beyin/karar-verici değildir; gerektiğinde çağrılan, değiştirilebilir bir danışmandır.
- MIO'nun kimliği, sürekliliği, hedefleri, hafızası ve karar mekanizmaları LLM'den bağımsız,
  deterministik ve kalıcıdır. Bu paket YALNIZCA standart kütüphane kullanır (model bağımlılığı yok).
"""

__all__ = ["executive"]
__version__ = "0.1.0"
