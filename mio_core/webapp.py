"""MIO Core · Web Uygulaması — tek-dosya, bağımsız (self-contained) arayüz. HARİCİ BAĞIMLILIK YOK.

`python -m mio_core serve` → tarayıcıda `http://127.0.0.1:8080` → çalışan uygulama: **onboarding → sohbet → panel**.
MIO'nun MEVCUT HTTP API'sine (aynı appservice DTO'ları) bağlanır: /converse, /business, /ceo/report, /health.
İş mantığı YOK (arayüz yalnız DTO tüketir — Interface Architecture). CLI değil, gerçek uygulama yüzü.

Inline CSS/JS (framework yok, build yok, node yok) — stdlib http.server ile servis edilir. Katman katman büyür
(OpenJarvis görsel dili referans): koyu tema, sohbet baloncukları, kenar çubuğu, onboarding akışı."""

WEBAPP_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0d12">
<title>MIO · Executive OS</title>
<style>
  :root{
    --bg:#0b0d12; --panel:#12151d; --panel2:#171b25; --line:#232838; --line2:#2c3243;
    --text:#e7ebf3; --muted:#8b93a7; --accent:#6d8bff; --accent2:#a678ff;
    --ok:#3ecf8e; --warn:#f5b544; --err:#f26d6d; --user:#243049;
    --grad:linear-gradient(135deg,#6d8bff,#a678ff);
  }
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{background:var(--bg);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,system-ui,sans-serif;
    -webkit-font-smoothing:antialiased;overflow:hidden}
  button{font-family:inherit;cursor:pointer}
  .hidden{display:none!important}

  /* ---- kabuk ---- */
  #app{display:flex;height:100vh;width:100vw}
  aside{width:248px;flex:0 0 248px;background:var(--panel);border-right:1px solid var(--line);
    display:flex;flex-direction:column;padding:16px 12px;gap:6px}
  .brand{display:flex;align-items:center;gap:10px;padding:8px 8px 16px}
  .logo{width:34px;height:34px;border-radius:9px;background:var(--grad);display:grid;place-items:center;
    font-weight:800;color:#fff;font-size:16px;box-shadow:0 4px 18px rgba(109,139,255,.35)}
  .brand b{font-size:15px;letter-spacing:.2px}
  .brand span{display:block;font-size:11px;color:var(--muted);font-weight:500}
  .nav{display:flex;flex-direction:column;gap:2px;margin-top:4px}
  .nav button{display:flex;align-items:center;gap:11px;width:100%;text-align:left;background:transparent;
    border:0;color:var(--muted);padding:10px 11px;border-radius:9px;font-size:14px;font-weight:500;transition:.15s}
  .nav button:hover{background:var(--panel2);color:var(--text)}
  .nav button.active{background:var(--panel2);color:var(--text)}
  .nav .ic{width:18px;text-align:center;font-size:15px}
  .sidefoot{margin-top:auto;padding:10px 8px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--muted);margin-right:7px}
  .dot.ok{background:var(--ok);box-shadow:0 0 8px var(--ok)}
  .dot.err{background:var(--err)}

  main{flex:1;display:flex;flex-direction:column;min-width:0;position:relative}
  .topbar{height:56px;flex:0 0 56px;border-bottom:1px solid var(--line);display:flex;align-items:center;
    padding:0 20px;gap:12px;background:rgba(11,13,18,.6);backdrop-filter:blur(8px)}
  .topbar .title{font-weight:600;font-size:15px}
  .topbar .biz{margin-left:auto;font-size:13px;color:var(--muted);display:flex;align-items:center;gap:8px}
  .chip{background:var(--panel2);border:1px solid var(--line2);border-radius:20px;padding:5px 12px;font-size:12.5px;
    color:var(--text)}

  /* ---- sohbet ---- */
  .view{flex:1;overflow-y:auto;padding:24px 0}
  .stream{max-width:760px;margin:0 auto;padding:0 20px;display:flex;flex-direction:column;gap:18px}
  .msg{display:flex;gap:12px;align-items:flex-start;animation:rise .25s ease}
  @keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  .msg .av{width:30px;height:30px;border-radius:8px;flex:0 0 30px;display:grid;place-items:center;font-size:14px;
    font-weight:700}
  .msg.mio .av{background:var(--grad);color:#fff}
  .msg.you .av{background:var(--user);color:var(--text)}
  .bubble{padding:12px 15px;border-radius:13px;line-height:1.55;font-size:14.5px;max-width:100%;
    white-space:pre-wrap;word-wrap:break-word}
  .msg.mio .bubble{background:var(--panel2);border:1px solid var(--line)}
  .msg.you{flex-direction:row-reverse}
  .msg.you .bubble{background:var(--user)}
  .who{font-size:12px;color:var(--muted);margin-bottom:4px;font-weight:600}
  .card{margin-top:10px;background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:12px 14px;
    font-size:13px;color:var(--muted)}
  .card .kv{display:flex;justify-content:space-between;padding:3px 0}
  .card .kv b{color:var(--text);font-weight:600}
  .typing{display:inline-flex;gap:4px;padding:4px 0}
  .typing i{width:7px;height:7px;border-radius:50%;background:var(--muted);animation:blink 1.2s infinite}
  .typing i:nth-child(2){animation-delay:.2s}.typing i:nth-child(3){animation-delay:.4s}
  @keyframes blink{0%,60%,100%{opacity:.25}30%{opacity:1}}

  /* ---- girdi ---- */
  .composer{flex:0 0 auto;padding:14px 20px 20px;border-top:1px solid var(--line);background:var(--bg)}
  .cbox{max-width:760px;margin:0 auto;display:flex;gap:10px;align-items:flex-end;background:var(--panel2);
    border:1px solid var(--line2);border-radius:15px;padding:8px 8px 8px 16px;transition:.15s}
  .cbox:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px rgba(109,139,255,.12)}
  .cbox textarea{flex:1;background:transparent;border:0;color:var(--text);font-size:15px;resize:none;outline:none;
    max-height:160px;line-height:1.5;padding:6px 0}
  .send{width:38px;height:38px;flex:0 0 38px;border:0;border-radius:11px;background:var(--grad);color:#fff;
    font-size:17px;display:grid;place-items:center;transition:.15s}
  .send:disabled{opacity:.4;cursor:default}
  .hint{max-width:760px;margin:8px auto 0;font-size:11.5px;color:var(--muted);text-align:center}
  .suggs{max-width:760px;margin:0 auto 14px;display:flex;gap:8px;flex-wrap:wrap;padding:0 20px}
  .sugg{background:var(--panel2);border:1px solid var(--line2);color:var(--muted);border-radius:20px;
    padding:7px 14px;font-size:13px;transition:.15s}
  .sugg:hover{color:var(--text);border-color:var(--accent)}

  /* ---- panel/işletme grid ---- */
  .grid{max-width:900px;margin:0 auto;padding:8px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
  .stat{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:16px}
  .stat .lab{font-size:12.5px;color:var(--muted);margin-bottom:8px}
  .stat .val{font-size:26px;font-weight:700;letter-spacing:-.5px}
  .stat .sub{font-size:12px;color:var(--muted);margin-top:4px}
  .section{max-width:900px;margin:18px auto 0;padding:0 20px}
  .section h3{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin:0 0 10px}
  .row{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px 15px;margin-bottom:8px;
    display:flex;align-items:center;gap:12px}
  .row .rt{font-weight:600;font-size:14px}.row .rs{font-size:12.5px;color:var(--muted)}
  .badge{margin-left:auto;font-size:11.5px;padding:3px 10px;border-radius:20px;background:var(--panel2);
    border:1px solid var(--line2);color:var(--muted)}
  .empty{max-width:900px;margin:40px auto;text-align:center;color:var(--muted);font-size:14px}
  .btn{background:var(--grad);color:#fff;border:0;border-radius:11px;padding:11px 20px;font-size:14px;font-weight:600}
  .btn.ghost{background:var(--panel2);border:1px solid var(--line2);color:var(--text)}

  /* ---- onboarding ---- */
  #onb{position:absolute;inset:0;background:var(--bg);z-index:50;display:flex;align-items:center;justify-content:center;
    padding:24px}
  .obcard{width:100%;max-width:460px;background:var(--panel);border:1px solid var(--line);border-radius:20px;
    padding:34px;animation:rise .35s ease}
  .obcard .biglogo{width:56px;height:56px;border-radius:15px;background:var(--grad);display:grid;place-items:center;
    font-size:26px;font-weight:800;color:#fff;margin-bottom:20px;box-shadow:0 8px 30px rgba(109,139,255,.4)}
  .obcard h1{font-size:24px;margin:0 0 8px;letter-spacing:-.4px}
  .obcard p{color:var(--muted);font-size:14.5px;line-height:1.6;margin:0 0 22px}
  .field{margin-bottom:16px}
  .field label{display:block;font-size:13px;color:var(--muted);margin-bottom:7px;font-weight:600}
  .field input,.field select{width:100%;background:var(--panel2);border:1px solid var(--line2);color:var(--text);
    border-radius:11px;padding:12px 14px;font-size:14.5px;outline:none;font-family:inherit}
  .field input:focus,.field select:focus{border-color:var(--accent)}
  .obrow{display:flex;gap:10px;margin-top:6px}
  .steps{display:flex;gap:6px;margin-bottom:24px}
  .steps i{height:4px;flex:1;border-radius:3px;background:var(--line2)}
  .steps i.on{background:var(--grad)}

  @media(max-width:720px){
    aside{position:absolute;z-index:40;height:100%;transform:translateX(-100%);transition:.25s}
    aside.open{transform:none}
    .topbar .menu{display:grid!important}
  }
  .menu{display:none;width:34px;height:34px;place-items:center;background:var(--panel2);border:1px solid var(--line2);
    border-radius:9px;color:var(--text);font-size:16px}
</style>
</head>
<body>
<div id="app">
  <aside id="side">
    <div class="brand">
      <div class="logo">M</div>
      <div><b>MIO</b><span>Executive OS</span></div>
    </div>
    <div class="nav">
      <button data-view="chat" class="active"><span class="ic">💬</span> Sohbet</button>
      <button data-view="mission"><span class="ic">🎯</span> Görev</button>
      <button data-view="panel"><span class="ic">📊</span> Panel</button>
      <button data-view="biz"><span class="ic">🏢</span> İşletmeler</button>
      <button data-view="conn"><span class="ic">🔌</span> Bağlantılar</button>
    </div>
    <div class="sidefoot"><span id="statusDot" class="dot"></span><span id="statusText">bağlanıyor…</span></div>
  </aside>

  <main>
    <div class="topbar">
      <div class="menu" id="menuBtn">☰</div>
      <div class="title" id="viewTitle">Sohbet</div>
      <div class="biz"><span class="chip" id="bizChip">—</span></div>
    </div>

    <!-- SOHBET -->
    <div class="view" id="view-chat">
      <div class="stream" id="stream"></div>
    </div>
    <div class="composer" id="composer">
      <div class="suggs" id="suggs">
        <button class="sugg">Durum nedir?</button>
        <button class="sugg">Yönetim panosu</button>
        <button class="sugg">Yeni bir pazarlama işletmesi kur</button>
        <button class="sugg">Neler yapabilirsin?</button>
      </div>
      <div class="cbox">
        <textarea id="input" rows="1" placeholder="MIO ile konuş…  (örn: 'geliri artırmak için ne yapmalıyım')"></textarea>
        <button class="send" id="mic" title="Sesli konuş">🎤</button>
        <button class="send" id="send" disabled>↑</button>
      </div>
      <div class="hint"><span id="hinttext">MIO Executive · doğal dille konuş, işi arka planda o organize eder</span>
        · <label style="cursor:pointer"><input type="checkbox" id="ttsToggle"> sesli yanıt</label></div>
    </div>

    <!-- PANEL -->
    <div class="view hidden" id="view-panel"></div>

    <!-- İŞLETMELER -->
    <div class="view hidden" id="view-biz"></div>

    <!-- BAĞLANTILAR -->
    <div class="view hidden" id="view-conn"></div>

    <!-- GÖREV (otonom) -->
    <div class="view hidden" id="view-mission"></div>
  </main>
</div>

<!-- ONBOARDING -->
<div id="onb" class="hidden">
  <div class="obcard" id="obcard"></div>
</div>

<script>
const API = location.origin;
async function api(path, method="GET", body){
  const opt={method,headers:{}};
  if(body){opt.headers["Content-Type"]="application/json";opt.body=JSON.stringify(body);}
  const r=await fetch(API+path,opt);
  let d=null; try{d=await r.json();}catch(e){}
  return {ok:r.ok,status:r.status,data:d};
}
const $=s=>document.querySelector(s);
const el=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const esc=s=>(s==null?"":String(s)).replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));

let STATE={businesses:[],biz:null,busy:false};

/* ---------------- durum / sağlık ---------------- */
async function refreshStatus(){
  const h=await api("/health");
  const dot=$("#statusDot"),tx=$("#statusText");
  if(h.ok){dot.className="dot ok";tx.textContent="MIO çevrimiçi";}
  else{dot.className="dot err";tx.textContent="bağlantı yok";}
}
async function refreshBiz(){
  const r=await api("/business");
  STATE.businesses=(r.ok&&Array.isArray(r.data))?r.data:[];
  STATE.biz=STATE.businesses[0]||null;
  $("#bizChip").textContent=STATE.biz?("🏢 "+STATE.biz.name):"işletme yok";
}

/* ---------------- sohbet ---------------- */
function addMsg(role,text,dataCard){
  const wrap=el("div","msg "+(role==="you"?"you":"mio"));
  const av=el("div","av",role==="you"?"S":"M");
  const body=el("div","",""); body.style.minWidth="0";
  if(role!=="you") body.appendChild(el("div","who","MIO"));
  const bub=el("div","bubble",esc(text)); body.appendChild(bub);
  if(dataCard) body.appendChild(dataCard);
  wrap.appendChild(av); wrap.appendChild(body);
  $("#stream").appendChild(wrap);
  $("#view-chat").scrollTop=$("#view-chat").scrollHeight;
  return bub;
}
function typing(){
  const wrap=el("div","msg mio"); wrap.id="typing";
  wrap.appendChild(el("div","av","M"));
  const b=el("div"); b.appendChild(el("div","who","MIO"));
  b.appendChild(el("div","bubble",'<span class="typing"><i></i><i></i><i></i></span>'));
  wrap.appendChild(b); $("#stream").appendChild(wrap);
  $("#view-chat").scrollTop=$("#view-chat").scrollHeight;
}
function stopTyping(){const t=$("#typing");if(t)t.remove();}

function dataCard(intent,data){
  if(!data||typeof data!=="object") return null;
  const c=el("div","card");
  const add=(k,v)=>{const r=el("div","kv");r.appendChild(el("span","",k));r.appendChild(el("b","",v));c.appendChild(r);};
  if(intent==="ceo"||data.executive_score!=null){
    if(data.system_confidence)add("Sistem güveni",esc(data.system_confidence));
    if(data.executive_score!=null)add("Skor",data.executive_score+"/100");
    if(data.businesses)add("İşletme",data.businesses.total??data.businesses);
    if(data.active_goals!=null)add("Aktif hedef",data.active_goals);
    if(data.agents)add("Agent",data.agents.total??data.agents);
    return c.children.length?c:null;
  }
  if(Array.isArray(data.businesses)&&data.businesses.length){
    data.businesses.slice(0,5).forEach(b=>add(esc(b.name),esc(b.label||b.business_type||"")));
    return c;
  }
  return null;
}

async function send(text){
  text=(text||$("#input").value).trim();
  if(!text||STATE.busy) return;
  STATE.busy=true; $("#send").disabled=true;
  $("#input").value=""; autosize();
  $("#suggs").classList.add("hidden");
  addMsg("you",text);
  typing();
  const r=await api("/converse","POST",{text});
  stopTyping();
  if(r.ok&&r.data){
    const bub=addMsg("mio", r.data.response||"…", dataCard(r.data.intent,r.data.data));
    speak(r.data.response||"");                        // sesli yanıt (toggle açıksa)
    // LLM bir işlem ÖNERDİ → Executive onayı bekler (Madde 24). Düğmeyle onayla/vazgeç (görünür onay).
    const pa=(r.data.data||{}).pending_action;
    if(pa) addConfirm(bub);
    // işletme değişmiş olabilir (ör. yeni kuruldu) → tazele
    if(r.data.intent==="business"||/işletme|kur/i.test(text)){ await refreshBiz(); }
  }else{
    addMsg("mio","Bir sorun oldu (HTTP "+r.status+"). MIO sunucusu çalışıyor mu?");
  }
  STATE.busy=false; $("#input").focus();
}
function addConfirm(bubble){
  const row=el("div"); row.style.cssText="display:flex;gap:8px;margin-top:10px";
  const yes=el("button","btn","✓ Onayla"); yes.style.cssText="padding:8px 16px;font-size:13px";
  const no=el("button","btn ghost","Vazgeç"); no.style.cssText="padding:8px 16px;font-size:13px";
  yes.onclick=()=>{row.remove(); send("evet, onaylıyorum");};
  no.onclick=()=>{row.remove(); send("hayır, vazgeç");};
  row.appendChild(yes); row.appendChild(no);
  bubble.parentNode.appendChild(row);
  $("#view-chat").scrollTop=$("#view-chat").scrollHeight;
}

/* ---------------- panel ---------------- */
async function renderPanel(){
  const v=$("#view-panel"); v.innerHTML="";
  const r=await api("/ceo/report");
  if(!r.ok){v.appendChild(el("div","empty","Panel yüklenemedi."));return;}
  const d=r.data;
  const grid=el("div","grid");
  const stat=(lab,val,sub)=>{const s=el("div","stat");s.appendChild(el("div","lab",lab));
    s.appendChild(el("div","val",val));if(sub)s.appendChild(el("div","sub",sub));return s;};
  grid.appendChild(stat("Sistem güveni",esc(d.system_confidence||"—"),(d.executive_score??0)+"/100"));
  grid.appendChild(stat("İşletmeler",d.businesses?.total??0,(d.businesses?.names||[]).slice(0,3).join(", ")));
  grid.appendChild(stat("Aktif hedef",d.active_goals??0,(d.goals??0)+" toplam"));
  grid.appendChild(stat("Planlar",d.plans?.total??0));
  grid.appendChild(stat("Agent'lar",d.agents?.total??0));
  grid.appendChild(stat("Görevler",d.tasks?.total??0));
  v.appendChild(grid);
  if((d.recommended_actions||[]).length){
    const s=el("div","section"); s.appendChild(el("h3","Öneriler"));
    d.recommended_actions.forEach(a=>{const row=el("div","row");row.appendChild(el("div","rt",esc(a)));s.appendChild(row);});
    v.appendChild(s);
  }
}
/* ---------------- işletmeler ---------------- */
async function renderBiz(){
  await refreshBiz();
  const v=$("#view-biz"); v.innerHTML="";
  const head=el("div","section");
  const h=el("div"); h.style.display="flex"; h.style.alignItems="center";
  h.appendChild(el("h3","İşletmeler")); const add=el("button","btn","+ Yeni işletme");
  add.style.marginLeft="auto"; add.onclick=()=>startOnboarding(true); h.appendChild(add);
  head.appendChild(h); v.appendChild(head);
  if(!STATE.businesses.length){v.appendChild(el("div","empty","Henüz işletmen yok. '+ Yeni işletme' ile başla."));return;}
  const sec=el("div","section");
  STATE.businesses.forEach(b=>{
    const row=el("div","row"); const t=el("div");
    t.appendChild(el("div","rt",esc(b.name)));
    t.appendChild(el("div","rs",esc((b.label||b.business_type||"")+" · "+(b.departments||[]).join(", "))));
    row.appendChild(t); row.appendChild(el("div","badge",esc(b.business_type||"")));
    sec.appendChild(row);
  });
  v.appendChild(sec);
}

/* ---------------- bağlantılar (MCP + servisler) ---------------- */
const RISK={low:["Düşük","var(--ok)"],medium:["Orta","var(--warn)"],high:["Yüksek","var(--err)"]};
async function renderConn(){
  const v=$("#view-conn"); v.innerHTML="";
  const intro=el("div","section");
  intro.appendChild(el("h3","Bağlantılar — MCP & Servisler"));
  intro.appendChild(el("div","rs","MIO tüm MCP sunucularını kurdu. Kullanmak istediğine <b>Yetki ver</b>. "+
    "API anahtarı gerekiyorsa, aşağıda yazan anahtarı proje klasöründeki <b>.env</b> dosyana ekle, sonra MIO'yu yeniden başlat."));
  v.appendChild(intro);
  const r=await api("/mcp/catalog");
  if(!r.ok){v.appendChild(el("div","empty","Katalog yüklenemedi."));return;}
  const sec=el("div","section");
  (r.data||[]).forEach(m=>{
    const row=el("div","row"); row.style.alignItems="flex-start";
    const t=el("div"); t.style.flex="1";
    t.appendChild(el("div","rt",esc(m.name)));
    t.appendChild(el("div","rs",esc(m.description||"")));
    if((m.needs_keys||[]).length){
      const k=el("div","rs"); k.style.marginTop="6px"; k.style.color="var(--accent)";
      k.innerHTML="🔑 Gerekli anahtar: "+m.needs_keys.map(x=>`<code>${esc(x)}</code>`).join(", ");
      t.appendChild(k);
    }
    row.appendChild(t);
    const right=el("div"); right.style.textAlign="right"; right.style.display="flex";
    right.style.flexDirection="column"; right.style.gap="6px"; right.style.alignItems="flex-end";
    const rk=RISK[m.risk]||RISK.low;
    const rb=el("div","badge","Risk: "+rk[0]); rb.style.color=rk[1]; right.appendChild(rb);
    const enabled=m.enabled||m.trust_level==="trusted";
    if(enabled){ const e=el("div","badge","✓ Etkin"); e.style.color="var(--ok)"; e.style.borderColor="var(--ok)"; right.appendChild(e);}
    else{
      const btn=el("button","btn","Yetki ver"); btn.style.padding="8px 14px"; btn.style.fontSize="13px";
      btn.onclick=async()=>{
        btn.disabled=true; btn.textContent="…";
        const rr=await api("/mcp/"+m.server_id+"/trust","POST",{level:"trusted"});
        if(rr.ok){renderConn();}else{btn.disabled=false;btn.textContent="Yetki ver";alert("Yetki verilemedi");}
      };
      right.appendChild(btn);
    }
    row.appendChild(right); sec.appendChild(row);
  });
  v.appendChild(sec);
}

/* ---------------- görev (otonom: CEO → brain-destekli agent'lar) ---------------- */
function renderMission(){
  const v=$("#view-mission"); v.innerHTML="";
  const s=el("div","section");
  s.appendChild(el("h3","Otonom Görev — bir hedef ver, MIO ekibi yapsın"));
  s.appendChild(el("div","rs","MIO hedefini alt görevlere böler, her birine uygun bir <b>brain-destekli agent</b> "+
    "(Pazarlama, Finans, Araştırma…) atar ve gerçek çıktı üretir. Yerel modelle çalışır — birkaç dakika sürebilir."));
  const box=el("div"); box.style.cssText="display:flex;gap:10px;margin-top:14px;max-width:700px";
  const inp=el("input"); inp.id="mgoal"; inp.placeholder="ör. kahve markam için bu ay 100 yeni müşteri kazan";
  inp.style.cssText="flex:1;background:var(--panel2);border:1px solid var(--line2);color:var(--text);border-radius:11px;padding:12px 14px;font-size:14.5px;outline:none";
  const btn=el("button","btn","MIO'ya yaptır"); btn.id="mrun";
  box.appendChild(inp); box.appendChild(btn); s.appendChild(box);
  v.appendChild(s);
  const out=el("div","section"); out.id="mout"; v.appendChild(out);
  const run=async()=>{
    const goal=inp.value.trim(); if(!goal)return;
    btn.disabled=true; inp.disabled=true;
    out.innerHTML="";
    const wait=el("div","row"); wait.innerHTML='<div class="rt">🎯 MIO ekibi çalışıyor…</div>'+
      '<div class="rs" style="margin-left:12px">Hedef bölünüyor, agent\'lar çıktı üretiyor (birkaç dakika)</div>';
    out.appendChild(wait);
    const r=await api("/mission","POST",{goal,max_steps:3});
    out.innerHTML="";
    if(!r.ok||!r.data||!r.data.ok){
      const msg=(r.data&&(r.data.message||r.data.error))||"Görev yürütülemedi.";
      out.appendChild(el("div","empty",esc(msg)+" (Gerçek konuşma/otonomi için Bağlantılar'dan bir LLM bağlı olmalı.)"));
      btn.disabled=false; inp.disabled=false; return;
    }
    const d=r.data;
    const head=el("div","row");
    head.innerHTML='<div><div class="rt">✓ Görev tamamlandı</div><div class="rs">Ekip: '+
      (d.team||[]).join(", ")+' · '+d.steps+' adım</div></div>';
    if(d.report_markdown){                              // computer-use: gerçek dosyaya kaydet (onaylı)
      const sv=el("button","btn ghost","📄 Raporu kaydet"); sv.style.marginLeft="auto";
      sv.style.padding="8px 14px"; sv.style.fontSize="13px";
      sv.onclick=async()=>{ sv.disabled=true; sv.textContent="Kaydediliyor…";
        const rr=await api("/mission/save","POST",{content:d.report_markdown,filename:goal});
        const p=rr.data&&rr.data.outcome&&(rr.data.outcome.result||rr.data.outcome);
        const path=(p&&(p.path||p.requested_path))||(rr.data&&rr.data.requested_path);
        sv.textContent = rr.ok ? ("✓ Kaydedildi: "+(path||"dosya")) : "Kaydedilemedi";
      };
      head.appendChild(sv);
    }
    out.appendChild(head);
    (d.results||[]).forEach(res=>{
      const c=el("div","row"); c.style.cssText="flex-direction:column;align-items:flex-start;gap:8px";
      const h=el("div"); h.style.cssText="display:flex;align-items:center;gap:10px;width:100%";
      h.innerHTML='<div class="rt">'+res.n+'. '+esc(res.step)+'</div><div class="badge" style="margin-left:auto">'+
        esc(res.brain)+' Agent</div>';
      c.appendChild(h);
      const o=el("div","rs"); o.style.cssText="white-space:pre-wrap;line-height:1.6;color:var(--text)";
      o.textContent=res.output; c.appendChild(o);
      out.appendChild(c);
    });
    btn.disabled=false; inp.disabled=false;
  };
  btn.onclick=run; inp.onkeydown=e=>{if(e.key==="Enter")run();};
}

/* ---------------- görünüm yönetimi ---------------- */
function show(view){
  ["chat","mission","panel","biz","conn"].forEach(x=>{
    $("#view-"+x).classList.toggle("hidden",x!==view);
  });
  $("#composer").classList.toggle("hidden",view!=="chat");
  document.querySelectorAll(".nav button").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
  $("#viewTitle").textContent={chat:"Sohbet",mission:"Görev",panel:"Panel",biz:"İşletmeler",conn:"Bağlantılar"}[view];
  $("#side").classList.remove("open");
  if(view==="panel")renderPanel();
  if(view==="biz")renderBiz();
  if(view==="conn")renderConn();
  if(view==="mission")renderMission();
}

/* ---------------- onboarding ---------------- */
const BIZ_TYPES=[["personal","Kişisel Şirket"],["marketing_agency","Pazarlama Ajansı"],
  ["ecommerce","E-Ticaret"],["factory","Fabrika"],["restaurant","Restoran"],["saas","SaaS Girişimi"]];
const OB_TEAM=[["📈","Pazarlama"],["💰","Finans"],["🤝","Satış"],["🔬","Araştırma"],
  ["📦","Ürün"],["⚙️","Operasyon"],["🛠️","Mühendislik"],["🛡️","Güvenlik"]];
function dots(n,total){let s="";for(let i=0;i<total;i++)s+='<i class="'+(i<n?"on":"")+'"></i>';return s;}
function startOnboarding(addMode){
  const onb=$("#onb"),c=$("#obcard"); onb.classList.remove("hidden");
  let step=addMode?1:0; let createdName="";
  const render=()=>{
    if(step===0){
      c.innerHTML=`<div class="biglogo">M</div>
        <div class="steps">${dots(1,4)}</div>
        <h1>MIO'ya hoş geldin</h1>
        <p>Ben MIO — <b>yaşayan bir Executive işletim sistemi</b>, senin AI iş ortağın. Bana bir <b>hedef</b>
        verirsin; onu anlar, alt görevlere böler, <b>uzman brain'lerden bir ekip</b> kurar ve işi yürütürüm.
        Komut ezberlemezsin — doğal dille konuşursun.</p>
        <div class="obrow"><button class="btn" id="ob-next" style="flex:1">Başlayalım →</button></div>`;
      $("#ob-next").onclick=()=>{step=1;render();};
    }else if(step===1){
      c.innerHTML=`<div class="biglogo">🏢</div>
        <div class="steps">${dots(2,4)}</div>
        <h1>İlk işletmeni kur</h1>
        <p>MIO her işletmeni ayrı ve izole yönetir. Bir ad ver, türünü seç — departmanları ben hazırlarım.</p>
        <div class="field"><label>İşletme adı</label><input id="ob-name" placeholder="ör. Acme Pazarlama" autofocus></div>
        <div class="field"><label>Tür</label><select id="ob-type">${
          BIZ_TYPES.map(t=>`<option value="${t[0]}">${t[1]}</option>`).join("")}</select></div>
        <div class="obrow">
          ${addMode?'<button class="btn ghost" id="ob-cancel" style="flex:0 0 auto">Vazgeç</button>':''}
          <button class="btn" id="ob-create" style="flex:1">İşletmeyi kur</button></div>
        <div id="ob-err" style="color:var(--err);font-size:13px;margin-top:10px"></div>`;
      const nm=$("#ob-name"); nm.focus();
      if($("#ob-cancel"))$("#ob-cancel").onclick=()=>onb.classList.add("hidden");
      $("#ob-create").onclick=async()=>{
        const name=nm.value.trim(); if(!name){$("#ob-err").textContent="Bir ad girin.";return;}
        $("#ob-create").disabled=true; $("#ob-create").textContent="Kuruluyor…";
        const r=await api("/business","POST",{name,business_type:$("#ob-type").value});
        if(r.ok){ createdName=name; await refreshBiz();
          if(addMode){ localStorage.setItem("mio-onboarded","1"); onb.classList.add("hidden"); renderBiz(); }
          else { step=2; render(); }
        }else{$("#ob-err").textContent=(r.data&&r.data.error)||"Kurulamadı.";
          $("#ob-create").disabled=false;$("#ob-create").textContent="İşletmeyi kur";}
      };
      nm.onkeydown=e=>{if(e.key==="Enter")$("#ob-create").click();};
    }else if(step===2){
      // Paperclip modeli: MIO işletmeye CEO olur, brain-destekli ekibini tanıtır
      c.innerHTML=`<div class="biglogo">🧠</div>
        <div class="steps">${dots(3,4)}</div>
        <h1>MIO artık '${esc(createdName)}'in CEO'su</h1>
        <p>Bir hedef verdiğinde onu alt görevlere böler ve her birine uygun bir <b>uzman agent</b> atarım.
        Her agent bir <b>brain</b> tarafından desteklenir — MIO'nun farkı bu.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:4px 0 20px">
          ${OB_TEAM.map(t=>`<div class="row" style="padding:9px 12px;margin:0">
            <span style="font-size:16px">${t[0]}</span><span class="rt" style="font-size:13.5px">${t[1]} Agent</span></div>`).join("")}
        </div>
        <div class="obrow"><button class="btn" id="ob-next" style="flex:1">Ekibi tanıdım →</button></div>`;
      $("#ob-next").onclick=()=>{step=3;render();};
    }else{
      // İlk görev — hemen değer üret (aksiyon odaklı onboarding)
      c.innerHTML=`<div class="biglogo">🎯</div>
        <div class="steps">${dots(4,4)}</div>
        <h1>İlk hedefini ver</h1>
        <p>Bir hedef yaz — ekibim hemen çalışsın. Dilersen sonra 'Sohbet'ten de konuşabilirsin.</p>
        <div class="field"><input id="ob-goal" placeholder="ör. bu ay 100 yeni müşteri kazan" autofocus></div>
        <div class="obrow">
          <button class="btn ghost" id="ob-skip" style="flex:0 0 auto">Şimdilik geç</button>
          <button class="btn" id="ob-go" style="flex:1">MIO'ya yaptır →</button></div>`;
      const finish=()=>{ localStorage.setItem("mio-onboarded","1"); onb.classList.add("hidden"); };
      $("#ob-skip").onclick=()=>{ finish(); show("chat");
        addMsg("mio",`'${createdName}' hazır. Bir hedef ver ya da sohbet et — ekibimle iş yaparım.`); };
      $("#ob-go").onclick=()=>{ const g=$("#ob-goal").value.trim(); finish(); show("mission");
        if(g){ const inp=$("#mgoal"); if(inp){ inp.value=g; $("#mrun").click(); } } };
      $("#ob-goal").onkeydown=e=>{if(e.key==="Enter")$("#ob-go").click();};
    }
  };
  render();
}

/* ---------------- sesli konuşma (tarayıcı Web Speech API — anahtar/npx YOK, tr-TR) ---------------- */
function speak(text){
  if(!$("#ttsToggle").checked||!window.speechSynthesis||!text) return;
  const clean=text.replace(/\n+/g," ").slice(0,600);
  const u=new SpeechSynthesisUtterance(clean); u.lang="tr-TR"; u.rate=1.05;
  try{ speechSynthesis.cancel(); speechSynthesis.speak(u); }catch(e){}
}
let recog=null,listening=false;
(function initSpeech(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  const mic=$("#mic");
  if(!SR){ if(mic) mic.style.display="none"; return; }
  mic.style.background="var(--panel)"; mic.style.border="1px solid var(--line2)";
  recog=new SR(); recog.lang="tr-TR"; recog.interimResults=false; recog.maxAlternatives=1;
  recog.onresult=e=>{ const t=e.results[0][0].transcript; $("#input").value=t; autosize(); send(); };
  recog.onend=()=>{ listening=false; mic.textContent="🎤"; mic.style.background="var(--panel)"; };
  recog.onerror=()=>{ listening=false; mic.textContent="🎤"; mic.style.background="var(--panel)"; };
  mic.onclick=()=>{
    if(listening){ try{recog.stop();}catch(e){} return; }
    try{ if(window.speechSynthesis) speechSynthesis.cancel();
      recog.start(); listening=true; mic.textContent="🔴"; mic.style.background="var(--err)"; }
    catch(e){ listening=false; }
  };
})();

/* ---------------- girdi davranışı ---------------- */
function autosize(){const i=$("#input");i.style.height="auto";i.style.height=Math.min(i.scrollHeight,160)+"px";
  $("#send").disabled=!i.value.trim();}
$("#input").addEventListener("input",autosize);
$("#input").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});
$("#send").onclick=()=>send();
document.querySelectorAll(".sugg").forEach(b=>b.onclick=()=>send(b.textContent));
document.querySelectorAll(".nav button").forEach(b=>b.onclick=()=>show(b.dataset.view));
$("#menuBtn").onclick=()=>$("#side").classList.toggle("open");

/* ---------------- başlangıç ---------------- */
(async function boot(){
  await refreshStatus(); await refreshBiz();
  setInterval(refreshStatus,15000);
  const onboarded=localStorage.getItem("mio-onboarded")||STATE.businesses.length;
  if(!onboarded){ startOnboarding(false); }
  else{
    addMsg("mio","Merhaba, ben MIO — Executive işletim sistemin. "+
      (STATE.biz?`'${STATE.biz.name}' işletmeni yönetmeye hazırım. `:"")+
      "Ne yapmak istersin? Doğal dille konuş; gerisini ben organize ederim.");
  }
})();
</script>
</body>
</html>
"""

__all__ = ["WEBAPP_HTML"]
