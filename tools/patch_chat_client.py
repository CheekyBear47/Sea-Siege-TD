# Client: Global Chat drawer + mini-profile cards with a working trade request,
# profile-picture selection, and a Forfeit button during a run.
import pathlib

p = pathlib.Path("index.html")
s = p.read_text(encoding="utf-8")
miss = []


def sub(old, new, why=""):
    global s
    if old not in s:
        miss.append(why or old[:70])
        return
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ markup
sub("""    <button class="top-btn" id="top-trade">🤝 <span>Trading &amp; Players</span></button>""",
    """    <button class="top-btn" id="top-trade">🤝 <span>Trading &amp; Players</span></button>
    <button class="top-btn" id="top-chat">💬 <span>Global Chat</span></button>""", "chat tab")

sub("""    <div id="profile"><div class="box">""",
    """    <div id="chat"><div class="box">
      <div class="board-head">
        <div class="pf-head">
          <h2>💬 Global Chat</h2>
          <div class="pf-id" id="chat-status">loading…</div>
        </div>
        <button class="btn tiny" id="chat-x" style="width:auto;padding:5px 10px">✕ Close</button>
      </div>
      <div id="chat-body" class="chat-body"></div>
      <div class="chat-send">
        <input id="chat-input" maxlength="240" placeholder="Say something to the harbour…" />
        <button class="btn primary" id="chat-send">Send</button>
      </div>
      <div class="board-foot">
        <span class="hint" style="flex:1;align-self:center">Tap any captain to see their card and send a trade request.</span>
      </div>
    </div></div>
    <div id="mini" class="mini-card"></div>
    <div id="profile"><div class="box">""", "chat overlay")

sub("""      <div class="sect2">Lifetime stats</div>""",
    """      <div class="sect2">Profile picture</div>
      <div class="pfp-row" id="pfp-row"></div>
      <div class="sect2">Lifetime stats</div>""", "pfp picker")

sub("""      <button class="btn tiny" id="btn-rush">⏩ Speed ×1</button>
    </div>""",
    """      <button class="btn tiny" id="btn-rush">⏩ Speed ×1</button>
    </div>
    <button class="btn tiny danger" id="btn-forfeit" style="margin-top:6px" disabled>🏳 Forfeit run</button>""",
    "forfeit button")

# ------------------------------------------------------------------ styles
sub("""  /* ============================ phones & tablets ============================""",
    """  /* ---------------------------- chat & mini-profile ------------------------ */
  #chat{
    position:absolute;inset:0;display:none;justify-items:center;align-items:start;border-radius:16px;z-index:6;
    background:radial-gradient(700px 460px at 50% 30%, rgba(10,24,40,.88), rgba(3,6,11,.96));
    backdrop-filter:blur(5px);padding:16px 0 20px;overflow:auto;
  }
  #chat.on{display:grid}
  #chat .box{
    text-align:left;padding:18px 22px 14px;border-radius:18px;max-width:760px;width:min(94%,760px);
    max-height:92%;overflow:hidden;display:flex;flex-direction:column;gap:10px;
    background:var(--glass);border:1px solid var(--stroke);
  }
  #chat h2{margin:0;font-size:20px;letter-spacing:3px;text-transform:uppercase}
  .chat-body{display:flex;flex-direction:column;gap:8px;overflow-y:auto;flex:1 1 auto;
    min-height:180px;max-height:52vh;padding-right:4px;-webkit-overflow-scrolling:touch}
  .chat-row{display:flex;gap:9px;align-items:flex-start;padding:8px 10px;border-radius:12px;
    background:rgba(255,255,255,.035);border:1px solid var(--stroke);cursor:pointer}
  .chat-row:hover{background:rgba(120,180,255,.1)}
  .chat-row.mine{border-color:rgba(87,224,138,.4);background:rgba(30,70,50,.28)}
  .chat-row .avatar{flex:0 0 auto}
  .chat-main{min-width:0;flex:1 1 auto}
  .chat-top{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
  .chat-name{font-weight:800;font-size:12px;color:#eaf6ff}
  .chat-worth{font-size:10px;color:#ffd166;font-weight:700;white-space:nowrap}
  .chat-time{font-size:9.5px;color:var(--dim);margin-left:auto;white-space:nowrap}
  .chat-text{font-size:12px;color:#dceaf7;line-height:1.45;margin-top:3px;overflow-wrap:anywhere}
  .chat-send{display:flex;gap:8px;align-items:center}
  .chat-send input{
    flex:1 1 auto;min-width:0;padding:10px 12px;border-radius:11px;font:inherit;font-size:12.5px;
    color:var(--txt);background:rgba(8,16,28,.7);border:1px solid var(--stroke);
  }
  .chat-empty{color:var(--dim);font-size:11.5px;padding:14px 4px;text-align:center}
  .mini-card{
    position:fixed;z-index:40;display:none;width:min(300px,88vw);padding:14px;border-radius:16px;
    background:linear-gradient(160deg, rgba(28,44,72,.97), rgba(10,18,32,.97));
    border:1px solid var(--stroke);box-shadow:0 22px 50px rgba(0,0,0,.6);
  }
  .mini-card.on{display:block}
  .mini-top{display:flex;align-items:center;gap:11px;margin-bottom:10px}
  .mini-name{font-weight:800;font-size:14px;color:#eaf6ff}
  .mini-sub{font-size:10.5px;color:var(--dim)}
  .mini-stats{display:grid;grid-template-columns:repeat(2,1fr);gap:7px;margin:10px 0}
  .mini-stats div{padding:7px 9px;border-radius:10px;background:var(--glass-2);border:1px solid var(--stroke)}
  .mini-stats small{display:block;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:var(--dim)}
  .mini-stats b{font-size:13px;color:#eaf6ff}
  .mini-actions{display:flex;gap:7px;margin-top:4px}
  .pfp-row{display:flex;flex-wrap:wrap;gap:7px;margin:2px 0 4px}
  .pfp{
    width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:19px;cursor:pointer;
    background:linear-gradient(150deg, rgba(45,90,140,.5), rgba(16,32,52,.55));border:1px solid var(--stroke);
  }
  .pfp:hover{filter:brightness(1.25)}
  .pfp.on{border-color:#57e08a;box-shadow:0 0 0 1px rgba(87,224,138,.6)}
  .btn.danger{border-color:rgba(255,120,120,.45);color:#ffd7d7}
  .btn.danger:disabled{opacity:.45}
  /* ============================ phones & tablets ============================""", "chat styles")

# ------------------------------------------------------------------ behaviour
sub("""function renderCratesPanel() {""",
    """/* --------------------------- global chat ---------------------------------- */
// Worth is what the SERVER computed from the account's own save; the client never gets
// to assert its own net worth.
let CHAT = { messages: [], at: 0, timer: null, open: false };
const PFP_CHOICES = ["⚓", "🐋", "🦈", "🧭", "⚔️", "🏴‍☠️", "🐙", "🔱", "🦀", "🌊", "🗺️", "🔭"];
function chatTime(at) {
  const d = new Date(at || Date.now());
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function renderChat() {
  const body = document.getElementById("chat-body");
  if (!body) return;
  const status = document.getElementById("chat-status");
  const acct = activeAccount();
  if (status) {
    status.textContent = CHAT.messages.length + " message" + (CHAT.messages.length === 1 ? "" : "s") +
      (acct ? " · you are " + acct.name + " · ⭐ " + fmtNum(worthTotal()) + " net worth" : " · sign in to talk");
  }
  body.textContent = "";
  if (!CHAT.messages.length) {
    body.appendChild(el("div", "chat-empty", "Nobody has said anything yet. Be the first."));
    return;
  }
  const me = acct ? acct.id : null;
  CHAT.messages.forEach(m => {
    const row = el("div", "chat-row" + (m.id === me ? " mine" : ""));
    const av = el("span", "avatar sm");
    paintAvatar(av, { id: m.id, name: m.name, avatar: m.avatar });
    row.appendChild(av);
    const main = el("div", "chat-main");
    const top = el("div", "chat-top");
    top.appendChild(el("span", "chat-name", m.name || "Captain"));
    top.appendChild(el("span", "chat-worth", "⭐ " + fmtNum(m.worth || 0) + " net worth"));
    top.appendChild(el("span", "chat-time", chatTime(m.at)));
    main.appendChild(top);
    main.appendChild(el("div", "chat-text", m.body));
    row.appendChild(main);
    row.title = "Tap to open " + (m.name || "Captain") + "'s card";
    row.onclick = () => openMini(m);
    body.appendChild(row);
  });
  body.scrollTop = body.scrollHeight;
}
function loadChat() {
  return apiGet("/api/chat").then(j => {
    if (j && j.ok) { CHAT.messages = j.messages || []; CHAT.at = Date.now(); }
    if (CHAT.open) renderChat();
    return j;
  }).catch(() => null);
}
function pushChat(msg) {
  if (!msg) return;
  CHAT.messages.push(msg);
  if (CHAT.messages.length > 120) CHAT.messages = CHAT.messages.slice(-120);
  if (CHAT.open) renderChat();
}
function sendChat() {
  const input = document.getElementById("chat-input");
  const text = (input.value || "").trim();
  if (!text) return;
  if (!activeAccount()) { toast("Sign in to talk in the chat."); return; }
  input.value = "";
  const token = (readSession() || {}).token;
  api("/api/chat/send", { token: token, body: text }, 12000)
    .then(j => { if (j && j.msg) pushChat(j.msg); })
    .catch(e => { toast("Could not send: " + (e.message || e)); input.value = text; });
}
// The mini-profile: name, worth, presence, and a working trade request.
function openMini(m) {
  const card = document.getElementById("mini");
  if (!card) return;
  const players = (NET && NET.players) || [];
  const online = players.find(p => (m.prof && p.prof === m.prof) || (!m.prof && p.name === m.name));
  card.textContent = "";
  const top = el("div", "mini-top");
  const av = el("span", "avatar lg");
  paintAvatar(av, { id: m.id, name: m.name, avatar: m.avatar });
  top.appendChild(av);
  const idBox = el("div");
  idBox.appendChild(el("div", "mini-name", m.name || "Captain"));
  idBox.appendChild(el("div", "mini-sub",
    (m.provider === "google" ? "🔐 Google account" : "🔑 Username account") +
    (online ? " · online now" : " · offline")));
  top.appendChild(idBox);
  card.appendChild(top);
  const stats = el("div", "mini-stats");
  [["Net worth", "⭐ " + fmtNum(m.worth || 0)],
   ["Status", online ? "🟢 in the hub" : "⚪ not connected"]].forEach(([k, v]) => {
    const d = el("div");
    d.appendChild(el("small", null, k));
    d.appendChild(el("b", null, v));
    stats.appendChild(d);
  });
  card.appendChild(stats);
  const actions = el("div", "mini-actions");
  const trade = el("button", "btn primary tiny", online ? "🤝 Send trade request" : "🤝 Trade request");
  trade.disabled = !online;
  trade.title = online ? "Ask " + m.name + " to trade"
    : "Trade requests need them online — they are offline right now";
  trade.onclick = () => {
    if (!online) return;
    if (!activeAccount()) { toast("Sign in to send trade requests."); return; }
    netSignal("trade-request", { to: online.id })
      .then(() => toast("Trade request sent to " + m.name + " — they will see it up top."))
      .catch(e => toast("Could not send that request: " + (e.message || e)));
    closeMini();
  };
  actions.appendChild(trade);
  const close = el("button", "btn tiny", "Close");
  close.onclick = closeMini;
  actions.appendChild(close);
  card.appendChild(actions);
  card.classList.add("on");
  // keep the card on screen, near the tapped message
  const w = card.offsetWidth || 300, h = card.offsetHeight || 180;
  const x = Math.min(Math.max(10, (window.innerWidth - w) / 2), window.innerWidth - w - 10);
  const y = Math.min(Math.max(64, window.innerHeight / 2 - h / 2), window.innerHeight - h - 10);
  card.style.left = Math.round(x) + "px";
  card.style.top = Math.round(y) + "px";
}
function closeMini() {
  const card = document.getElementById("mini");
  if (card) card.classList.remove("on");
}
function showChat(on) {
  const visible = on !== false;
  if (visible) closeOverlays("chat");
  document.getElementById("chat").classList.toggle("on", visible);
  CHAT.open = visible;
  if (visible) {
    renderChat();
    loadChat();
    if (CHAT.timer) clearInterval(CHAT.timer);
    CHAT.timer = setInterval(loadChat, 10000);      // and SSE appends live between polls
  } else {
    closeMini();
    if (CHAT.timer) { clearInterval(CHAT.timer); CHAT.timer = null; }
  }
  syncTopTabs();
}
/* ------------------------ profile pictures -------------------------------- */
function renderPfp() {
  const row = document.getElementById("pfp-row");
  if (!row) return;
  const acct = activeAccount();
  row.textContent = "";
  const current = acct && acct.avatar;
  PFP_CHOICES.forEach(g => {
    const b = el("div", "pfp" + (current === g ? " on" : ""), g);
    b.title = "Use " + g + " as your profile picture";
    b.onclick = () => setPfp(g);
    row.appendChild(b);
  });
  const gpic = googlePicFor(acct);
  if (gpic) {
    const g = el("div", "pfp" + (current === gpic ? " on" : ""), "G");
    g.title = "Use your Google picture";
    g.onclick = () => setPfp("google");
    row.appendChild(g);
  }
  if (current) {
    const none = el("div", "pfp", "∅");
    none.title = "No picture";
    none.onclick = () => setPfp("");
    row.appendChild(none);
  }
}
// Google hands us a picture URL at sign-in. Remember it per account so switching to a
// glyph does not throw it away for good.
const GPIC_KEY = "seaSiege.gpic.v1";
function rememberGooglePic(acct) {
  try {
    if (acct && acct.id && typeof acct.avatar === "string" && /^https?:/.test(acct.avatar)) {
      const db = JSON.parse(localStorage.getItem(GPIC_KEY) || "{}");
      if (db[acct.id] !== acct.avatar) {
        db[acct.id] = acct.avatar;
        localStorage.setItem(GPIC_KEY, JSON.stringify(db));
      }
    }
  } catch (e) { /* private mode: the picker just won't offer it */ }
}
function googlePicFor(acct) {
  try { return (JSON.parse(localStorage.getItem(GPIC_KEY) || "{}"))[(acct || {}).id] || null; }
  catch (e) { return null; }
}
function setPfp(choice) {
  const acct = activeAccount();
  if (!acct) { toast("Sign in to choose a profile picture."); return; }
  let avatar;
  if (choice === "google") {
    avatar = googlePicFor(acct);
    if (!avatar) { toast("No Google picture on file for this account."); return; }
  } else {
    avatar = choice || null;
  }
  api("/api/account/avatar", { token: (readSession() || {}).token, avatar: avatar }, 12000)
    .then(j => {
      if (j && j.account) {
        // mirror the updated account locally, exactly as the other account replies do
        const db = loadAccounts();
        db.accounts[j.account.id] = Object.assign({}, db.accounts[j.account.id] || {}, j.account);
        saveAccounts(db);
      } else if (activeAccount()) {
        activeAccount().avatar = avatar;
      }
      paintAvatar(document.getElementById("chip-avatar"), activeAccount());
      paintAvatar(document.getElementById("pf-avatar"), activeAccount());
      renderPfp();
      renderTopBar();
      toast(avatar ? "Profile picture updated." : "Profile picture cleared.");
    })
    .catch(e => toast("Could not save that picture: " + (e.message || e)));
}
function renderCratesPanel() {""", "chat js")

# live messages over the existing event stream (no polling lag between refreshes)
sub("""    case "trade-invite":
      showInvite(d);
      break;""",
    """    case "chat":
      pushChat(d.msg);
      break;
    case "trade-invite":
      showInvite(d);
      break;""", "sse chat case")

# capture the Google picture whenever an avatar is painted (covers sign-in too)
sub("""function paintAvatar(host, acct) {""",
    """function paintAvatar(host, acct) {
  rememberGooglePic(acct);""", "capture google pic")

# the panel renders the picker with the rest of the profile
sub("""  paintAvatar(document.getElementById("pf-avatar"), acct);""",
    """  paintAvatar(document.getElementById("pf-avatar"), acct);
  renderPfp();""", "render pfp in profile")

# wire the buttons
sub("""document.getElementById("crates-x").onclick = () => showCrates(false);""",
    """document.getElementById("top-chat").onclick = () => toggleOverlay("chat");
document.getElementById("chat-x").onclick = () => showChat(false);
document.getElementById("chat-send").onclick = sendChat;
document.getElementById("chat-input").addEventListener("keydown", ev => {
  if (ev.key === "Enter") { ev.preventDefault(); sendChat(); }
});
document.getElementById("crates-x").onclick = () => showCrates(false);""", "chat wiring")

# overlay bookkeeping
sub("""const OVERLAY_IDS = ["board", "crates", "inv", "trade", "profile"];""",
    """const OVERLAY_IDS = ["board", "crates", "inv", "trade", "chat", "profile"];""", "overlay ids")

sub("""  [["top-board", "board"], ["top-crates", "crates"], ["top-inv", "inv"], ["top-trade", "trade"],
   ["top-profile", "profile"]]""",
    """  [["top-board", "board"], ["top-crates", "crates"], ["top-inv", "inv"], ["top-trade", "trade"],
   ["top-chat", "chat"], ["top-profile", "profile"]]""", "syncTopTabs")

sub("""  else if (id === "trade") showTrade(!open);""",
    """  else if (id === "trade") showTrade(!open);
  else if (id === "chat") showChat(!open);""", "toggleOverlay chat")

# forfeit: two-tap, only during a live run
sub("""document.getElementById("btn-pause").onclick = () => { G.paused = !G.paused; ui(); };""",
    """document.getElementById("btn-pause").onclick = () => { G.paused = !G.paused; ui(); };
// Forfeit: end the run on purpose. Two taps, because it throws the run away.
const forfeitBtn = document.getElementById("btn-forfeit");
forfeitBtn.onclick = () => armConfirm(forfeitBtn, "🏳 Forfeit run — tap again", () => {
  if (G.over) return;
  sfx("deny");
  banner("Run forfeited", "#ff9f9f");
  toast("Run forfeited at wave " + G.wave + " — recorded as a loss, not a best.");
  endGame(false);
});""", "forfeit wiring")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
