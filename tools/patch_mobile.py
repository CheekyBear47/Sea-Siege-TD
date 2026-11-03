# Make the game usable on phones and tablets: a scrolling single-column layout,
# touch input that never fights the page, and full-screen scrollable overlays.
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


# ------------------------------------------------------------------ viewport meta
sub("""<meta name="viewport" content="width=device-width, initial-scale=1" />""",
    """<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#0b1a2b" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />""", "viewport meta")

# ------------------------------------------------------------------ rotate hint
sub("""<body>
<header id="topbar">""",
    """<body>
<div class="rotate-hint">🔄 Tip: turn your phone sideways for a bigger harbour.</div>
<header id="topbar">""", "rotate hint")

# ------------------------------------------------------------------ responsive css
sub("""  @media (max-width:1080px){ #panel{width:290px;flex-basis:290px} }
</style>""",
    """  @media (max-width:1080px){ #panel{width:290px;flex-basis:290px} }

  /* ============================ phones & tablets ============================
     The desktop layout is a height-locked row (canvas + 330px panel). On a narrow
     screen that squeezes the canvas to nothing, so below 900px the page becomes a
     scrolling single column: canvas first, controls underneath, sticky top bar. */
  html,body{overscroll-behavior:none}
  canvas{touch-action:none;-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent}
  button,.btn,.pick,.top-btn,.atab{touch-action:manipulation}
  button,.btn,.pick,.top-btn,.atab{-webkit-tap-highlight-color:transparent}
  #panel,#topbar,.box,#crates .box,#inv .box{-webkit-overflow-scrolling:touch}
  .rotate-hint{
    display:none;align-items:center;gap:8px;margin:0;padding:8px 12px;font-size:11.5px;
    color:#cfe6ff;background:rgba(30,60,96,.55);border-bottom:1px solid var(--stroke);
  }

  @media (max-width:900px){
    html,body{height:auto;min-height:100%}
    body{display:block}
    #topbar{
      position:sticky;top:0;flex-wrap:wrap;gap:8px;row-gap:6px;
      padding:8px 10px;
      padding-top:calc(8px + env(safe-area-inset-top));
      padding-left:calc(10px + env(safe-area-inset-left));
      padding-right:calc(10px + env(safe-area-inset-right));
    }
    .brand{font-size:15px}
    .brand small{display:none}
    .top-btn{min-height:40px;padding:8px 11px;font-size:11.5px}
    .top-wallet{padding:6px 9px;font-size:11px}
    .top-status{display:none}
    #app{
      display:flex;flex-direction:column;align-items:stretch;gap:10px;padding:10px;
      padding-bottom:calc(26px + env(safe-area-inset-bottom));
    }
    /* an explicitly sized stage: fitCanvas() measures this box, so give it a shape */
    #stage{flex:0 0 auto;width:100%;aspect-ratio:16/9;height:auto;min-height:0}
    canvas{border-radius:12px}
    #panel{
      width:auto;flex:0 0 auto;max-height:none;overflow:visible;
      padding:12px;border-radius:14px;
    }
    /* overlays become true full-viewport sheets, so they stay put while the page scrolls */
    #board,#inv,#crates,#trade,#profile{position:fixed}
    #board .box,#inv .box,#crates .box,#trade .box,#profile .box{
      max-height:calc(100dvh - 96px);width:min(96%,1080px);
    }
    .cos-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
    .btn{min-height:38px}
    .btn.tiny{min-height:32px;padding:7px 11px}
    .pick{min-height:32px}
    .inv-selects select{min-height:34px}
  }
  @media (orientation:portrait) and (max-width:820px){ .rotate-hint{display:flex} }
  @media (max-width:430px){
    .cos-grid{grid-template-columns:1fr}
    #panel{padding:11px;gap:8px}
    .crate-odds span{font-size:10px;padding:3px 7px}
    .top-btn{padding:8px 10px}
  }
  /* a coarse pointer means fingers: never hover-only, always tappable */
  @media (pointer:coarse){
    .cos-card{padding:11px}
    .top-btn,.btn,.pick{min-height:40px}
  }
</style>""", "responsive css")

# ------------------------------------------------------------------ touch input
sub("""cv.addEventListener("touchstart", ev => {
  ev.preventDefault();
  audioInit();
  canvasClick(canvasPos(ev), 0);
}, { passive: false });""",
    """// Touch: a tap is a click, a drag follows the finger so the ghost/carried turret
// previews where it will land. touch-action:none on the canvas keeps the page still.
cv.addEventListener("touchstart", ev => {
  ev.preventDefault();
  audioInit();
  const p = canvasPos(ev);
  G.hover.x = p.x; G.hover.y = p.y;
  canvasClick(p, 0);
}, { passive: false });
cv.addEventListener("touchmove", ev => {
  ev.preventDefault();
  const p = canvasPos(ev);
  G.hover.x = p.x; G.hover.y = p.y;
}, { passive: false });
const touchEnd = ev => {
  if (ev && ev.cancelable) ev.preventDefault();
  G.hover.x = -999; G.hover.y = -999;
};
cv.addEventListener("touchend", touchEnd, { passive: false });
cv.addEventListener("touchcancel", touchEnd, { passive: false });
// iOS can still start a pinch/gesture over the canvas; the game wants none of it.
["gesturestart", "gesturechange", "gestureend"].forEach(n =>
  cv.addEventListener(n, ev => ev.preventDefault(), { passive: false }));""", "touch input")

# --------------------------------------------------------- keep the fit up to date
sub("""window.addEventListener("resize", fitCanvas);""",
    """window.addEventListener("resize", fitCanvas);
window.addEventListener("orientationchange", () => setTimeout(fitCanvas, 150));
if (window.visualViewport) window.visualViewport.addEventListener("resize", fitCanvas);
// The mobile layout depends on media queries, so re-fit after the browser has
// settled the new box (and once more after images/fonts land).
window.addEventListener("load", () => { setTimeout(fitCanvas, 60); setTimeout(fitCanvas, 400); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) fitCanvas(); });""",
    "fit listeners")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
