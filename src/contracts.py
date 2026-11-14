"""Submission checks: every requested key and metadata field must survive inference."""
import numpy as np
import pandas as pd


def check_predictions(required, predicted):
    keys = ["data", "ad_id", "adset_id"]
    left, right = required.copy(), predicted.copy()
    for table in [left, right]:
        table["data"] = pd.to_datetime(table["data"]).dt.strftime("%Y-%m-%d")
        if table.duplicated(keys).any():
            raise ValueError("Duplicate forecast keys.")
    if len(left) != len(right):
        raise ValueError("Forecast count does not match the requested rows.")
    joined = left.merge(right, on=keys, how="outer", suffixes=("_required", "_predicted"),
                        indicator=True, validate="one_to_one")
    if not joined["_merge"].eq("both").all():
        raise ValueError("Missing or extra forecast keys.")
    for col in ["vertical", "campaign_id", "asset_id", "leva", "formato", "budget_giornaliero_adset"]:
        if not joined[f"{col}_required"].eq(joined[f"{col}_predicted"]).all():
            raise ValueError(f"Forecast metadata mismatch: {col}")
    for metric in ["ctr", "cpm"]:
        values = right[[f"{metric}_{s}" for s in ["lo", "pred", "hi"]]].to_numpy(float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(f"Invalid {metric} forecast values.")
        if (np.diff(values, axis=1) < 0).any():
            raise ValueError(f"Unordered {metric} intervals.")
        if metric == "ctr" and (values > 100).any():
            raise ValueError("CTR percentage exceeds 100.")
    return {"required_rows": len(left), "predicted_rows": len(right),
            "unique_keys": True, "metadata_matches": True, "finite_ordered_intervals": True}
