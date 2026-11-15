# Sources behind the audience model and the simulated world

Every number in `data/priors/priors.json` comes from one of the sources below. `scripts/build_priors.py` rebuilds that file from them. The official forecasts (`out/predictions.csv`) use only the organisers' kit.

| What | Source | Type | Used for | Caveat |
|---|---|---|---|---|
| Italian Meta ad audience by age × gender (39.4M, 18+) | [Affectgroup, Mar 2026](https://affectgroup.com/blog/italy-facebook-instagram-audience-in-meta-ads-2026/), from the Meta Marketing API | real | fallback prior; hero crowd | accounts, not unique people |
| Beauty audience mix | Meta Ad Library, Sephora IT/FR: 567 ads with reach in Italy | real | beauty prior, and its spread (κ) | one brand |
| Pet audience mix | Meta Ad Library, Arcaplanet: 245 ads | real | pet prior | one brand |
| Clothing audience mix | Meta Ad Library, page "OVS" only: 153 ads | real | clothing prior | the keyword search also returned JOVS, OVS Kids and Swarovski; excluded |
| CTR and CPM by gender and age | [Kaggle "clicks conversion tracking"](https://www.kaggle.com/datasets/loveall/clicks-conversion-tracking): 1,143 Facebook ads | real, provenance unverified | cell multipliers: women CTR ×1.43, CPM ×1.24; per 5 years of age CTR ×1.15, CPM ×1.14 | ages 30–49 only. Outside that range the slope is halved and uncertainty widened; a 0.10 log-sd external-validity term is added everywhere |
| CPM women vs men | [Lebesgue 2025](https://lebesgue.io/facebook-ads/facebook-cpm-by-gender): $6.01 vs $4.92 | benchmark | cross-check (1.22× vs our 1.24×) | vendor data |
| Category CTR | [WordStream / LocaliQ 2025](https://wordstream.com/blog/facebook-ads-benchmarks-2025): beauty 1.81%, pets 1.64%, apparel 1.29% | benchmark | CTR levels of simulated companies | traffic campaigns, not sales |
| Black Friday CPM | Kit 2025 index: Black Week = 1.60–1.66× September. [Lebesgue](https://lebesgue.io/?p=15192): 1.59× (2025), 1.80× (2024). Nest Commerce: +21% YoY on the day | benchmark | validates the kit's season | different baselines |
| Retargeting | [Lebesgue](https://lebesgue.io/?p=3128): retargeting CPM >2× prospecting; sources disagree on CTR | benchmark | warm-audience prior: CPM +80% (wide), CTR centred on 0 (sd 0.5) | vendor data, 2022–23 |
| CPM level, Italy | Kit `cpm_storici.csv` (Meta, IT, sales objective) | kit | CPM level of simulated companies | |

| Candidate creatives (studio) | A language model through OpenRouter (free tier: NVIDIA Nemotron 3 Ultra, with Gemma 4 31B and Ling 3.2 as fallbacks), or Claude Opus 5.5 | tool | proposes copy only | never used for scoring; invented numbers are flagged |

## Assumptions (not sourced, tested only on simulated companies)
- Retargeting raises frequency by about 15% relative to the brand's other audiences.
- Demographics leave about 15% (CTR) and 10% (CPM) of an ad set's level unexplained, from targeting, placements and the like.
- Prior probability that an audience is warm: 0.2.

## Data cost
Arcaplanet and OVS were pulled on 15 Nov 2026 through the Apify Ad Library scraper (`scripts/fetch_apify_ads.py`), about $0.50 in total. The raw data stays in git-ignored `data/external/`.
