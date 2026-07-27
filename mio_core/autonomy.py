"""MIO Core · Otonom Görev Yürütücü (Mission Runner) — hedef → CEO böler → brain-destekli agent'lar → çıktı → rapor.

Kullanıcının vizyonu (Paperclip ilhamı, MIO kimliği): sisteme bir HEDEF verilir; CEO hedefi alt görevlere böler,
her alt göreve uygun bir **brain-destekli agent** atanır, agent'lar GERÇEK çıktı üretir (araştırma/plan/analiz/
içerik), sonuç raporlanır. "OpenJarvis'i örnek al ama OpenJarvis olma" — MIO'nun farkı: agent'ları **domain
brain'ler** (Marketing/Finance/Sales/Research...) destekler.

**ANAYASA (değişmez):** LLM KARAR VERMEZ (Madde 1) — brain'ler yalnız **çıktı/öneri** üretir (advisory). Executive
KARAR VERİR (Madde 3). Bu döngü DÜŞÜNSEL işi (araştırma/plan/içerik metni) otonom üretir — bu güvenli, geri-alınır.
Gerçek DIŞ DÜNYA aksiyonu (dosya yazma/e-posta/yayın) buraya DAHİL DEĞİL; o ayrıca Executive onayından geçer
(Madde 24). Yeni sistem YOK — mevcut Executive/CEO/Planning/Multi-Agent/Brain/Advisor zincirlenir."""

from __future__ import annotations

from typing import Any, Optional

# Alt görev metnini uygun domain brain'e eşler (deterministik — LLM'e bırakılmaz). Sıra: özelden genele.
_BRAIN_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Marketing", ["pazarlama", "reklam", "musteri kazan", "buyume", "icerik", "marka", "kampanya",
                   "sosyal medya", "tanitim", "hedef kitle"]),
    ("Sales", ["satis", "donusum", "huni", "muzakere", "teklif", "anlasma", "musteri iliskisi", "gelir art"]),
    ("Finance", ["gelir", "butce", "maliyet", "kar", "nakit", "fiyat", "yatirim", "finans", "gider", "kdv"]),
    ("Product", ["urun", "ozellik", "roadmap", "kullanici deneyimi", "prototip", "mvp"]),
    ("Engineering", ["kod", "yazilim", "sistem", "otomasyon", "entegrasyon", "teknik", "altyapi", "api"]),
    ("Knowledge", ["arastir", "analiz", "incele", "rapor", "bilgi", "veri", "rakip", "pazar analiz", "trend"]),
    ("Operations", ["operasyon", "surec", "tedarik", "lojistik", "verimlilik", "organizasyon", "ekip kur"]),
    ("Security", ["guvenlik", "risk", "uyum", "denetim", "gizlilik", "yasal"]),
]

_TR = str.maketrans("ıİşŞğĞüÜöÖçÇâîû", "iisSgGuUoOcCaiu")


def _norm(s: str) -> str:
    return (s or "").translate(_TR).lower()


def pick_brain(text: str) -> str:
    """Alt görev için en uygun domain brain'i deterministik seçer (yoksa genel: Business)."""
    low = _norm(text)
    for brain, kws in _BRAIN_KEYWORDS:
        if any(k in low for k in kws):
            return brain
    return "Business"


class MissionRunner:
    """Bir hedefi otonom yürütür: CEO böler → brain-destekli agent'lar çıktı üretir → rapor. İş mantığı YOK
    (orkestrasyon); gerçek düşünsel çıktı brain persona'sıyla advisor'dan gelir. Executive tek karar verici."""

    def __init__(self, mio) -> None:
        self._mio = mio

    def run(self, goal_text: str, *, business_id: Optional[str] = None, actor: str = "owner",
            max_steps: int = 5) -> dict[str, Any]:
        mio = self._mio
        goal_text = (goal_text or "").strip()
        if not goal_text:
            return {"ok": False, "error": "empty_goal", "message": "Bir hedef ver."}
        if not mio.advisor.available():
            return {"ok": False, "error": "advisor_unavailable",
                    "message": "Otonom yürütme için bir LLM (Ollama ya da API anahtarı) bağlı olmalı. "
                               "Bağlantılar ekranından ya da .env ile bağla."}

        # 1) CEO hedefi Executive hedefine + plana böler (Planning; adımlar advisor önerisi). Düşünsel — güvenli.
        direct = mio.ceo.direct(goal_text, actor=actor, horizon_days=30)
        plan_id = direct["plan"]["id"]
        plan = mio.planning.plan_view(actor, plan_id)
        steps = [s["description"] for s in plan.get("steps", []) if s.get("description")]
        if not steps:                                  # advisor adım üretmediyse hedefi tek görev say
            steps = [goal_text]
        steps = steps[:max_steps]

        # 2) her alt görev → brain-destekli agent GERÇEK çıktı üretir (advisor + brain persona/uzmanlık)
        results = []
        for i, step in enumerate(steps, 1):
            brain_name = pick_brain(step)
            output = self._brain_work(brain_name, goal_text, step, actor)
            # görünürlük: alt agent'ı kaydet (mevcut multi_agent — CEO'nun kurduğu ekip)
            agent_id = self._register_agent(brain_name, actor)
            # ÖĞRENME: sonucu Learning'e sinyal ver (MIO öğrenir — hangi brain hangi işte başarılı)
            success = bool(output) and not output.startswith("(çıktı üretilemedi")
            self._learn(brain_name, step, success, actor)
            results.append({"n": i, "step": step, "brain": brain_name,
                            "agent_id": agent_id, "output": output})

        # 3) rapor (Executive'in özeti) + kaydedilebilir markdown iş ürünü (computer-use: gerçek dosya)
        report_md = self._compile_report(goal_text, results)
        return {"ok": True, "goal": goal_text, "plan_id": plan_id, "business_id": business_id,
                "team": sorted({r["brain"] for r in results}), "steps": len(results), "results": results,
                "report_markdown": report_md}

    @staticmethod
    def _compile_report(goal: str, results: list[dict[str, Any]]) -> str:
        """Görev çıktılarını tek bir markdown iş ürününe derler (dosyaya kaydedilebilir)."""
        from datetime import datetime, timezone
        lines = [f"# MIO Görev Raporu", "", f"**Hedef:** {goal}",
                 f"**Tarih:** {datetime.now(timezone.utc).isoformat()[:19].replace('T', ' ')} UTC",
                 f"**Ekip:** {', '.join(sorted({r['brain'] for r in results}))}", "", "---", ""]
        for r in results:
            lines += [f"## {r['n']}. {r['step']}", f"*Agent: {r['brain']}*", "", r["output"], "", "---", ""]
        lines.append("_MIO Executive OS tarafından otonom üretildi._")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    def _brain_work(self, brain_name: str, goal: str, step: str, actor: str) -> str:
        """Brain-destekli agent bir alt göreve GERÇEK çıktı üretir. LLM danışman (çıktı = öneri, karar değil)."""
        brain = self._mio.brains.get(brain_name) if hasattr(self._mio, "brains") else None
        expertise = ", ".join(getattr(brain, "knowledge_domains", []) or []) if brain else "genel iş"
        prompt = (
            f"Sen MIO'nun {brain_name} uzmanı agent'ısın (uzmanlık alanların: {expertise}). "
            f"İşletmenin genel hedefi: \"{goal}\".\n"
            f"Senin sorumlu olduğun alt görev: \"{step}\".\n"
            "Bu alt görevi somut ve uygulanabilir biçimde ele al. Türkçe, kısa ve eyleme dönük yaz "
            "(3-5 madde). Uydurma veri verme; net adımlar/öneriler sun."
        )
        r = self._mio.advisor.ask(prompt, actor=actor)
        if r.get("ok"):
            return ((r.get("result", {}) or {}).get("advice", "") or "").strip() or "(boş çıktı)"
        return f"(çıktı üretilemedi: {r.get('status', r.get('error', 'bilinmiyor'))})"

    def _learn(self, brain_name: str, step: str, success: bool, actor: str) -> None:
        """Görev sonucunu Learning'e sinyal verir (mevcut learning domain — MIO deneyimden öğrenir)."""
        try:
            self._mio.learning.record_outcome(
                actor, f"mission:{brain_name}", success=success, tags=["mission", brain_name.lower()],
                lesson=f"{brain_name} agent '{step[:60]}' görevini "
                       f"{'tamamladı' if success else 'tamamlayamadı'}")
        except Exception:  # noqa: BLE001 — öğrenme sinyali başarısızsa görev yine tamamlanır (ikincil)
            pass

    def _register_agent(self, brain_name: str, actor: str) -> Optional[str]:
        """CEO'nun kurduğu alt agent'ı görünürlük için kaydeder (idempotent — brain başına bir agent)."""
        try:
            existing = {a.get("name"): a for a in self._mio.multi_agent.list_agents(actor)}
            name = f"{brain_name} Agent"
            if name in existing:
                return existing[name].get("id")
            rec = self._mio.multi_agent.register_agent(
                actor, name, role="worker", capabilities=[brain_name.lower()], max_load=5)
            return rec.get("id")
        except Exception:  # noqa: BLE001 — kayıt başarısızsa çıktı yine üretilir (görünürlük ikincil)
            return None


__all__ = ["MissionRunner", "pick_brain"]
