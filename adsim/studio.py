"""Creative studio: A language model proposes, the forecaster decides.

Flow (the brief's "per chi vuole spingere oltre"):
  1. evidence   what the trained model already knows about the target audience: which lever works
                there, its best current creatives, the inferred audience, the brand's own voice
  2. propose    Claude writes N candidate creatives as structured JSON in exactly the creative table's
                schema, restricted to levers and formats seen in training (the forecaster cannot
                score a lever it has never seen, so allowing one would produce a confident wrong number)
  3. check      deterministic guards: discount above the brief's maximum, lengths outside the
                training range, near-duplicates
  4. score      the same engine that made the forecasts scores every candidate in every audience of
                the brand, as a new ad from 16 Nov, with its 80% band. Claude's own opinion of how well
                an ad will do is never used.
  5. rank       by forecast CTR in the target audience, compared with the best creative already
                running there; novelty (distance to the nearest training creative in the encoder
                space) is reported, because far-from-training text is extrapolation

Run live:   python -m adsim.studio            (serves web/ and /api/generate on 127.0.0.1:8787)
Precompute: python scripts/run_studio.py      (writes out/studio/runs.json for the static page)
Needs an Anthropic API key in .env.anthropic (ANTHROPIC_API_KEY=...) or the environment.
"""
import json
import os
import re
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import Engine, load
from .creative import embed
from .population import AudienceModel, audience_effects

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-opus-5-5"
TEXT_FIELDS = ["headline", "testo_principale", "call_to_action", "descrizione_visual"]

SYSTEM = """You are the creative strategist inside an ad-forecasting tool for Italian e-commerce brands on Meta (Facebook and Instagram).

You write candidate ad creatives in Italian. A separate statistical model, trained on this brand's real results, will forecast click-through rate and price for every candidate; your candidates are only as good as that forecast says. So write ads that are different from each other in meaningful ways (lever, angle, format, opening visual), not ten rewrites of one idea, so the forecaster has real alternatives to choose between.

Rules:
- Use only the levers and formats offered in the schema. They are the ones the forecaster has seen; anything else cannot be scored.
- Stay inside the product facts and the maximum discount in the brief. Never invent a discount, a stock quantity, a price, a spending threshold, a deadline, a certification or a health claim that the brief does not state. If you need a number, use one from the brief; otherwise write the copy without it. A checker flags every number that is not in the brief.
- Match the brand's existing voice and the field lengths of its current creatives (given below).
- descrizione_visual describes what is on screen, concretely, as the brand's creatives do: subject, setting, what happens in the first two seconds, on-screen text. The forecaster reads it.
- durata_video_s is required for video (between 10 and 25 seconds) and must be null otherwise.
- call_to_action is one of the button labels Meta offers in Italian; the brand mostly uses "Acquista ora".
- rationale_en / rationale_it: one sentence, in English and in Italian, on which evidence the candidate responds to. It is shown to the user as your reasoning and is not used for scoring."""


def _schema(levers, formats, n):
    item = {"type": "object", "additionalProperties": False,
            "required": ["leva", "formato", "durata_video_s", "headline", "testo_principale", "call_to_action", "descrizione_visual", "rationale_en", "rationale_it"],
            "properties": {"leva": {"type": "string", "enum": levers}, "formato": {"type": "string", "enum": formats},
                           "durata_video_s": {"type": ["integer", "null"]}, "headline": {"type": "string"},
                           "testo_principale": {"type": "string"}, "call_to_action": {"type": "string", "enum": ["Acquista ora", "Scopri di più"]},
                           "descrizione_visual": {"type": "string"}, "rationale_en": {"type": "string"},
                           "rationale_it": {"type": "string"}}}
    return {"type": "json_schema", "schema": {"type": "object", "additionalProperties": False, "required": ["creatives"],
                                              "properties": {"creatives": {"type": "array", "items": item}}}}


# Free models are throttled upstream at random; OpenRouter tries these in order within one request.
# Probed on 15 Nov 2026: Nemotron Ultra answered in good Italian while both Gemma 4 endpoints were throttled.
OPENROUTER_DEFAULT = "nvidia/nemotron-3-ultra-550b-a55b:free,google/gemma-4-31b-it:free,inclusionai/ling-3.2-flash:free"


def _env(name, file):
    v = os.environ.get(name)
    f = ROOT / file
    if not v and f.exists():
        for line in f.read_text().splitlines():
            if line.strip().startswith(name + "="):
                v = line.split("=", 1)[1].strip().strip("'\"")
    return v or None


def backend():
    """Which language model proposes. The forecaster scores in every case, so a weaker proposer
    costs diversity and copy quality, never the honesty of the numbers.
      1. Claude      .env.anthropic   ANTHROPIC_API_KEY=...
      2. OpenRouter  .env.openrouter  OPENROUTER_API_KEY=...  (optional OPENROUTER_MODEL=..., default a free Gemma)
      3. Local       env STUDIO_BASE_URL (e.g. http://localhost:11434/v1 for Ollama) + STUDIO_MODEL, no key
    """
    k = _env("ANTHROPIC_API_KEY", ".env.anthropic")
    if k:
        return {"kind": "anthropic", "key": k, "model": MODEL}
    k = _env("OPENROUTER_API_KEY", ".env.openrouter")
    if k:
        return {"kind": "openai_compat", "key": k, "model": _env("OPENROUTER_MODEL", ".env.openrouter") or OPENROUTER_DEFAULT,
                "base_url": "https://openrouter.ai/api/v1"}
    if os.environ.get("STUDIO_BASE_URL"):
        return {"kind": "openai_compat", "key": os.environ.get("STUDIO_API_KEY"), "model": os.environ.get("STUDIO_MODEL", "gemma3:12b"),
                "base_url": os.environ["STUDIO_BASE_URL"].rstrip("/")}
    return None


def api_key():                                      # kept for callers that only need "is a proposer configured"
    return backend() is not None


class Studio:
    def __init__(self, config=ROOT / "configs" / "wevion_bighack.json"):
        self.b = load(config)
        h = self.b["history"]
        self.e = Engine(self.b["cfg"]).calibrate(h, self.b["creatives"]).fit(h, self.b["creatives"])
        self.cr = pd.concat([pd.read_csv(f) for f in sorted((ROOT / "data" / "raw" / "asset_creativi").glob("*.csv"))])
        self.adv = pd.read_csv(ROOT / "data" / "raw" / "inserzionisti.csv").set_index("inserzionista_id")
        vert = h.groupby("advertiser_id")["vertical"].first().to_dict()
        self.pop = AudienceModel().infer_all(audience_effects(h), vert.get)
        self.levers = sorted(self.cr["leva"].unique())
        self.formats = sorted(self.cr["formato"].unique())
        lens = self.cr[["headline", "testo_principale", "descrizione_visual"]].apply(lambda s: s.str.len())
        self.len_range = {c: (int(lens[c].min()), int(lens[c].max())) for c in lens}
        self.train_vecs, _ = embed(self.cr[TEXT_FIELDS].fillna("").astype(str).agg(". ".join, axis=1).tolist())
        # Novelty scale from the training creatives themselves: each one's similarity to its nearest
        # other creative. A candidate below the 10th percentile of that is further from the training
        # set than almost any training creative is from the rest: its forecast is extrapolation.
        t = self.train_vecs / np.linalg.norm(self.train_vecs, axis=1, keepdims=True)
        sim = t @ t.T
        np.fill_diagonal(sim, -1)
        nn = sim.max(1)
        self.novelty_scale = {"p10": float(np.quantile(nn, 0.1)), "p50": float(np.quantile(nn, 0.5))}
        self.lab = self._score_rows(self.cr.rename(columns={"asset_id": "creative_id"}))
        self._client = None

    # ---------- scoring ----------
    def _score_rows(self, creatives, prefix=""):
        """Forecast each creative in every audience of its brand over the future window, as a new ad."""
        c = creatives.copy()
        c["creative_id"] = prefix + c["creative_id"].astype(str)
        self.e.add_creatives(c)
        fut = self.b["future"]
        out = []
        for _, r in c.iterrows():
            adv_campaign = r.get("campaign_id") if isinstance(r.get("campaign_id"), str) else r["creative_id"].split("-")[0] + "-C1"
            base = fut[fut["advertiser_id"] == adv_campaign].drop_duplicates(["date", "audience_id"]).copy()
            base["creative_id"] = r["creative_id"]
            base["ad_id"] = "STUDIO|" + base["audience_id"] + "|" + r["creative_id"]
            base["age_days"] = (base["date"] - base["date"].min()).dt.days
            p = self.e.predict(base)
            g = p.groupby("audience_id").agg(ctr=("ctr", "mean"), ctr_lo=("ctr_lo", "mean"), ctr_hi=("ctr_hi", "mean"), cpm=("cpm", "mean"))
            for a, x in g.iterrows():
                out.append({"creative_id": r["creative_id"], "audience": a, "ctr": round(float(x.ctr), 4), "ctr_lo": round(float(x.ctr_lo), 4),
                            "ctr_hi": round(float(x.ctr_hi), 4), "cpm": round(float(x.cpm), 3), "cpc": round(float(x.cpm / (10 * x.ctr)), 3)})
        return pd.DataFrame(out)

    # ---------- evidence ----------
    def evidence(self, brand, audience):
        campaign = f"{brand}-C1"
        lab = self.lab.merge(self.cr[["asset_id", "leva", "formato"]].rename(columns={"asset_id": "creative_id"}), on="creative_id")
        la = lab[lab["audience"] == audience]
        by_lever = la.groupby("leva")["ctr"].mean().sort_values(ascending=False)
        by_format = la.groupby("formato")["ctr"].mean().sort_values(ascending=False)
        top = la.sort_values("ctr", ascending=False).head(3)
        own = self.cr[self.cr["asset_id"].str.startswith(brand)]
        p = self.pop.get(audience, {})
        return {"brand": brand, "campaign": campaign, "audience": audience, "brand_name": self.adv.loc[brand, "nome"],
                "brand_description": self.adv.loc[brand, "descrizione"], "vertical": self.adv.loc[brand, "vertical"],
                "audience_profile": {"headline": p.get("label", {}).get("headline"), "temperature": p.get("temperature"),
                                     "share_female": p.get("share_female", {}).get("mean"), "mean_age": p.get("mean_age", {}).get("mean"),
                                     "confidence": p.get("label", {}).get("confidence")},
                "lever_forecast_ctr": by_lever.round(3).to_dict(), "format_forecast_ctr": by_format.round(3).to_dict(),
                "best_existing": [dict(creative_id=r.creative_id, ctr=r.ctr, **own.set_index("asset_id").loc[r.creative_id, ["leva", "formato", "headline", "testo_principale", "descrizione_visual"]].to_dict())
                                  for r in top.itertuples()],
                "benchmark_ctr": float(top["ctr"].iloc[0]) if len(top) else None,
                "voice_examples": own.sample(min(6, len(own)), random_state=0)[["leva", "formato", "headline", "testo_principale", "call_to_action"]].to_dict("records"),
                "length_range_chars": self.len_range}

    # ---------- propose ----------
    def propose(self, brief, ev, n=6):
        b = backend()
        if b is None:
            raise RuntimeError("No language model configured: add .env.anthropic (ANTHROPIC_API_KEY=...) or .env.openrouter (OPENROUTER_API_KEY=...).")
        user = (f"Brand: {ev['brand_name']} ({ev['vertical']}). {ev['brand_description']}\n\n"
                f"Brief from the marketer:\n{json.dumps(brief, ensure_ascii=False, indent=1)}\n\n"
                f"Target audience {ev['audience']} as inferred by the tool (an estimate, not a fact): {json.dumps(ev['audience_profile'], ensure_ascii=False)}\n\n"
                f"What the forecaster expects in this audience from 16 Nov (mean forecast CTR %, by lever and by format):\n"
                f"levers {json.dumps(ev['lever_forecast_ctr'])}, formats {json.dumps(ev['format_forecast_ctr'])}\n\n"
                f"Best existing creatives in this audience (the bar to beat):\n{json.dumps(ev['best_existing'], ensure_ascii=False, indent=1)}\n\n"
                f"The brand's voice (sample of current creatives):\n{json.dumps(ev['voice_examples'], ensure_ascii=False, indent=1)}\n\n"
                f"Field lengths in characters across current creatives: {json.dumps(ev['length_range_chars'])}\n\n"
                f"Write {n} candidates. Cover at least two levers and at least two formats.")
        t = time.time()
        schema = _schema(self.levers, self.formats, n)
        if b["kind"] == "anthropic":
            items, meta = self._propose_anthropic(b, user, schema)
        else:
            items, meta = self._propose_openai_compat(b, user, schema)
        meta["seconds"] = round(time.time() - t, 1)
        items, dropped = self._validate(items)
        meta["dropped_invalid"] = dropped
        if not items:
            raise RuntimeError(f"The model returned no usable candidates ({dropped} malformed). Try again or switch model.")
        return items, meta

    def _validate(self, items):
        """Keep only candidates that match the creative schema. Free models break JSON contracts more
        often than Claude does; a malformed candidate is dropped and counted, never guessed at."""
        need = ["leva", "formato", "headline", "testo_principale", "call_to_action", "descrizione_visual"]
        ok, bad = [], 0
        for c in items if isinstance(items, list) else []:
            if not isinstance(c, dict) or any(not isinstance(c.get(k), str) or not c.get(k).strip() for k in need) \
                    or c["leva"] not in self.levers or c["formato"] not in self.formats:
                bad += 1
                continue
            d = c.get("durata_video_s")
            c["durata_video_s"] = int(d) if isinstance(d, (int, float)) or (isinstance(d, str) and d.isdigit()) else None
            c.setdefault("rationale_en", "")
            c.setdefault("rationale_it", c.get("rationale_en", ""))
            ok.append(c)
        return ok, bad

    def _propose_openai_compat(self, b, user, schema):
        """Any OpenAI-compatible chat endpoint: OpenRouter, Ollama, LM Studio, vLLM. JSON mode plus the
        schema in the prompt, because free models rarely support strict schemas; one retry on bad JSON."""
        import urllib.error
        import urllib.request
        sys_prompt = SYSTEM + "\n\nReturn only a JSON object that follows this JSON Schema exactly:\n" + json.dumps(schema["schema"], ensure_ascii=False)
        models = [m.strip() for m in b["model"].split(",") if m.strip()]
        body = {"model": models[0], "temperature": 0.9, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]}
        if "openrouter.ai" in b["base_url"] and len(models) > 1:
            body["models"] = models                      # OpenRouter fallback routing
        headers = {"Content-Type": "application/json", "X-Title": "adsim studio"}
        if b.get("key"):
            headers["Authorization"] = "Bearer " + b["key"]
        last = None
        for attempt in range(3):
            req = urllib.request.Request(b["base_url"] + "/chat/completions", data=json.dumps(body).encode(), headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    j = json.load(r)
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300].replace(b.get("key") or "\x00", "<key>")
                if e.code == 401:
                    raise RuntimeError("The API key was rejected. Check .env.openrouter.")
                if e.code == 429:
                    if attempt < 2:
                        time.sleep(10 * (attempt + 1))       # upstream throttling on free models is usually brief
                        continue
                    raise RuntimeError("Rate limited (free models are throttled upstream). Try again in a minute or set OPENROUTER_MODEL.")
                raise RuntimeError(f"Model endpoint error {e.code}: {msg}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"Could not reach {b['base_url']}: {e.reason}")
            except (TimeoutError, OSError) as e:                # slow free endpoints: retry, then give up cleanly
                last = e
                if attempt < 2:
                    continue
                raise RuntimeError(f"The model endpoint timed out ({e}). Try again.")
            if j.get("error"):
                raise RuntimeError(f"Model endpoint error: {str(j['error'])[:300]}")
            text = (j["choices"][0]["message"].get("content") or "").strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
            try:
                data = json.loads(text)
                items = data["creatives"] if isinstance(data, dict) else data
                u = j.get("usage") or {}
                return items, {"model": j.get("model", b["model"]), "input_tokens": u.get("prompt_tokens", 0),
                               "output_tokens": u.get("completion_tokens", 0), "request_id": j.get("id"), "backend": "openai_compat"}
            except (ValueError, KeyError, TypeError) as exc:
                last = exc
                body["messages"].append({"role": "assistant", "content": text[:4000]})
                body["messages"].append({"role": "user", "content": "That was not valid JSON matching the schema. Return only the JSON object."})
        raise RuntimeError(f"The model did not return valid JSON after a retry ({last}).")

    def _propose_anthropic(self, b, user, schema):
        import anthropic
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=b["key"])
        try:
            r = self._client.beta.messages.create(
                model=MODEL, max_tokens=16000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                thinking={"type": "adaptive"}, output_config={"effort": "high", "format": schema},
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}])
        except anthropic.AuthenticationError:
            raise RuntimeError("The Anthropic API key was rejected. Check .env.anthropic.")
        except anthropic.RateLimitError:
            raise RuntimeError("Rate limited by the Anthropic API. Try again in a minute.")
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"Anthropic API error {exc.status_code}: {exc.message}")
        except anthropic.APIConnectionError:
            raise RuntimeError("Could not reach the Anthropic API. Check the network.")
        if r.stop_reason == "refusal":
            raise RuntimeError("Claude declined this brief.")
        if r.stop_reason == "max_tokens":
            raise RuntimeError("The response was cut off; ask for fewer candidates.")
        text = next(blk.text for blk in r.content if blk.type == "text")
        meta = {"model": r.model, "input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens,
                "request_id": getattr(r, "_request_id", None), "backend": "anthropic"}
        return json.loads(text)["creatives"], meta

    # ---------- check ----------
    def check(self, cands, brief):
        """Deterministic guards. Language models, free ones especially, add concrete numbers (stock
        counts, thresholds, deadlines) that the brief never gave. Any number in the copy that is not
        in the brief is flagged for a human to confirm; a discount above the maximum is rejected."""
        maxd = brief.get("max_discount_pct")
        brief_nums = set(re.findall(r"\d+", " ".join(str(v) for v in brief.values() if v is not None)))
        out = []
        for c in cands:
            flags = []
            text = " ".join(str(c.get(k) or "") for k in TEXT_FIELDS)
            pcts = [int(x) for x in re.findall(r"(\d{1,2})\s?%", text)]
            if maxd is not None and any(p > maxd for p in pcts):
                flags.append({"code": "discount", "max": maxd, "found": max(pcts), "reject": True})
            copy = " ".join(str(c.get(k) or "") for k in ("headline", "testo_principale"))
            pct_vals = {m for m in re.findall(r"(\d{1,2})\s?%", copy)}
            unsupported = sorted({n for n in re.findall(r"\d+", copy)} - brief_nums - {p for p in pct_vals if maxd is not None and int(p) <= maxd}, key=int)
            if unsupported:
                flags.append({"code": "claim", "nums": unsupported})
            for k, (lo, hi) in self.len_range.items():
                L = len(str(c.get(k) or ""))
                if L > hi * 1.3 or L < lo * 0.6:
                    flags.append({"code": "length", "field": k, "len": L, "lo": lo, "hi": hi})
            if c["formato"] == "video" and not c.get("durata_video_s"):
                c["durata_video_s"] = 16
                flags.append({"code": "video_duration", "set": 16})
            if c["formato"] != "video":
                c["durata_video_s"] = None
            c["flags"] = flags
            c["rejected"] = any(f.get("reject") for f in flags)
            out.append(c)
        vecs, _ = embed([" . ".join(str(c.get(k) or "") for k in TEXT_FIELDS) for c in out])
        if vecs is not None and len(out):
            v = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
            t = self.train_vecs / np.linalg.norm(self.train_vecs, axis=1, keepdims=True)
            near = v @ t.T
            for i, c in enumerate(out):
                j = int(near[i].argmax())
                c["nearest_training"] = {"creative_id": self.cr["asset_id"].iloc[j], "similarity": round(float(near[i, j]), 3)}
                q = self.novelty_scale
                c["novelty"] = "typical" if near[i, j] >= q["p50"] else "within" if near[i, j] >= q["p10"] else "beyond"
                for k in range(i):
                    if float(v[i] @ v[k]) > 0.95 and not out[k].get("duplicate_of"):
                        c["duplicate_of"] = k
        return out

    # ---------- the whole flow ----------
    def run(self, brand, audience, brief, n=6):
        ev = self.evidence(brand, audience)
        cands, meta = self.propose(brief, ev, n)
        cands = self.check(cands, brief)
        stamp = f"G{int(time.time() * 1000) % 10**8}"
        rows = []
        for i, c in enumerate(cands):
            rows.append(dict(c, creative_id=f"{brand}-{stamp}-{i + 1}", asset_id=f"{brand}-{stamp}-{i + 1}", campaign_id=f"{brand}-C1",
                             vertical=ev["vertical"]))
        df = pd.DataFrame(rows)
        ok = df[~df["rejected"]]
        scores = self._score_rows(ok[["creative_id", "campaign_id"] + TEXT_FIELDS + ["leva", "formato", "durata_video_s"]]) if len(ok) else pd.DataFrame()
        res = []
        for r in rows:
            s = scores[scores["creative_id"] == r["creative_id"]] if len(scores) else pd.DataFrame()
            tgt = s[s["audience"] == audience]
            res.append({k: r.get(k) for k in ["creative_id", "leva", "formato", "durata_video_s", "headline", "testo_principale", "call_to_action",
                                              "descrizione_visual", "rationale_en", "rationale_it", "flags", "rejected", "novelty", "nearest_training", "duplicate_of"]}
                       | {"target": tgt.iloc[0].drop(["creative_id", "audience"]).to_dict() if len(tgt) else None,
                          "by_audience": s.drop(columns=["creative_id"]).to_dict("records")})
        res.sort(key=lambda x: -(x["target"]["ctr"] if x["target"] else -1))
        bench = ev["benchmark_ctr"]
        for i, x in enumerate(res):
            x["rank"] = i + 1
            if x["target"] and bench:
                x["vs_best_existing"] = round(x["target"]["ctr"] / bench, 3)
                x["clearly_better"] = bool(x["target"]["ctr_lo"] > bench)
        return {"brand": brand, "audience": audience, "brief": brief, "evidence": {k: ev[k] for k in ("audience_profile", "lever_forecast_ctr",
                "format_forecast_ctr", "best_existing", "benchmark_ctr")}, "candidates": res, "meta": meta,
                "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"), "levers_allowed": self.levers, "formats_allowed": self.formats}


# ---------- tiny local server: static web/ + /api/generate ----------
def serve(port=8787):
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    print("fitting the forecaster ...", flush=True)
    st = Studio()
    web = ROOT / "web"
    bk = backend()
    have_key = bk is not None

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(web), **k)

        def log_message(self, fmt, *args):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/api/health":
                return self._json(200, {"ok": True, "key": have_key, "model": bk["model"] if bk else None, "levers": st.levers, "formats": st.formats})
            return super().do_GET()

        def do_POST(self):
            if self.path != "/api/generate":
                return self._json(404, {"error": "not found"})
            try:
                q = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                brand, aud = q["brand"], q["audience"]
                if not aud.startswith(brand):
                    raise ValueError("audience does not belong to brand")
                n = int(min(8, max(2, q.get("n", 6))))
                brief = {k: q.get(k) for k in ("product", "offer", "max_discount_pct", "notes")}
                if brief.get("max_discount_pct") not in (None, ""):
                    brief["max_discount_pct"] = int(brief["max_discount_pct"])
                self._json(200, st.run(brand, aud, brief, n))
            except Exception as exc:                          # the page shows the message; nothing secret is in it
                self._json(400, {"error": str(exc)[:400]})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"studio on http://127.0.0.1:{port}  (proposer: {bk['model'] if bk else 'MISSING: add .env.anthropic or .env.openrouter'})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8787)
