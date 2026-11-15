"""Creative studio: guards, schema validation and the OpenAI-compatible path, all offline."""
import json
import os
import threading
import unittest
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import adsim.studio as S

warnings.filterwarnings("ignore")
BRIEF = {"product": "Siero alla vitamina C", "offer": "Black Week: fino al -40%", "max_discount_pct": 40, "notes": ""}


def bare_studio():
    st = S.Studio.__new__(S.Studio)
    st.levers, st.formats = ["black_friday", "scarcity", "urgency"], ["carosello", "immagine", "video"]
    st.len_range = {"headline": (20, 44), "testo_principale": (32, 75), "descrizione_visual": (54, 120)}
    return st


def cand(**kw):
    c = {"leva": "scarcity", "formato": "video", "durata_video_s": 15, "headline": "Siero vitamina C: ultimi pezzi",
         "testo_principale": "Il lotto sta finendo: Black Week fino al -40%.", "call_to_action": "Acquista ora",
         "descrizione_visual": "Mano che prende l'ultimo flacone da uno scaffale quasi vuoto, scritta in sovrimpressione.",
         "rationale_en": "r", "rationale_it": "r"}
    c.update(kw)
    return c


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.st = bare_studio()
        self.p = mock.patch.object(S, "embed", lambda *a, **k: (None, "none"))
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_discount_above_brief_is_rejected(self):
        out = self.st.check([cand(headline="Solo oggi -50% su tutto il siero")], BRIEF)[0]
        self.assertTrue(out["rejected"])

    def test_discount_within_brief_is_allowed(self):
        out = self.st.check([cand()], BRIEF)[0]
        self.assertFalse(out["rejected"])
        self.assertEqual([f for f in out["flags"] if f["code"] == "claim"], [])

    def test_invented_numbers_are_flagged_not_rejected(self):
        out = self.st.check([cand(testo_principale="Ultime 150 confezioni, spedizione gratis sopra 60 euro.")], BRIEF)[0]
        claim = [f for f in out["flags"] if f["code"] == "claim"]
        self.assertEqual(claim[0]["nums"], ["60", "150"])
        self.assertFalse(out["rejected"])

    def test_non_video_has_no_duration(self):
        out = self.st.check([cand(formato="immagine", durata_video_s=12)], BRIEF)[0]
        self.assertIsNone(out["durata_video_s"])


class ValidateTest(unittest.TestCase):
    def test_unknown_lever_and_missing_fields_are_dropped_and_counted(self):
        ok, bad = bare_studio()._validate([cand(), cand(leva="discount"), {"leva": "scarcity"}, "junk"])
        self.assertEqual((len(ok), bad), (1, 3))

    def test_string_duration_is_coerced(self):
        ok, _ = bare_studio()._validate([cand(durata_video_s="16")])
        self.assertEqual(ok[0]["durata_video_s"], 16)


class OpenAICompatTest(unittest.TestCase):
    def test_bad_json_is_retried_then_parsed(self):
        calls = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                content = "{not json" if len(calls) == 1 else json.dumps({"creatives": [cand()]})
                out = json.dumps({"id": "x", "model": "mock", "choices": [{"message": {"content": content}}], "usage": {}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            b = {"kind": "openai_compat", "key": None, "model": "mock", "base_url": f"http://127.0.0.1:{srv.server_port}/v1"}
            items, meta = bare_studio()._propose_openai_compat(b, "brief", S._schema(["scarcity"], ["video"], 1))
        finally:
            srv.shutdown()
        self.assertEqual(len(calls), 2)
        self.assertEqual(items[0]["leva"], "scarcity")
        self.assertEqual(meta["backend"], "openai_compat")


class BackendTest(unittest.TestCase):
    def test_local_endpoint_needs_no_key(self):
        with mock.patch.object(S, "_env", lambda *a: None), mock.patch.dict(os.environ, {"STUDIO_BASE_URL": "http://localhost:11434/v1/"}):
            b = S.backend()
        self.assertEqual((b["kind"], b["base_url"]), ("openai_compat", "http://localhost:11434/v1"))

    def test_no_backend_configured(self):
        with mock.patch.object(S, "_env", lambda *a: None), mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(S.backend())


if __name__ == "__main__":
    unittest.main()
