"""Creative representation that does not depend on the language or on hand-written rules.

Encoders, in order of preference:
  * "hf":    a pretrained multilingual sentence encoder from Hugging Face, run through ONNX
             (fastembed; default sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2).
  * "tfidf": character n-gram TF-IDF. No download, any language, weaker.
"auto" uses "hf" when available. Vectors are reduced to a few principal components so that a
customer with a few dozen creatives does not overfit.
"""
import numpy as np
import pandas as pd

HF_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_cache = {}


def _texts(creatives, fields):
    return creatives[fields].fillna("").astype(str).agg(". ".join, axis=1).tolist()


def embed(texts, encoder="auto"):
    if encoder in ("auto", "hf"):
        try:
            from fastembed import TextEmbedding
            if "hf" not in _cache:
                _cache["hf"] = TextEmbedding(HF_MODEL)
            return np.array(list(_cache["hf"].embed(texts))), "hf:" + HF_MODEL
        except Exception as exc:  # no package, no network, no model
            if encoder == "hf":
                raise
            _cache["hf_error"] = str(exc)[:200]
    return None, "tfidf"


class CreativeSpace:
    def __init__(self, cfg, n_components=6):
        self.spec, self.n, self.encoder = cfg.get("creatives") or {}, n_components, cfg.get("encoder", "auto")

    def fit(self, creatives):
        """Fit the text projection on the creatives passed in. The engine passes only creatives
        present in the training rows unless the config asks for the transductive protocol."""
        from sklearn.decomposition import PCA, TruncatedSVD
        self.prior = None
        if not self.spec.get("text"):                     # customer supplied no creative text
            self.used = "none"
            return self
        texts = _texts(creatives, self.spec["text"])
        vecs, self.used = embed(texts, self.encoder)
        k = min(self.n, len(texts) - 1)                 # components that the data can support
        if vecs is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit(texts)
            vecs = self.tfidf.transform(texts)
            k = min(k, vecs.shape[1] - 1)
        # With one creative there is no variation to project: carry no text components at all
        # instead of asking for a zero-dimensional projection.
        self.proj = None
        if k >= 1:
            self.proj = (PCA(k, random_state=0) if self.used.startswith("hf") else TruncatedSVD(k, random_state=0)).fit(vecs)
        self.n_fit_creatives = len(texts)
        self.prior = None
        ev = self.spec.get("external_evidence")
        if ev:
            self.prior = fit_external_prior(ev, self)
        return self

    def transform(self, creatives):
        if self.used == "none":
            return pd.DataFrame(index=creatives["creative_id"].values)
        texts = _texts(creatives, self.spec["text"])
        vecs = embed(texts, "hf")[0] if self.used.startswith("hf") else self.tfidf.transform(texts)
        z = self.proj.transform(vecs) if self.proj is not None else np.zeros((len(texts), 0))
        out = pd.DataFrame(z, columns=[f"emb{i}" for i in range(z.shape[1])], index=creatives["creative_id"].values)
        for c in self.spec.get("numeric", []):
            out["num_" + c] = pd.to_numeric(creatives[c], errors="coerce").fillna(0).values
        if getattr(self, "prior", None) is not None:              # optional external evidence
            out["prior_longevity"] = self.prior.predict(vecs)
        import re
        for name, pattern in (self.spec.get("keyword_tags") or {}).items():   # optional, per customer
            out["tag_" + name] = [int(bool(re.search(pattern, t.lower()))) for t in texts]
        return out


def fit_external_prior(ev, space):
    """Learn 'what tends to keep running' from public evidence such as an ad-library export.

    Expected CSV: one row per external ad with free-text columns and one numeric outcome proxy,
    e.g. days the ad stayed live or the midpoint of its impression band. The proxy is a weak label
    (advertisers keep what works), so the result is used as ONE extra creative feature whose
    weight the customer's own results decide. It is never reported as a measured outcome.
    """
    from sklearn.linear_model import RidgeCV
    e = pd.read_csv(ev["file"])
    texts = e[ev["text"]].fillna("").astype(str).agg(". ".join, axis=1).tolist()
    y = np.log1p(pd.to_numeric(e[ev["outcome"]], errors="coerce").fillna(0).values)
    vecs = embed(texts, "hf")[0] if space.used.startswith("hf") else space.tfidf.transform(texts)
    model = RidgeCV(alphas=[1, 10, 100]).fit(vecs, (y - y.mean()) / (y.std() + 1e-9))
    model.n_external_ads = len(e)
    return model
