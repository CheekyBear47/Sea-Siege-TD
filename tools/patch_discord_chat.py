# Discord-style chat: compact dark rows, author headers grouped like Discord, worth
# badges, smooth auto-scroll that respects a reader who scrolled up.
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


# ------------------------------------------------------------------ styles
sub("""  #chat{
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
  }""",
    """  /* ---- Discord-style chat: dark, compact, grouped message rows ---- */
  #chat{
    position:absolute;inset:0;display:none;justify-items:center;align-items:start;border-radius:16px;z-index:6;
    background:radial-gradient(700px 460px at 50% 30%, rgba(8,12,20,.9), rgba(2,3,6,.97));
    backdrop-filter:blur(5px);padding:16px 0 20px;overflow:auto;
  }
  #chat.on{display:grid}
  #chat .box{
    text-align:left;padding:0;border-radius:16px;max-width:880px;width:min(96%,880px);
    max-height:92%;overflow:hidden;display:flex;flex-direction:column;gap:0;
    background:#0d1117;border:1px solid rgba(255,255,255,.07);
    box-shadow:0 26px 60px rgba(0,0,0,.7);
  }
  #chat .board-head{padding:14px 18px 12px;margin:0;border-bottom:1px solid rgba(255,255,255,.06)}
  #chat h2{margin:0;font-size:16px;letter-spacing:.4px;text-transform:none;color:#f2f3f5}
  #chat .pf-id{font-size:11px;color:#8b93a1}
  #chat .board-foot{padding:10px 18px 14px;margin:0;border-top:1px solid rgba(255,255,255,.06)}
  .chat-body{display:flex;flex-direction:column;overflow-y:auto;flex:1 1 auto;
    min-height:200px;max-height:56vh;padding:12px 8px 16px 18px;-webkit-overflow-scrolling:touch;
    scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.14) transparent}
  .chat-body::-webkit-scrollbar{width:9px}
  .chat-body::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:9px}
  /* a grouped row carries no header, Discord-style */
  .chat-row{display:block;padding:2px 10px 2px 8px;border-radius:5px;cursor:pointer;position:relative}
  .chat-row:hover{background:rgba(255,255,255,.045)}
  .chat-row.group-start{margin-top:14px}
  .chat-row.cont::before{
    content:"";position:absolute;left:18px;right:10px;top:-1px;height:1px;
    background:transparent;
  }
  .chat-row.cont{padding-left:52px}
  .chat-head{display:flex;align-items:center;gap:9px;min-width:0;margin-bottom:1px}
  .chat-row .avatar{flex:0 0 auto;width:30px;height:30px;font-size:12px}
  .chat-name{font-weight:700;font-size:13.5px;color:#f2f3f5}
  .chat-name.mine{color:#8ee6b0}
  .chat-worth{font-size:10px;color:#ffd166;font-weight:700;white-space:nowrap;
    padding:1px 7px;border-radius:7px;background:rgba(255,209,102,.1);border:1px solid rgba(255,209,102,.22)}
  .chat-time{font-size:10px;color:#7a8291;white-space:nowrap}
  .chat-text{font-size:13.5px;color:#dbdee1;line-height:1.45;overflow-wrap:anywhere;
    padding-left:39px;margin-top:-2px}
  .chat-row.cont .chat-text{padding-left:0}
  .chat-hint{font-size:10px;color:#5c6370;padding-left:39px;margin-top:2px}
  .chat-send{display:flex;gap:8px;align-items:center;padding:12px 18px 4px}
  .chat-send input{
    flex:1 1 auto;min-width:0;padding:11px 13px;border-radius:9px;font:inherit;font-size:13px;
    color:#f2f3f5;background:#1e232b;border:1px solid rgba(255,255,255,.06);
  }
  .chat-send input::placeholder{color:#6b7280}
  .chat-send .btn{border-radius:9px;background:#4b6bff;border-color:#4b6bff;color:#fff;font-weight:700}
  .chat-row .avatar{background:linear-gradient(150deg,#5865f2,#404ece)}""",
    "discord chat css")

# ------------------------------------------------------------------ grouping
sub("""function renderChat() {
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
}""",
    """// Discord reads best because consecutive messages from one author collapse into a
// single block: the header (avatar, name, worth badge, time) appears once, and the
// follow-up rows just indent. Clicking any row opens that captain's mini-profile.
const CHAT_GROUP_MS = 5 * 60 * 1000;
function renderChat() {
  const body = document.getElementById("chat-body");
  if (!body) return;
  const status = document.getElementById("chat-status");
  const acct = activeAccount();
  if (status) {
    status.textContent = CHAT.messages.length + " message" + (CHAT.messages.length === 1 ? "" : "s") +
      (acct ? " · signed in as " + acct.name + " · ⭐ " + fmtNum(worthTotal()) + " net worth"
            : " · sign in to talk");
  }
  // Only auto-scroll when the reader is already at the bottom: yanking the view while
  // somebody is reading history is the classic chat sin.
  const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 60;
  body.textContent = "";
  if (!CHAT.messages.length) {
    body.appendChild(el("div", "chat-empty", "Nobody has said anything yet. Be the first."));
    return;
  }
  const me = acct ? acct.id : null;
  let lastId = null, lastAt = 0;
  CHAT.messages.forEach(m => {
    const sameAuthor = m.id === lastId && (m.at || 0) - lastAt < CHAT_GROUP_MS;
    const row = el("div", "chat-row " + (sameAuthor ? "cont" : "group-start"));
    if (!sameAuthor) {
      const head = el("div", "chat-head");
      const av = el("span", "avatar sm");
      paintAvatar(av, { id: m.id, name: m.name, avatar: m.avatar });
      head.appendChild(av);
      head.appendChild(el("span", "chat-name" + (m.id === me ? " mine" : ""), m.name || "Captain"));
      head.appendChild(el("span", "chat-worth", "⭐ " + fmtNum(m.worth || 0)));
      head.appendChild(el("span", "chat-time", chatTime(m.at)));
      row.appendChild(head);
    }
    row.appendChild(el("div", "chat-text", m.body));
    row.title = "Open " + (m.name || "Captain") + "'s card";
    row.onclick = () => openMini(m);
    body.appendChild(row);
    lastId = m.id;
    lastAt = m.at || 0;
  });
  if (nearBottom) {
    requestAnimationFrame(() => {
      try { body.scrollTo({ top: body.scrollHeight, behavior: "smooth" }); }
      catch (e) { body.scrollTop = body.scrollHeight; }
    });
  }
}""", "discord grouping")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
