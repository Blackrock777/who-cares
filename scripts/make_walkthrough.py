"""Italian walkthrough video with English captions, generated end to end.

  1. voice    ElevenLabs text-to-speech, one clip per scene (key in .env.elevenlabs, never printed)
  2. screen   Playwright drives web/index.html scene by scene, timed to each clip, with a visible
              cursor and English captions drawn into the page
  3. mix      ffmpeg places each clip at the moment its scene started and muxes an MP4 (+ .srt)

Run with a Python that has Playwright (the project venv only needs it for this script):
  python scripts/make_walkthrough.py            -> out/video/walkthrough_it.mp4, walkthrough_en.srt
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "video"
VOICE = "EXAVITQu4vr4xnSDxMaL"            # ElevenLabs premade voice, spoken through the multilingual model
MODEL = "eleven_multilingual_v2"
W, H = 1440, 900

SCENES = [
    {"id": "intro", "it": "Ciao! Siamo il team di Who Cares. La sfida si chiamava «Clienti che non esistono»: capire chi c'è dietro una campagna, prevederne i risultati e decidere dove investire. Tutto prima di spendere un euro.",
     "en": "Hi! We're the Who Cares team. The challenge was called 'Customers who don't exist': understand who is behind a campaign, predict its results and decide where to invest. All before spending a single euro."},
    {"id": "brands", "it": "Questa è la nostra dashboard. Ci sono tre brand: skincare, prodotti per animali e abbigliamento. Partiamo dalla domanda più difficile: chi sono le persone dietro ogni ad set?",
     "en": "This is our dashboard. There are three brands: skincare, pet products and clothing. Let's start with the hardest question: who are the people behind each ad set?"},
    {"id": "audience", "it": "Il pubblico non ci è stato dato, quindi siamo partiti da dati reali: migliaia di annunci italiani della Meta Ad Library, con la copertura per età e genere. Poi un modello bayesiano aggiorna la stima con il comportamento di ogni ad set: quanto clicca, quanto costa, quante volte rivede l'annuncio. Qui frequenza e costo alti indicano retargeting, non una fascia d'età. E quando i dati spostano poco la stima, lo diciamo.",
     "en": "We weren't given the audience, so we started from real data: thousands of Italian ads from the Meta Ad Library, with reach by age and gender. A Bayesian model then updates that estimate with each ad set's behaviour: how often it clicks, what it costs, how often people see the ad again. Here, high frequency and cost point to retargeting, not an age group. And when the data barely moves the estimate, we say so."},
    {"id": "crowd", "it": "Da questo mix nasce una folla simulata: cento persone, ognuna con la sua probabilità di clic.",
     "en": "From this mix we draw a simulated crowd: a hundred people, each with their own chance of clicking."},
    {"id": "forecast", "it": "Il cuore è la previsione: CTR e CPM per ogni annuncio, giorno per giorno, fino al Cyber Monday. Il modello è gerarchico, quindi un annuncio nuovo impara dal suo pubblico, dalla creatività e dal brand. Il Black Friday arriva da un indice di mercato, e la fascia mostra dove cadrà l'ottanta per cento dei giorni. Nelle due settimane di verifica abbiamo ridotto l'errore sul CTR dal trentatré al ventisei per cento.",
     "en": "The core is the forecast: CTR and CPM for every ad, day by day, up to Cyber Monday. The model is hierarchical, so a new ad learns from its audience, its creative and its brand. Black Friday comes from a market index, and the band shows where 80% of days will land. On the two validation weeks we cut CTR error from 33 to 26 percent."},
    {"id": "decide", "it": "Poi si decide. Sposto il budget e vedo subito clic, CPM e costo per clic. Se supero quanto l'ad set ha mai speso, il sistema avvisa che è un'estrapolazione. A destra: come spostare il budget, e quali creatività spingere nella Black Week.",
     "en": "Then you decide. I move the budget and instantly see clicks, CPM and cost per click. If I go beyond anything this ad set has spent, it warns that it's an extrapolation. On the right: how to shift budget, and which creatives to push in Black Week."},
    {"id": "lab", "it": "Nel laboratorio provo ogni creatività su ogni pubblico, e la mostro a mille persone simulate.",
     "en": "In the lab I try any creative on any audience, and show it to a thousand simulated people."},
    {"id": "studio", "it": "E poi lo studio creativo. Un modello linguistico scrive nuovi annunci dal brief, ma a giudicarli è il nostro modello di previsione, non l'intelligenza artificiale. Blocchiamo gli sconti oltre il limite e segnaliamo i numeri inventati: è successo in un annuncio su cinque. Risultato onesto: nessuno batte ancora i vincitori attuali, quindi il consiglio è testare, non sostituire.",
     "en": "And then the creative studio. A language model writes new ads from the brief, but our forecasting model judges them, not the AI. We block discounts above the limit and flag invented numbers: that happened in one ad in five. Honest result: none beats the current winners yet, so the advice is to test, not to replace."},
    {"id": "proof", "it": "Un solo dataset non basta. Così abbiamo creato sessanta aziende fittizie partendo da fonti reali. Il nostro motore batte il riferimento in cinquantotto casi, e riconosce il retargeting nel novantotto per cento.",
     "en": "One dataset isn't enough. So we built sixty fictional companies from real sources. Our engine beats the baseline in fifty-eight of them, and spots retargeting 98 percent of the time."},
    {"id": "close", "it": "E funziona per qualsiasi azienda, con un solo file di configurazione. I clienti non esistono. I loro clic sì. Grazie!",
     "en": "And it works for any company, with a single config file. The customers don't exist. Their clicks do. Thank you!"},
]


def key():
    for line in (ROOT / ".env.elevenlabs").read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("No ELEVENLABS_API_KEY in .env.elevenlabs")


def duration(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode())


def voice():
    k = key()
    for s in SCENES:
        p = OUT / f"{s['id']}.mp3"
        if not p.exists():
            body = {"text": s["it"], "model_id": MODEL,
                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}}
            req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
                                         data=json.dumps(body).encode(), headers={"xi-api-key": k, "Content-Type": "application/json"})
            p.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        s["dur"] = duration(p)
        print(f"  {s['id']:9s} {s['dur']:5.1f}s", flush=True)
    print(f"  total speech {sum(s['dur'] for s in SCENES):.1f}s")


CURSOR_JS = """
(() => { if (window.__cur) return; const c = document.createElement('div'); window.__cur = c;
  c.style.cssText = 'position:fixed;z-index:99999;width:22px;height:22px;border-radius:50%;background:rgba(27,26,23,.25);border:2px solid #1b1a17;pointer-events:none;transform:translate(-50%,-50%);transition:transform .12s;left:-50px;top:-50px';
  document.body.appendChild(c);
  addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => c.style.transform = 'translate(-50%,-50%) scale(.7)', true);
  addEventListener('mouseup', () => c.style.transform = 'translate(-50%,-50%)', true);
  const cap = document.createElement('div'); window.__cap = cap;
  cap.style.cssText = 'position:fixed;z-index:99998;left:50%;bottom:34px;transform:translateX(-50%);max-width:1100px;padding:10px 18px;border-radius:12px;background:rgba(20,20,18,.82);color:#fff;font:500 22px/1.35 Inter,system-ui,sans-serif;text-align:center;pointer-events:none;opacity:0;transition:opacity .2s';
  document.body.appendChild(cap);
  window.__setCap = t => { cap.textContent = t; cap.style.opacity = t ? 1 : 0; };
  window.__scrollTo = (sel, off, ms) => new Promise(res => { const el = document.querySelector(sel); const y0 = scrollY;
    const y1 = el.getBoundingClientRect().top + scrollY - off; const t0 = performance.now();
    const step = t => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2*k*k : 1 - Math.pow(-2*k + 2, 2) / 2; scrollTo(0, y0 + (y1 - y0) * e); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step); });
})();
"""


def chunks(text, n_max=95):
    """English caption chunks of at most ~2 short lines, split on sentence then clause boundaries."""
    import re
    parts = re.split(r"(?<=[.!?:])\s+", text)
    out = []
    for p in parts:
        while len(p) > n_max:
            cut = max(p.rfind(", ", 0, n_max), p.rfind(" ", 0, n_max))
            out.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        out.append(p)
    return [c for c in out if c]


def record():
    from playwright.sync_api import sync_playwright
    marks, subs = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT / "raw"), record_video_size={"width": W, "height": H},
                            color_scheme="light")
        ctx.add_init_script("try{localStorage.setItem('lang','it')}catch(e){}")
        pg = ctx.new_page()
        t0 = time.monotonic()
        pg.goto((ROOT / "web" / "index.html").as_uri())
        pg.wait_for_timeout(1200)
        pg.evaluate(CURSOR_JS)
        # pre-reveal everything once so cards are visible when we arrive
        pg.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('in'))")
        mouse = {"x": W * 0.7, "y": H * 0.5}

        def move(x, y, steps=25):
            pg.mouse.move(x, y, steps=steps)
            mouse.update(x=x, y=y)

        def center(sel, i=0):
            box = pg.locator(sel).nth(i).bounding_box()
            return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

        def click(sel, i=0):
            x, y = center(sel, i)
            move(x, y)
            pg.wait_for_timeout(250)
            pg.mouse.click(x, y)

        def scroll(sel, off=90, ms=1400):
            pg.evaluate(f"__scrollTo('{sel}', {off}, {ms})")
            pg.wait_for_timeout(ms + 150)

        def hover_dots(n=4):
            for i in [7, 33, 58, 81][:n]:
                x, y = center(".person", i)
                move(x, y, 12)
                pg.wait_for_timeout(700)

        actions = {
            "intro": lambda: (move(W * 0.75, H * 0.45, 40), pg.wait_for_timeout(1500), move(W * 0.62, H * 0.6, 40)),
            "brands": lambda: (scroll("#audience", 150), click("#switcher [data-b=CDF]"), pg.wait_for_timeout(900),
                               click("#switcher [data-b=FGR]"), pg.wait_for_timeout(900), click("#switcher [data-b=NDL]")),
            "audience": lambda: (pg.wait_for_timeout(1500), move(*center(".aud", 0)), pg.wait_for_timeout(3000), click(".aud", 3),
                                 pg.wait_for_timeout(2500), move(*center(".aud .chip.warm"))),
            "crowd": lambda: (scroll("#crowdPanel", 120), hover_dots()),
            "forecast": lambda: (scroll("#forecast", 70), click("#fcSets .pill", 0), pg.wait_for_timeout(5000), click("#fcKpi [data-k=cpm]"),
                                 pg.wait_for_timeout(1500), [move(W * f, H * 0.62, 10) or pg.wait_for_timeout(500) for f in (0.72, 0.78, 0.84, 0.88)]),
            "decide": lambda: (scroll("#decide", 60), decide_drag()),
            "lab": lambda: (scroll("#lab", 60), click("#heat td.c", 5), pg.wait_for_timeout(600), click("#simBtn")),
            "studio": lambda: (scroll("#studio", 40), pg.wait_for_timeout(2500), scroll("#stCands", 110, 1200), move(*center(".cand .range", 0)),
                               pg.wait_for_timeout(2500), move(*center(".cand .verdict", 0)), pg.wait_for_timeout(2000),
                               click(".cand [data-sim]", 0)),
            "proof": lambda: (scroll("#proof", 40), pg.wait_for_timeout(1500), scroll("#proofGrid", 110, 1000), move(*center(".pf", 1)),
                              pg.wait_for_timeout(1800), move(*center(".pf", 4))),
            "close": lambda: (scroll("main", 0, 1800), move(W * 0.7, H * 0.45, 40)),
        }

        def decide_drag():
            x0, y0 = center("#wiR")
            box = pg.locator("#wiR").bounding_box()
            sx = box["x"] + box["width"] * (0.75 / 2.75)          # thumb position at 1.0x
            move(sx, y0)
            pg.mouse.down()
            for k in range(1, 31):
                pg.mouse.move(sx + box["width"] * 0.24 * k / 30, y0)
                pg.wait_for_timeout(50)
            pg.mouse.up()
            pg.wait_for_timeout(1500)
            move(*center("#moves"))

        for s in SCENES:
            start = time.monotonic() - t0
            marks.append(start)
            cs = chunks(s["en"])
            tot = sum(len(c) for c in cs)
            tc = start
            for c in cs:
                d = s["dur"] * len(c) / tot
                subs.append((tc, tc + d, c))
                tc += d
            # captions run on their own timer inside the page so they stay in sync while actions run
            sched = [[(subs[-len(cs) + j][0] - start) * 1000, c] for j, c in enumerate(cs)]
            pg.evaluate("s => { s.forEach(([ms, t]) => setTimeout(() => __setCap(t), ms)); }", sched)
            actions[s["id"]]()
            left = start + s["dur"] + 0.35 - (time.monotonic() - t0)
            if left > 0:
                pg.wait_for_timeout(int(left * 1000))
            print(f"  scene {s['id']:9s} at {start:6.1f}s  (ran {time.monotonic() - t0 - start:4.1f}s for {s['dur']:4.1f}s audio)", flush=True)
        pg.evaluate("__setCap('')")
        pg.wait_for_timeout(1200)
        end = time.monotonic() - t0
        video = pg.video.path()
        ctx.close()
        b.close()
    return marks, subs, end, video


def srt(subs, path):
    f = lambda t: "%02d:%02d:%02d,%03d" % (t // 3600, t % 3600 // 60, t % 60, (t % 1) * 1000)
    path.write_text("\n".join(f"{i + 1}\n{f(a)} --> {f(b)}\n{t}\n" for i, (a, b, t) in enumerate(subs)), encoding="utf-8")


def mix(marks, end, video):
    inputs, filt = ["-i", str(video)], []
    for i, (s, m) in enumerate(zip(SCENES, marks)):
        inputs += ["-i", str(OUT / f"{s['id']}.mp3")]
        filt.append(f"[{i + 1}:a]adelay={int(m * 1000)}|{int(m * 1000)}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(SCENES))) + f"amix=inputs={len(SCENES)}:normalize=0,apad[aout]")
    out = OUT / "walkthrough_it.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[aout]",
                    "-t", f"{end:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("voice:")
    voice()
    print("screen:")
    marks, subs, end, video = record()
    srt(subs, OUT / "walkthrough_en.srt")
    out = mix(marks, end, video)
    print(f"wrote {out} ({duration(out):.1f}s) and walkthrough_en.srt")
