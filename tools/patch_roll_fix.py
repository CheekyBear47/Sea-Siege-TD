# Drive the crate roll off the render loop with wall-clock timing: setInterval is
# throttled hard on a backgrounded/hidden page, which left the overlay stuck on screen.
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


sub("""  const pool = [];
  RARITY_ORDER.forEach(r => cratePool(r).forEach(x => pool.push(x)));
  if (label) label.textContent = crate.glyph + " " + crate.name + " — rolling…";
  host.classList.add("on");
  let ticks = 0;
  const total = 24 + Math.floor(Math.random() * 10);
  const timer = setInterval(() => {
    const it = pool[(Math.random() * pool.length) | 0];
    if (it) {
      card.textContent = it.item.glyph || "🎁";
      card.className = "roll-card spin r-" + (it.item.r || "common");
    }
    ticks++;
    if (ticks < total) return;
    clearInterval(timer);
    reveal();
    setTimeout(() => {
      host.classList.remove("on");
      rolling = false;
      done();
    }, 1500);
  }, 70);
}""",
    """  const pool = [];
  RARITY_ORDER.forEach(r => cratePool(r).forEach(x => pool.push(x)));
  if (label) label.textContent = crate.glyph + " " + crate.name + " — rolling…";
  host.classList.add("on");
  const landed = () => {
    reveal();
    setTimeout(() => {
      host.classList.remove("on");
      rolling = false;
      done();
    }, 1200);
  };
  // Wall-clock, frame-driven. A tick-counting setInterval stalls on a throttled or
  // hidden page and the overlay would stay up (the drop is already in the hold).
  const started = Date.now();
  const SPIN = 1500, HOLD = 1400;
  const spray = () => {
    const it = pool[(Math.random() * pool.length) | 0];
    if (it) {
      card.textContent = it.item.glyph || "🎁";
      card.className = "roll-card spin r-" + (it.item.r || "common");
    }
  };
  const frame = () => {
    if (Date.now() - started >= SPIN) {
      clearInterval(safety);
      landed();
      return;
    }
    spray();
    requestAnimationFrame(frame);
  };
  const safety = setInterval(spray, 90);        // keeps spinning if rAF is throttled
  setTimeout(() => {                            // and never leave the overlay stuck
    if (rolling && Date.now() - started >= SPIN + HOLD) {
      clearInterval(safety);
      host.classList.remove("on");
      rolling = false;
      reveal();
      done();
    }
  }, SPIN + HOLD + 200);
  requestAnimationFrame(frame);
}""", "playRoll timing")

# the overlay belongs with the other stage overlays, not floating at page level
sub("""<div id="invites"></div>

<!-- Crate rolling animation: a spray of possible drops that settles on the real one -->
<div id="roll">
  <div class="roll-box">
    <div class="roll-card r-common" id="roll-card">📦</div>
    <div class="roll-label" id="roll-label">Rolling…</div>
  </div>
</div>""", """<div id="invites"></div>""", "roll overlay out")

sub("""    <div id="trade"><div class="box">""",
    """    <!-- Crate rolling animation: a spray of possible drops that settles on the real one -->
    <div id="roll"><div class="roll-box">
      <div class="roll-card r-common" id="roll-card">📦</div>
      <div class="roll-label" id="roll-label">Rolling…</div>
    </div></div>
    <div id="trade"><div class="box">""", "roll overlay in")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
