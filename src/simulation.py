"""Synthetic viewer scenarios calibrated to a measured ad-set CTR forecast.

The kit has no age, habit or person-level labels. Ages/needs are illustrative priors;
habit effects are user-controlled assumptions and never enter submitted forecasts.
Calibration conserves the forecast CTR exactly, avoiding invented aggregate accuracy.
"""
import numpy as np
import pandas as pd
from scipy.special import expit

AGES = ["18-34", "35-54", "55-70"]
HABITS = ["Fast scroller", "Proof seeker", "Deal watcher"]
NEEDS = {
    "beauty_skincare": ["Simple daily routine", "Ingredient reassurance", "Value for money"],
    "pet_ecommerce": ["Convenient reordering", "Pet suitability", "Affordable supplies"],
    "abbigliamento": ["Easy outfit ideas", "Fit and material confidence", "Affordable wardrobe"],
}


def simulate(ctr_percent, vertical, tags, viewers=10000, seed=42, strength=0.0, age_weights=None):
    if not 0 < ctr_percent < 100:
        raise ValueError("CTR must be a percentage strictly between 0 and 100.")
    if vertical not in NEEDS or viewers < 1 or not 0 <= strength <= 2:
        raise ValueError("Invalid simulation vertical, viewer count or sensitivity strength.")
    weights = np.asarray(age_weights if age_weights is not None else [1, 1, 1], dtype=float)
    if weights.shape != (3,) or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Provide three nonnegative age weights with a positive total.")
    weights /= weights.sum()
    # These offsets are declared scenario assumptions, not estimated demographic effects.
    get = lambda key: float(tags.get(key, 0))
    offsets = strength * np.array([
        0.4*get("hook_first2s") - 0.4*get("heavy_text") - 0.2*get("logo_first"),
        0.3*get("reviews") + 0.2*get("talks_to_camera") - 0.2*get("discount_late"),
        0.3*get("timer") + 0.2*(get("discount_pct") > 0) - 0.3*get("discount_late"),
    ])
    group_weights = np.repeat(weights, 3) / 3
    utility = np.tile(offsets, 3)
    target = ctr_percent / 100
    left, right = -50., 50.
    for _ in range(100):
        middle = (left+right)/2
        if np.dot(group_weights, expit(middle+utility)) < target:
            left = middle
        else:
            right = middle
    probabilities = expit((left+right)/2+utility)
    rng = np.random.default_rng(seed)
    n = rng.multinomial(viewers, group_weights)
    clicks = rng.binomial(n, probabilities)
    panel = pd.DataFrame({"age_assumption": np.repeat(AGES, 3), "habit_assumption": np.tile(HABITS, 3),
                          "need_assumption": np.tile(NEEDS[vertical], 3), "population_weight": group_weights,
                          "scenario_ctr_%": probabilities*100, "simulated_viewers": n, "simulated_clicks": clicks})
    return panel, {"forecast_ctr_%": ctr_percent, "calibrated_ctr_%": float(np.dot(group_weights, probabilities)*100),
                   "expected_clicks": viewers*target, "sampled_clicks": int(clicks.sum()),
                   "seed": seed, "habit_strength_assumption": strength,
                   "limitation": "Age and habit response are unobserved. Subgroup rates are hypothetical; random clicks are a simulation, not validation."}
