# MIO — Conversation Runtime & Executive Pipeline (Ürün Omurgası)

> **Ürün vizyonu (kullanıcı):** *"MIO ile doğal şekilde konuşayım. O beni anlasın, işi yapsın, gerektiğinde
> bilgisayarı kullansın, gerektiğinde ajanları yönetsin ve sohbet hiç kopmasın."*
>
> Kullanıcı komut ezberlemez · terminal düşünmez · JSON yazmaz · `call`/`execute` bilmez. **Sadece konuşur.**
> Geri kalanı Executive, Agent'lar ve araçlar arka planda organize eder.

## Temel ilke: çekirdek arayüzden bağımsız

**Odak CLI değil — Conversation Runtime (iletişim katmanı).** CLI yalnızca bu katmanın bir istemcisidir. Aynı
çekirdeğe yarın şunlar da bağlanır: **Windows uygulaması · Web · Mobil (telefon) · Sesli asistan · AR/VR.** Hepsi
aynı Conversation Runtime'a konuşur; iş mantığı arayüzde ASLA olmaz (Interface Architecture / Anayasa).

**Bütün olarak tasarlanır (parça parça değil):** Runtime baştan **ağ üzerinden erişilebilir + çok-istemcili +
oturumu cihazlar arası SENKRON** bir servistir. Böylece **telefonunu eklersin**, masaüstünde başladığın sohbet
telefonda kesintisiz devam eder — aynı `session_id`, aynı bağlam, canlı senkron.

```
  CLI   Web   📱Telefon   Ses   AR/VR       ← istemciler (yalnız taşıma; iş mantığı YOK)
    \    |      |        |     /
     ▼   ▼      ▼        ▼    ▼
      (ağ · token auth · canlı akış)        ← tüm cihazlar aynı çekirdeğe; oturum SENKRON
   ┌─────────────────────────┐
   │   CONVERSATION RUNTIME   │            ← ÜRÜN OMURGASI (arayüzden bağımsız)
   │  oturum · bağlam · süreklilik · sync │  (sohbet hiç kopmaz, cihazlar arası senkron)
   └─────────────┬───────────┘
                 ▼
              EXECUTIVE                     ← tek karar verici (niyet, yetki, risk)
                 ▼
          BUSINESS WORKSPACE                ← hangi işletme bağlamı (izole state)
                 ▼
                CEO                          ← intent→plan→delegate→report (CEOExperience)
                 ▼
              MANAGER                        ← koordinasyon rolü (delege + gözetim)
                 ▼
               AGENT                         ← görevi yürüten (multi_agent)
                 ▼
             WORKFLOW                        ← çok-adımlı DAG (checkpoint/onay)
                 ▼
   TOOLS / MCP / COMPUTER CONTROL            ← gerçek dünya (connector/MCP/shell/tarayıcı)
                 ▼
              SONUÇ
                 ▼
   ┌─────────────────────────┐
   │   CONVERSATION RUNTIME   │            ← sonucu sohbete akıtır (CEO üslubu)
   └─────────────────────────┘
```

## Her katman = MEVCUT parça (yeni domain/capability/connector YOK)

| Katman | Mevcut MIO modülü | Not |
|--------|-------------------|-----|
| **Conversation Runtime** | `mio.conversational` → oturumlu **ConversationRuntime**'a evrilir | Ürün omurgası. Tek yeni şey **bu ince spine** — domain değil, orkestrasyon. |
| Clients | `cli.ask`/REPL, HTTP `POST /converse` (+ gelecekte web/mobil/ses) | Yalnız taşıma. Hepsi aynı Runtime'ı çağırır. |
| **Executive** | `mio.executive` (decide/status, Madde 24) | Niyeti alır, yetki/risk, yol seçer. Tek karar verici. |
| **Business Workspace** | `mio.business` (izole işletme) | Sohbet hangi işletme bağlamında? |
| **CEO** | `mio.ceo` (CEOExperience: direct/delegate/report) | intent→plan→delegate→execute→report. |
| **Manager** | *rol* — CEO.delegate + `mio.multi_agent` atama/gözetim | Ayrı domain DEĞİL (yeni domain yok); koordinasyon rolü. |
| **Agent** | `mio.multi_agent` (submit_task/agents) | Görevi yürütür; agent/executor yoksa dürüst no_agent/no_connector. |
| **Workflow** | `mio.workflow` (DAG/checkpoint/rollback/approval) | Çok-adımlı işler. |
| **Tools / MCP / Computer Control** | `mio.connectors` (capability), `mio.mcp_*` (MCP hub), shell/filesystem connector, tarayıcı otomasyonu | "Bilgisayarı kullan" = MEVCUT araçları bağla; yeni connector yok. Bağlı değilse dürüst "unavailable". |
| **Intent yorumu / Sentez** | `mio.brain_runtime` (DomainBrainRuntime) + LLM advisor | LLM yalnız yorum + ifade — KARAR DEĞİL. |
| **Bilgi / Süreklilik** | `mio.knowledge`, `mio.memory`, EventBus | innate kural + oturum hafızası + arka plan iş olayları. |

## Pipeline (Conversation Runtime içinde, 6 evre)

```
[1] ENTRY      doğal dil → normalize → Intent{kind, entities, confidence}   (oturum bağlamıyla)
                belirsizse → LLM advisor YORUMLAR (karar değil) → Intent netleşir
[2] EXECUTIVE  Intent'i alır. Okuma mı, çok-adımlı/mutasyon mu? Risk? (Madde 24) → yol seç
[3] PLANNING   (çok-adımlıysa) draft_plan → add_step(domain.op) → sequence → assess (fizibilite)
[4] EXECUTE    her adım: DomainBrainRuntime.perform → Executive onayı → appservice.call/act
                connector yoksa dürüst "unavailable"; uzun iş → arka planda, sohbet KOPMAZ (EventBus)
[5] SYNTHESIZE Executive toplar; LLM advisor yalnız ifade → tek akıcı cevap
[6] REPLY      doğal dil (CEO üslubu) + data → Conversation Runtime → kullanıcı
```

## Süreklilik ("sohbet hiç kopmasın")
- **Oturum**: her konuşma bir `session_id` + kalıcı bağlam (mevcut conversational context + `mio.memory`).
- **Arka plan işi**: Executive uzun bir iş başlatır (agent/workflow), kullanıcı konuşmaya devam eder; iş bitince
  **EventBus** üzerinden sonuç sohbete düşer. Tek kesintisiz akış.
- **Referanslar**: "bunu durdur", "devam et", "onu raporla" → önceki adıma/işe bağlanır (konuşma hafızası).

## Görsel mimari referansı: OpenJarvis → MIO eşlemesi

OpenJarvis (Stanford, "Personal AI on Personal Devices") **görsel/etkileşim mimarisi** referans alınır — kod kopya
DEĞİL, desen uyarlaması (Anayasa'ya göre "kendimize göre"). OpenJarvis frontend'i (React 19 + Vite + Tailwind v4 +
shadcn/base-ui, **Tauri masaüstü + PWA telefon**, zustand, SSE streaming, markdown/katex) neredeyse **birebir MIO
backend'ine oturuyor** — her ekran MIO'nun MEVCUT DTO'suna bağlanır:

| OpenJarvis ekranı/parçası | MIO karşılığı (mevcut, yeni yok) |
|---|---|
| `ChatPage` | Conversation Runtime · `POST /converse` |
| `DashboardPage` | `appservice.ceo_report` (konsolide pano) |
| `AgentsPage` | `appservice.agent_list` / `agent_tasks` (multi_agent) |
| `ApprovalBell` | yüksek-risk onay kuyruğu (Madde 24) |
| `SystemPulse` | `appservice.diagnose` / health |
| `LogsPage` | `appservice.events` / audit |
| `DataSourcesPage` | connectors / MCP yüzeyi |
| `SettingsPage` / `GetStartedPage` | config / onboarding |
| `lib/sse.ts` + `useAgentEvents` | **EventBus** → per-session canlı akış (sohbet kopmaz) |
| Tauri + PWA (`pwa-192/512`) | arayüzden bağımsız istemciler; **telefon PWA ile kurulur** |

**Uyarlama ilkesi:** OpenJarvis'in ekran yapısını + etkileşim desenini al; **iş mantığını MIO backend'inde bırak**
(arayüz yalnız DTO tüketir). Böylece görsel OpenJarvis'e benzer, çekirdek %100 MIO (Executive otoritesi, Anayasa).

## Katman katman yol haritası (bugün basit → projeyle büyür)
1. **L1 — Conversation Runtime spine**: oturumlu, arayüzden bağımsız `converse(session, text)`; CLI + HTTP aynı yolu
   kullanır. (Bugün: mevcut intent yönlendirmesi + oturum.)
2. **L2 — Executive pipeline**: keyword→tek-op yerine Intent→Planning→Execute→Synthesize (çok-adımlı işler).
3. **L3 — Basit sohbet UI** (paperclip benzeri): tek sayfa, `/converse`'e bağlı; kendi kendine yeten.
4. **L4 — Süreklilik**: arka plan işleri + EventBus → sohbete canlı sonuç; onay düğmeleri (Madde 24).
5. **L5 — Computer Control**: mevcut shell/filesystem/MCP/tarayıcı araçlarını Executive kontrolünde bağla.
6. **L6+**: streaming, zengin kartlar (plan/pano), ses girişi, sonra web/mobil istemciler — aynı çekirdek.

> **paperclip** referansı UI iskeleti için gerekiyor (repo/link). Alınınca L3 ona göre şekillenir; şimdilik L1–L2
> (çekirdek omurga) arayüzden bağımsız ilerler — hangi arayüzü seçersen seç aynı Runtime'a bağlanır.
