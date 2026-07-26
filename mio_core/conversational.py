"""MIO Core · Conversational Orchestrator — doğal dil (Türkçe) → Intent → Executive → mevcut domain işlemleri.

**Bu YENİ bir mimari DEĞİL.** Mevcut Application Service Layer (appservice) üzerine bir **orkestrasyon katmanı**dır:
kullanıcının doğal dil isteğini DETERMİNİSTİK bir intent'e çevirir ve mevcut appservice operasyonuna yönlendirir.
İş mantığı yoktur (domainlerde/Executive'te). LLM (Advisor) yalnız **yorumlama/ifade** için danışmandır — karar
verici DEĞİL; yönlendirme deterministiktir (Anayasa Madde 1/3). İkinci bir workflow/task/memory/registry
oluşturmaz — hepsini mevcut sistemler üzerinden yürütür (ürün bütünlüğü).

Pipeline: Kullanıcı → Intent Analizi → Executive (deterministik yönlendirme) → mevcut appservice op → Sonuç →
CEO yanıtı (Türkçe). Konuşma bağlamı (referanslar: 'bunu durdur', 'devam et') korunur."""

from __future__ import annotations

import re
from typing import Any, Optional

from mio_core import appservice


# Türkçe diacritic → ASCII (kullanıcı 'yardım' ya da 'yardim' yazabilir; ikisi de eşleşmeli).
_TR_MAP = str.maketrans("ıİşŞğĞüÜöÖçÇâîû", "iisSgGuUoOcCaiu")


def _normalize(text: str) -> str:
    """Küçük harf + Türkçe diacritic soyma (deterministik, diacritic-duyarsız eşleşme için)."""
    return (text or "").translate(_TR_MAP).lower()


# Deterministik niyet kalıpları — ASCII-normalize + KÖK/ÖNEK eşleşme (kapanış \b YOK; Türkçe sondan-eklemeli:
# 'mesaj' → 'mesajlari', 'is akis' → 'is akislari'). Sıra ÖNEMLİ: özelden genele (ilk eşleşen kazanır).
_INTENT_PATTERNS = [
    ("greeting", r"\b(merhaba|selam|gunaydin|hey|hello|iyi aksam)"),
    ("ceo", r"\b(pano|yonetim panosu|dashboard|genel bakis|ceo|devret|delege|butun resmi|butun resim)"),
    ("business", r"\b(isletme|is yeri|sirket kur|yeni sirket|workspace|departman kur|business)"),
    ("diagnose", r"\b(saglik|saglig|tani|teshis|kontrol et|diagnose|health|sorun var)"),
    ("hardware", r"\b(donanim|gpu|cuda|vram|hardware|islemci|ekran kart)"),
    ("models", r"\b(model|llm|ollama|yapay zeka)"),
    ("present", r"\b(sunum|podcast|konus|yayin|video|slayt|anlat|seslendir|present|webinar|canli)"),
    ("conversation", r"\b(mesaj|sohbet|izleyici|moderasyon|spam|yorum|chat)"),
    ("workflow", r"\b(is akis|workflow|gorev graf|pipeline|gorevler|dag)"),
    ("connect", r"\b(baglan|connector|entegrasyon|servis bagla|connect|smtp|discord)"),
    ("mcp", r"\b(mcp|sunucu ekle)"),
    ("config", r"\b(ayar|yapilandir|config)"),
    ("status", r"\b(durum|ne yapiyorsun|sirket|nasil gidiyor|ozet|rapor|bugun ne|calisiyorsun|status)"),
    ("help", r"\b(yardim|ne yapabilir|neler yapabilir|komut|yetenek|help|kullanim|nasil kullan)"),
]

# Referans (bağlam) sözcükleri — önceki sonuca gönderme (konuşma hafızası).
_REFERENCE = re.compile(r"\b(bunu|bunlari|onu|sunu|devam|ayni|onceki|geri don|dur|durdur|iptal)\b")


class ConversationalOrchestrator:
    """Doğal dil → mevcut appservice işlemleri. Konuşma bağlamı tutar. İş mantığı YOK (orkestrasyon)."""

    def __init__(self, mio) -> None:
        self._mio = mio
        self._context: dict[str, Any] = {"history": [], "last_intent": None, "last_data": None}

    # ------------------------------------------------------------------ #
    def handle(self, text: str, *, actor: str = "owner") -> dict[str, Any]:
        """Doğal dil isteğini işler. {intent, response, data, suggestion} döner. ASLA raise etmez."""
        text = (text or "").strip()
        if not text:
            return self._resp("empty", "Bir şey yazın; örneğin 'durum nedir' ya da 'yardım'.", None)
        intent = self._classify(text)
        try:
            result = self._route(intent, text, actor)
        except Exception as exc:  # noqa: BLE001 — orkestrasyon hatası kullanıcıya dönüşür, çökmez
            result = self._resp(intent, f"İşlem sırasında bir sorun oldu: {type(exc).__name__}: {exc}", None)
        self._context["history"].append({"text": text, "intent": intent})
        self._context["last_intent"] = intent
        self._context["last_data"] = result.get("data")
        return result

    def context(self) -> dict[str, Any]:
        return {"turns": len(self._context["history"]), "last_intent": self._context["last_intent"],
                "recent": self._context["history"][-5:]}

    # ------------------------------------------------------------------ #
    def _classify(self, text: str) -> str:
        low = _normalize(text)                        # diacritic-duyarsız (yardım == yardim)
        # bağlam referansı + önceki niyet varsa onu sürdür ('devam et', 'bunu durdur')
        if _REFERENCE.search(low) and self._context["last_intent"]:
            return self._context["last_intent"]
        for kind, pat in _INTENT_PATTERNS:
            if re.search(pat, low):
                return kind
        return "unknown"

    def _route(self, intent: str, text: str, actor: str) -> dict[str, Any]:
        mio = self._mio
        if intent == "greeting":
            exe = appservice.executive_summary(mio)
            return self._resp(intent, f"Merhaba. Ben MIO Executive. Sistem güveni: "
                              f"{exe['system_confidence']} ({exe['executive_score']}/100). "
                              f"Ne yapmak istersiniz? 'durum', 'sunum', 'iş akışı' diyebilirsiniz.", exe)
        if intent == "help":
            caps = appservice.capabilities_catalog(mio)
            doms = appservice.list_domains(mio)
            msg = (f"Ben {len(doms)} yetenek alanını yöneten bir işletim sistemiyim. Doğal dille konuşabilirsiniz:\n"
                   "  • 'durum nedir' — özet/sağlık\n  • 'donanım' — GPU/model durumu\n"
                   "  • 'sunum hazırla' — konuşma/podcast/yayın\n  • 'mesajları göster' — canlı sohbet\n"
                   "  • 'iş akışları' — görev grafı\n  • 'bağlan' — dış servisler\n"
                   "Gelişmiş: 'domains', 'call <domain> <op>', 'workflow', 'present', 'chat' komutları da çalışır.")
            return self._resp(intent, msg, {"domains": len(doms), "capabilities": len(caps["capabilities"])})
        if intent == "status":
            exe = appservice.executive_summary(mio)
            actions = "; ".join(exe.get("recommended_actions", [])[:2]) or "bekleyen kritik iş yok"
            return self._resp(intent, f"Sistem güveni {exe['system_confidence']} ({exe['executive_score']}/100). "
                              f"{exe['domains']} alan, {exe['connectors']} bağlı servis. Öneri: {actions}.", exe)
        if intent == "diagnose":
            d = appservice.diagnose(mio)
            attn = [c["component"] for c in d["components"] if c["status"] != "ok"]
            tail = f" Dikkat: {', '.join(attn)}." if attn else " Tüm bileşenler sağlıklı."
            return self._resp(intent, f"Executive Score {d['score']}/100 — {d['verdict']}.{tail}", d)
        if intent == "hardware":
            hw = appservice.hardware_report(mio)
            g = hw["gpus"][0]["name"] if hw.get("gpus") else "GPU yok"
            ol = "çalışıyor" if hw.get("ollama", {}).get("reachable") else "kapalı"
            warn = (" Uyarı: " + hw["warnings"][0]) if hw.get("warnings") else ""
            return self._resp(intent, f"{g}, Ollama {ol}.{warn}", hw)
        if intent == "models":
            m = appservice.models_overview(mio)
            return self._resp(intent, f"Önerilen model: {m.get('recommended') or 'yok'}. "
                              f"Kurulu: {len(m.get('installed', []))}, VRAM boş: {m.get('vram_free_mb', 0)} MB.", m)
        if intent == "present":
            lst = appservice.presentation_list(mio)
            return self._resp(intent, f"{len(lst)} sunum senaryosu var. Yeni oluşturmak için: "
                              "'present outline <başlık> [\"madde1\",\"madde2\"]'. Yürütmek için 'present deliver <id>'.",
                              {"scripts": lst})
        if intent == "conversation":
            q = appservice.conversation_queue(mio)
            s = appservice.conversation_summary(mio)
            return self._resp(intent, f"{s['pending']} cevap bekleyen mesaj (toplam {s['messages']}). "
                              f"İşaretli/moderasyon: {s['flagged']}.", {"queue": q, "summary": s})
        if intent == "workflow":
            wl = appservice.workflow_list(mio)
            running = sum(1 for w in wl if w["status"] == "running")
            return self._resp(intent, f"{len(wl)} iş akışı ({running} çalışıyor). Yürütmek için "
                              "'workflow run <id>'. Yeni: 'workflow create <ad> <json>'.", {"workflows": wl})
        if intent == "connect":
            summary = appservice.connect_env(mio)
            reg = ", ".join(summary.get("registered", [])) or "yok"
            return self._resp(intent, f"Bağlanan servisler: {reg}. Yapılandırma için .env dosyanızı düzenleyin.",
                              summary)
        if intent == "mcp":
            servers = appservice.mcp_list(mio)
            return self._resp(intent, f"{len(servers)} MCP sunucusu kayıtlı. Eklemek için "
                              "'mcp install <ad>'. Durum: 'mcp status'.", {"servers": servers})
        if intent == "config":
            cfg = appservice.config_diagnostics(mio)
            return self._resp(intent, f"Yapılandırma yüklendi (.env {'var' if cfg['env_file_loaded'] else 'yok'}). "
                              f"LLM: {'açık' if cfg.get('llm_enabled') else 'kapalı'}, "
                              f"Ollama: {'erişilebilir' if cfg.get('ollama_reachable') else 'kapalı'}.", cfg)
        if intent == "ceo":
            rep = appservice.ceo_report(mio)
            g, a = rep["active_goals"], rep["agents"]["total"]
            t = rep["tasks"]["total"]
            return self._resp(intent, f"Yönetim panosu — güven {rep['system_confidence']} "
                              f"({rep['executive_score']}/100). {rep['businesses']['total']} işletme, {g} aktif "
                              f"hedef, {rep['plans']['total']} plan, {a} agent, {t} görev. Yeni hedef için "
                              "'ceo direct <hedef>', devretmek için 'ceo delegate <plan_id>'.", rep)
        if intent == "business":
            bl = appservice.business_list(mio)
            if bl:
                names = ", ".join(b["name"] for b in bl[:5])
                return self._resp(intent, f"{len(bl)} işletmeniz var: {names}. Yeni oluşturmak için "
                                  "'business create <ad> <tip>'. Detay: 'business info <ad>'.", {"businesses": bl})
            return self._resp(intent, "Henüz işletmeniz yok. Oluşturmak için: 'business create <ad> <tip>' "
                              "(tipler: personal/marketing_agency/ecommerce/factory/restaurant/saas).",
                              {"businesses": []})
        # UNKNOWN → LLM danışmana sor (varsa; DANIŞMAN, karar vermez) ya da öner
        return self._unknown(text, actor)

    def _unknown(self, text: str, actor: str) -> dict[str, Any]:
        """Niyet çözülemedi. LLM danışman varsa yorumlaması için sorulur (karar VERMEZ); yoksa öneri."""
        if self._mio.advisor.available():
            adv = self._mio.advisor.ask(
                "Kullanıcının MIO işletim sistemine isteği: '" + text + "'. Kısa, Türkçe, tek cümlede hangi "
                "eylemi kastettiğini açıkla (durum/sunum/sohbet/iş akışı/donanım/bağlan).", actor=actor)
            if adv.get("ok"):
                hint = adv.get("result", {}).get("advice", "")[:200]
                return self._resp("unknown", f"Tam anlayamadım. Danışman yorumu: {hint} "
                                  "(Netleştirmek için 'yardım' diyebilirsiniz.)", {"advisor": hint})
        return self._resp("unknown", "Bunu tam anlayamadım. 'yardım' ile neler yapabileceğimi görebilir "
                          "ya da 'durum', 'sunum', 'iş akışı', 'donanım' gibi konularda konuşabilirsiniz.", None)

    @staticmethod
    def _resp(intent: str, response: str, data: Any) -> dict[str, Any]:
        return {"intent": intent, "response": response, "data": data}


__all__ = ["ConversationalOrchestrator"]
