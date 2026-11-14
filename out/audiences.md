# Audience hypotheses grounded in observed response

Simulated challenge data. Targeting identities and demographics are not observed. Profiles are ranked from metrics within each advertiser, not assigned from ad-set IDs.

| adset_id   |   budget_eur |   impressions |   clicks |    spend |   frequency |   rows |   ctr_% |   cpm_eur |   cpc_eur |   reach_per_eur |   fatigue_late_vs_first_week |   fatigue_ads |   bf_mix_ratio |   matched_ctr_ratio | campaign_id   | profile   | audience                                        |
|:-----------|-------------:|--------------:|---------:|---------:|------------:|-------:|--------:|----------:|----------:|----------------:|-----------------------------:|--------------:|---------------:|--------------------:|:--------------|:----------|:------------------------------------------------|
| CDF-AS1    |       90     |       1510667 |    17301 |  7869.52 |      1.0307 |    159 |  1.1453 |    5.2093 |    0.4549 |        186.246  |                       0.7191 |             3 |         0.905  |              0.6715 | CDF-C1        | broad     | Broad / discovery response                      |
| CDF-AS2    |       50     |        685154 |     7263 |  4374.21 |      1.0316 |    149 |  1.0601 |    6.3843 |    0.6023 |        151.825  |                       0.7791 |             3 |         1.713  |              0.9389 | CDF-C1        | deal      | Promotion-responsive prospecting hypothesis     |
| CDF-AS3    |       50     |        708362 |     8630 |  4361.44 |      1.0313 |    187 |  1.2183 |    6.1571 |    0.5054 |        157.478  |                       0.7578 |             3 |         1.0338 |              1.0171 | CDF-C1        | uncertain | Mixed prospecting response / identity uncertain |
| CDF-AS4    |       35     |        307171 |     7412 |  3054.52 |      1.1664 |    142 |  2.413  |    9.944  |    0.4121 |         86.1134 |                       0.736  |             3 |         1.5092 |              1.3815 | CDF-C1        | warm      | Warm-response / retargeting hypothesis          |
| FGR-AS1    |      100     |       1488929 |    13318 |  8736.71 |      1.0307 |    132 |  0.8945 |    5.8678 |    0.656  |        165.339  |                       0.7082 |             2 |         0.7958 |              0.6155 | FGR-C1        | broad     | Broad / discovery response                      |
| FGR-AS2    |       60     |        733944 |     8727 |  5318.5  |      1.0324 |    151 |  1.1891 |    7.2465 |    0.6094 |        133.664  |                       0.6918 |             3 |         1.1992 |              0.9367 | FGR-C1        | deal      | Promotion-responsive prospecting hypothesis     |
| FGR-AS3    |       40     |        348913 |     4216 |  3523.37 |      1.035  |    161 |  1.2083 |   10.0981 |    0.8357 |         95.6567 |                       0.7254 |             2 |         0.6237 |              1.018  | FGR-C1        | selective | Selective / higher-cost response                |
| FGR-AS4    |       50     |        407032 |     8913 |  4410.89 |      1.2119 |    144 |  2.1898 |   10.8367 |    0.4949 |         75.9323 |                       0.721  |             3 |         1.347  |              1.3927 | FGR-C1        | warm      | Warm-response / retargeting hypothesis          |
| NDL-AS1    |      120     |       1391111 |    12351 | 10612.8  |      1.0308 |    161 |  0.8879 |    7.629  |    0.8593 |        127.149  |                       0.7451 |             3 |         0.7955 |              0.6726 | NDL-C1        | broad     | Broad / discovery response                      |
| NDL-AS2    |       80     |        837640 |     9563 |  7078.46 |      1.0316 |    151 |  1.1417 |    8.4505 |    0.7402 |        114.7    |                       0.6969 |             3 |         1.5396 |              0.8864 | NDL-C1        | deal      | Promotion-responsive prospecting hypothesis     |
| NDL-AS3    |       60     |        535744 |     7433 |  5284.89 |      1.0368 |    188 |  1.3874 |    9.8646 |    0.711  |         97.7496 |                       0.7286 |             3 |         0.6686 |              1.1046 | NDL-C1        | uncertain | Mixed prospecting response / identity uncertain |
| NDL-AS4    |       49.375 |        318658 |     6020 |  4276.55 |      1.2341 |    144 |  1.8892 |   13.4205 |    0.7104 |         59.9581 |                       0.6917 |             3 |         1.5762 |              1.3915 | NDL-C1        | warm      | Warm-response / retargeting hypothesis          |

## CDF-AS1: Broad / discovery response

A broad, relatively cold audience is plausible. Low auction cost and weak click response support this reading.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 159 cleaned ad-day observations; pooled CTR 1.15%, CPM €5.21.
- Median daily frequency per ad 1.031; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.72 across 3 ads.
- Same-asset/day relative CTR median 0.67; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 0.91; creative/date mix confounds this comparison.

**Alternative:** Cheap placements or weaker creative delivery could produce a similar profile.
**Decision:** Test a clear product introduction against the strongest existing creative.

## CDF-AS2: Promotion-responsive prospecting hypothesis

An interest or lookalike prospecting audience is plausible. Promotion response should be tested rather than assumed.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 149 cleaned ad-day observations; pooled CTR 1.06%, CPM €6.38.
- Median daily frequency per ad 1.032; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.78 across 3 ads.
- Same-asset/day relative CTR median 0.94; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.71; creative/date mix confounds this comparison.

**Alternative:** Creative mix and launch dates can explain apparent deal sensitivity.
**Decision:** Compare promotion, scarcity and urgency on the same dates. Watch the measured creative fatigue.

## CDF-AS3: Mixed prospecting response / identity uncertain

An interest-based audience is plausible, but the observed signals do not reliably distinguish deal seekers from selective shoppers.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 187 cleaned ad-day observations; pooled CTR 1.22%, CPM €6.16.
- Median daily frequency per ad 1.031; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.76 across 3 ads.
- Same-asset/day relative CTR median 1.02; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.03; creative/date mix confounds this comparison.

**Alternative:** Creative mix, delivery and time effects can explain the differences between these ad sets.
**Decision:** Run a controlled proof-versus-promotion comparison before changing the targeting story.

## CDF-AS4: Warm-response / retargeting hypothesis

Visitors, previous buyers or cart abandoners are plausible: repeat exposure and click propensity are relatively high.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 142 cleaned ad-day observations; pooled CTR 2.41%, CPM €9.94.
- Median daily frequency per ad 1.166; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.74 across 3 ads.
- Same-asset/day relative CTR median 1.38; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.51; creative/date mix confounds this comparison.

**Alternative:** A small, highly interested prospecting pool can also click often and see repeated impressions.
**Decision:** Prioritise promising creatives cautiously and monitor fatigue; high CTR does not establish sales lift.

## FGR-AS1: Broad / discovery response

A broad, relatively cold audience is plausible. Low auction cost and weak click response support this reading.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 132 cleaned ad-day observations; pooled CTR 0.89%, CPM €5.87.
- Median daily frequency per ad 1.031; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.71 across 2 ads.
- Same-asset/day relative CTR median 0.62; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 0.80; creative/date mix confounds this comparison.

**Alternative:** Cheap placements or weaker creative delivery could produce a similar profile.
**Decision:** Test a clear product introduction against the strongest existing creative.

## FGR-AS2: Promotion-responsive prospecting hypothesis

An interest or lookalike prospecting audience is plausible. Promotion response should be tested rather than assumed.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 151 cleaned ad-day observations; pooled CTR 1.19%, CPM €7.25.
- Median daily frequency per ad 1.032; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.69 across 3 ads.
- Same-asset/day relative CTR median 0.94; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.20; creative/date mix confounds this comparison.

**Alternative:** Creative mix and launch dates can explain apparent deal sensitivity.
**Decision:** Compare promotion, scarcity and urgency on the same dates. Watch the measured creative fatigue.

## FGR-AS3: Selective / higher-cost response

A narrower or more expensive audience is plausible. Premium interests and trust needs are hypotheses only.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 161 cleaned ad-day observations; pooled CTR 1.21%, CPM €10.10.
- Median daily frequency per ad 1.035; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.73 across 2 ads.
- Same-asset/day relative CTR median 1.02; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 0.62; creative/date mix confounds this comparison.

**Alternative:** Placement, bidding or competition can raise CPM without premium customers.
**Decision:** Compare product proof with discount-led creative; retain the winner only when the evidence supports it.

## FGR-AS4: Warm-response / retargeting hypothesis

Visitors, previous buyers or cart abandoners are plausible: repeat exposure and click propensity are relatively high.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 144 cleaned ad-day observations; pooled CTR 2.19%, CPM €10.84.
- Median daily frequency per ad 1.212; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.72 across 3 ads.
- Same-asset/day relative CTR median 1.39; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.35; creative/date mix confounds this comparison.

**Alternative:** A small, highly interested prospecting pool can also click often and see repeated impressions.
**Decision:** Prioritise promising creatives cautiously and monitor fatigue; high CTR does not establish sales lift.

## NDL-AS1: Broad / discovery response

A broad, relatively cold audience is plausible. Low auction cost and weak click response support this reading.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 161 cleaned ad-day observations; pooled CTR 0.89%, CPM €7.63.
- Median daily frequency per ad 1.031; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.75 across 3 ads.
- Same-asset/day relative CTR median 0.67; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 0.80; creative/date mix confounds this comparison.

**Alternative:** Cheap placements or weaker creative delivery could produce a similar profile.
**Decision:** Test a clear product introduction against the strongest existing creative.

## NDL-AS2: Promotion-responsive prospecting hypothesis

An interest or lookalike prospecting audience is plausible. Promotion response should be tested rather than assumed.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 151 cleaned ad-day observations; pooled CTR 1.14%, CPM €8.45.
- Median daily frequency per ad 1.032; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.70 across 3 ads.
- Same-asset/day relative CTR median 0.89; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.54; creative/date mix confounds this comparison.

**Alternative:** Creative mix and launch dates can explain apparent deal sensitivity.
**Decision:** Compare promotion, scarcity and urgency on the same dates. Watch the measured creative fatigue.

## NDL-AS3: Mixed prospecting response / identity uncertain

An interest-based audience is plausible, but the observed signals do not reliably distinguish deal seekers from selective shoppers.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 188 cleaned ad-day observations; pooled CTR 1.39%, CPM €9.86.
- Median daily frequency per ad 1.037; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.73 across 3 ads.
- Same-asset/day relative CTR median 1.10; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 0.67; creative/date mix confounds this comparison.

**Alternative:** Creative mix, delivery and time effects can explain the differences between these ad sets.
**Decision:** Run a controlled proof-versus-promotion comparison before changing the targeting story.

## NDL-AS4: Warm-response / retargeting hypothesis

Visitors, previous buyers or cart abandoners are plausible: repeat exposure and click propensity are relatively high.

**Confidence:** Moderate for relative behaviour; low for targeting identity; demographics unobserved.
**Unobserved:** Age, gender, income, geography and placement cannot be recovered from these aggregates.

- 144 cleaned ad-day observations; pooled CTR 1.89%, CPM €13.42.
- Median daily frequency per ad 1.234; this is not deduplicated audience reach.
- Within-ad late/first-week CTR ratio, season-adjusted: 0.69 across 3 ads.
- Same-asset/day relative CTR median 1.39; a descriptive matched comparison.
- Black Friday creative CTR / all-creative CTR 1.58; creative/date mix confounds this comparison.

**Alternative:** A small, highly interested prospecting pool can also click often and see repeated impressions.
**Decision:** Prioritise promising creatives cautiously and monitor fatigue; high CTR does not establish sales lift.
