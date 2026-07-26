"""MIO Core · CEO Experience — sahibin yüksek-seviyeli niyetini uçtan uca yürüten orkestrasyon.

**Bu YENİ bir mimari DEĞİL.** Sahibin tek cümlelik stratejik niyetini (ör. "3 ayda geliri ikiye katla") mevcut
domainlere bağlayan ince bir **orkestrasyon katmanı**dır: intent → plan → delegate → execute → report.

  intent   → sahibin doğal niyeti (metin + opsiyonel adımlar)
  plan     → Executive stratejik hedef (`executive.set_goal`) + Planning taslak/sıralama/fizibilite
  delegate → Planning adımları → Multi-Agent görevleri (`multi_agent.submit_task`, yetenek eşleşmeli)
  execute  → Multi-Agent deterministik atama+dispatch (uygun agent/executor yoksa DÜRÜST: no_agent/no_connector)
  report   → konsolide yönetim panosu (Executive + Planning + Multi-Agent + Business + tanı)

**YENİ plan/görev/hedef/registry OLUŞTURMAZ** — hepsini mevcut Executive/Planning/Multi-Agent üzerinden yürütür
(ürün bütünlüğü). **Executive tek karar verici**; LLM yalnız **danışman** — adım önerisi advisory'dir (karar
DEĞİL), sahip/Executive onaylar. Yüksek-risk görev onay ister (Madde 24). İş mantığı domainlerde; burada yok."""

from __future__ import annotations

from typing import Any, Optional

from mio_core import appservice


class CEOExperience:
    """Sahip niyeti → mevcut Executive/Planning/Multi-Agent zinciri. İş mantığı YOK (orkestrasyon)."""

    def __init__(self, mio) -> None:
        self._mio = mio

    # ------------------------------------------------------------------ #
    def direct(self, goal_text: str, *, horizon_days: int = 30, steps: Optional[list] = None,
               actor: str = "owner") -> dict[str, Any]:
        """Sahibin stratejik niyetini bir Executive hedefi + Planning planına dönüştürür (yürütmez).

        `steps` verilirse sahibin niyetidir; verilmez ve Advisor etkinse danışman **önerir** (advisory, karar
        değil); ikisi de yoksa boş plan döner (sahip adım ekler). Adımlar bağımsız eklenir (sahip bağımlılık
        belirtmedi); Planning `sequence` yine deterministik sıralar, `assess` fizibiliteyi denetler."""
        mio = self._mio
        goal = mio.executive.set_goal(actor, goal_text, horizon_days)          # Executive stratejik hedef
        plan = mio.planning.draft_plan(actor, goal_text, goal_id=goal.goal_id)  # Planning taslak (hedefe bağlı)

        source, specs = "none", steps
        if not specs and mio.advisor.available():
            specs = self._advisor_steps(goal_text, actor)                     # danışman ÖNERİSİ (advisory)
            source = "advisor" if specs else "none"
        elif specs:
            source = "owner"

        added = []
        for spec in (specs or []):
            desc = spec.get("description") if isinstance(spec, dict) else str(spec)
            cap = spec.get("capability") if isinstance(spec, dict) else None
            if not (desc or "").strip():
                continue
            added.append(mio.planning.add_step(actor, plan["id"], desc, capability=cap))

        sequenced = assess = None
        if added:
            sequenced = mio.planning.sequence(actor, plan["id"])              # deterministik sıralama
            assess = mio.planning.assess(actor, plan["id"])                   # fizibilite (mutasyonsuz)

        feasible = assess["feasible"] if assess else None
        if not added:
            nxt = "Plana adım ekleyin: ceo direct <hedef> ile steps verin veya Advisor'ı etkinleştirin."
        elif feasible:
            nxt = f"Devretmek için: ceo delegate {plan['id']} (yüksek-risk görev onay ister)."
        else:
            nxt = f"Plan fizibil değil; sorunları giderin: {assess['issues'][:2]}"
        return {
            "goal": {"id": goal.goal_id, "text": goal.text, "horizon_days": goal.horizon_days,
                     "status": goal.status},
            "plan": {"id": plan["id"], "steps": len(added), "step_source": source,
                     "status": (sequenced or plan).get("status", plan.get("status"))},
            "feasible": feasible, "assessment": assess, "next": nxt,
        }

    def delegate(self, plan_id: str, *, actor: str = "owner", approve: bool = False) -> dict[str, Any]:
        """Planning adımlarını Multi-Agent görevlerine devreder (execute). Her adım → bir görev; yetenek varsa
        `required_capabilities`. Uygun agent/executor yoksa DÜRÜST no_agent/no_connector (çökmez). Yüksek-risk
        görev onaysızsa requires_approval (Madde 24). YENİ görev sistemi YOK — mevcut multi_agent kullanılır."""
        mio = self._mio
        plan = mio.planning.plan_view(actor, plan_id)
        results = []
        for step in plan.get("steps", []):
            caps = [step["capability"]] if step.get("capability") else []
            task = mio.multi_agent.submit_task(
                actor, step["description"], required_capabilities=caps,
                payload={"plan_id": plan_id, "step_id": step["id"], "goal_id": plan.get("goal_id")},
                user_approved=approve)
            results.append({"step_id": step["id"], "capability": step.get("capability"),
                            "task_id": task["id"], "status": task["status"]})
        by_status: dict[str, int] = {}
        for r in results:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        return {"plan_id": plan_id, "goal_id": plan.get("goal_id"), "delegated": len(results),
                "by_status": by_status, "results": results}

    def report(self, *, actor: str = "owner") -> dict[str, Any]:
        """Konsolide yönetim panosu (salt-okunur DTO): Executive + Planning + Multi-Agent + Business + tanı.

        Bu aynı zamanda **İşletme Panosu (Dashboard)** DTO'sudur — tek yerde bütün resim. Mevcut domainlerden
        gerçek veri toplar; hiçbir şey uydurmaz (veri yoksa boş/sıfır — dürüst)."""
        mio = self._mio
        exe = appservice.executive_summary(mio)
        exec_status = mio.executive.status()
        plans = mio.planning.list_plans(actor)
        agents = mio.multi_agent.list_agents(actor)
        tasks = mio.multi_agent.list_tasks(actor)
        businesses = mio.business.list() if hasattr(mio, "business") else []

        return {
            "identity": exe["identity"],
            "system_confidence": exe["system_confidence"],
            "executive_score": exe["executive_score"],
            "businesses": {"total": len(businesses),
                           "names": [b["name"] for b in businesses[:8]]},
            "goals": exec_status.get("counts", {}).get("goals", 0),
            "active_goals": exec_status.get("counts", {}).get("active_goals", 0),
            "plans": {"total": len(plans), "by_status": _count_by(plans, "status")},
            "agents": {"total": len(agents),
                       "roster": [{"name": a.get("name"), "role": a.get("role"),
                                   "status": a.get("status")} for a in agents[:8]]},
            "tasks": {"total": len(tasks), "by_status": _count_by(tasks, "status")},
            "recommended_actions": exe["recommended_actions"],
            "warnings": exe["warnings"],
        }

    # ------------------------------------------------------------------ #
    def _advisor_steps(self, goal_text: str, actor: str) -> list[dict[str, Any]]:
        """Advisor'dan adım ÖNERİSİ (advisory — karar değil). Başarısız/boşsa []. Serbest metni satırlara böler."""
        try:
            adv = self._mio.advisor.ask(
                "Bir işletme hedefini 3-6 somut, sıralı eyleme böl. Hedef: '" + goal_text + "'. "
                "Yalnız eylemleri madde madde, her satır bir eylem, kısa Türkçe yaz.", actor=actor)
        except Exception:  # noqa: BLE001 — danışman zorunlu değil; başarısızsa öneri yok
            return []
        if not adv.get("ok"):
            return []
        text = (adv.get("result", {}) or {}).get("advice", "") or ""
        specs = []
        for line in text.splitlines():
            clean = line.strip().lstrip("-*0123456789.) ").strip()
            if clean:
                specs.append({"description": clean[:200]})
        return specs[:6]


def _count_by(items: list, key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        out[it.get(key, "?")] = out.get(it.get(key, "?"), 0) + 1
    return out


__all__ = ["CEOExperience"]
