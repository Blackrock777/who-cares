# Decisions for 16-30 November

## Budget: where a euro buys the most clicks

Cost per click = CPM / (10 x CTR). Clicks scale with budget^0.42 (measured in the history when an ad set doubled its budget: CPM +28%, CTR -14%).

| campaign_id   | adset_id   |   budget |   ctr |    cpm |   cpc |   clicks_per_day |   budget_proposed |   clicks_per_day_proposed | note                                       |
|:--------------|:-----------|---------:|------:|-------:|------:|-----------------:|------------------:|--------------------------:|:-------------------------------------------|
| CDF-C1        | CDF-AS1    |      135 | 0.777 |  7.947 | 1.047 |          128.927 |               108 |                     117.4 | most expensive clicks: gives 20% of budget |
| CDF-C1        | CDF-AS2    |       50 | 1.124 |  8.577 | 0.815 |           61.327 |                50 |                      61.3 |                                            |
| CDF-C1        | CDF-AS3    |       50 | 0.9   |  8.884 | 1.034 |           48.378 |                50 |                      48.4 |                                            |
| CDF-C1        | CDF-AS4    |       60 | 2.036 | 15.35  | 0.799 |           75.084 |                87 |                      87.8 | cheapest clicks: receives the shift        |
| FGR-C1        | FGR-AS1    |      160 | 0.805 |  8.366 | 1.092 |          146.457 |               160 |                     146.5 |                                            |
| FGR-C1        | FGR-AS2    |       60 | 1.14  |  9.935 | 0.918 |           65.348 |                60 |                      65.3 |                                            |
| FGR-C1        | FGR-AS3    |       40 | 0.991 | 14.276 | 1.558 |           25.682 |                32 |                      23.4 | most expensive clicks: gives 20% of budget |
| FGR-C1        | FGR-AS4    |      125 | 2.126 | 17.464 | 0.832 |          150.277 |               133 |                     154.2 | cheapest clicks: receives the shift        |
| NDL-C1        | NDL-AS1    |      150 | 0.712 | 10.566 | 1.536 |           97.68  |               150 |                      97.7 |                                            |
| NDL-C1        | NDL-AS2    |       80 | 1.072 | 11.521 | 1.152 |           69.457 |               102 |                      76.9 | cheapest clicks: receives the shift        |
| NDL-C1        | NDL-AS3    |      110 | 0.971 | 14.764 | 1.645 |           66.882 |                88 |                      60.9 | most expensive clicks: gives 20% of budget |
| NDL-C1        | NDL-AS4    |      110 | 1.834 | 20.823 | 1.209 |           91.014 |               110 |                      91   |                                            |

## Creative and lever: push and pause, per ad set and week

| adset_id   | week                                  | push     | push_asset   | push_leva    | push_formato   |   push_ctr | push_band   | push_is_cold_start   | pause    | pause_asset   |   pause_ctr | ctr_gap   | confident   |
|:-----------|:--------------------------------------|:---------|:-------------|:-------------|:---------------|-----------:|:------------|:---------------------|:---------|:--------------|------------:|:----------|:------------|
| CDF-AS1    | Black Week + Black Friday (23-30 Nov) | CDF-AD06 | CDF-B3       | black_friday | carosello      |       0.98 | 0.69-1.38   | True                 | CDF-AD04 | CDF-U4        |        0.66 | 1.5x      | False       |
| CDF-AS1    | Pre Black Week (16-22 Nov)            | CDF-AD06 | CDF-B3       | black_friday | carosello      |       1.06 | 0.75-1.50   | True                 | CDF-AD04 | CDF-U4        |        0.63 | 1.7x      | False       |
| CDF-AS2    | Black Week + Black Friday (23-30 Nov) | CDF-AD11 | CDF-B4       | black_friday | video          |       1.6  | 1.13-2.26   | True                 | CDF-AD09 | CDF-U3        |        0.87 | 1.8x      | False       |
| CDF-AS2    | Pre Black Week (16-22 Nov)            | CDF-AD10 | CDF-B2       | black_friday | video          |       1.43 | 1.05-1.94   | False                | CDF-AD09 | CDF-U3        |        0.84 | 1.7x      | False       |
| CDF-AS3    | Black Week + Black Friday (23-30 Nov) | CDF-AD17 | CDF-B4       | black_friday | video          |       1.43 | 1.01-2.02   | True                 | CDF-AD15 | CDF-U3        |        0.74 | 1.9x      | True        |
| CDF-AS3    | Pre Black Week (16-22 Nov)            | CDF-AD16 | CDF-B1       | black_friday | immagine       |       0.94 | 0.69-1.28   | False                | CDF-AD15 | CDF-U3        |        0.72 | 1.3x      | False       |
| CDF-AS4    | Black Week + Black Friday (23-30 Nov) | CDF-AD22 | CDF-B2       | black_friday | video          |       2.4  | 1.76-3.26   | False                | CDF-AD21 | CDF-U4        |        1.5  | 1.6x      | False       |
| CDF-AS4    | Pre Black Week (16-22 Nov)            | CDF-AD22 | CDF-B2       | black_friday | video          |       2.71 | 1.99-3.69   | False                | CDF-AD21 | CDF-U4        |        1.46 | 1.9x      | True        |
| FGR-AS1    | Black Week + Black Friday (23-30 Nov) | FGR-AD06 | FGR-B3       | black_friday | carosello      |       0.97 | 0.69-1.37   | True                 | FGR-AD05 | FGR-B1        |        0.58 | 1.7x      | False       |
| FGR-AS1    | Pre Black Week (16-22 Nov)            | FGR-AD06 | FGR-B3       | black_friday | carosello      |       1.01 | 0.72-1.43   | True                 | FGR-AD05 | FGR-B1        |        0.55 | 1.8x      | False       |
| FGR-AS2    | Black Week + Black Friday (23-30 Nov) | FGR-AD11 | FGR-B4       | black_friday | video          |       1.47 | 1.04-2.07   | True                 | FGR-AD09 | FGR-U3        |        0.87 | 1.7x      | False       |
| FGR-AS2    | Pre Black Week (16-22 Nov)            | FGR-AD10 | FGR-B2       | black_friday | video          |       1.26 | 0.92-1.71   | False                | FGR-AD09 | FGR-U3        |        0.8  | 1.6x      | False       |
| FGR-AS3    | Black Week + Black Friday (23-30 Nov) | FGR-AD17 | FGR-B4       | black_friday | video          |       1.47 | 1.04-2.08   | True                 | FGR-AD16 | FGR-B1        |        0.69 | 2.1x      | True        |
| FGR-AS3    | Pre Black Week (16-22 Nov)            | FGR-AD13 | FGR-S2       | scarcity     | video          |       1.17 | 0.86-1.59   | False                | FGR-AD16 | FGR-B1        |        0.65 | 1.8x      | False       |
| FGR-AS4    | Black Week + Black Friday (23-30 Nov) | FGR-AD22 | FGR-B2       | black_friday | video          |       2.3  | 1.69-3.13   | False                | FGR-AD20 | FGR-S3        |        2    | 1.2x      | False       |
| FGR-AS4    | Pre Black Week (16-22 Nov)            | FGR-AD22 | FGR-B2       | black_friday | video          |       2.4  | 1.76-3.26   | False                | FGR-AD20 | FGR-S3        |        1.8  | 1.3x      | False       |
| NDL-AS1    | Black Week + Black Friday (23-30 Nov) | NDL-AD06 | NDL-B3       | black_friday | carosello      |       0.96 | 0.68-1.36   | True                 | NDL-AD05 | NDL-B1        |        0.59 | 1.6x      | False       |
| NDL-AS1    | Pre Black Week (16-22 Nov)            | NDL-AD06 | NDL-B3       | black_friday | carosello      |       1.03 | 0.73-1.45   | True                 | NDL-AD05 | NDL-B1        |        0.59 | 1.8x      | False       |
| NDL-AS2    | Black Week + Black Friday (23-30 Nov) | NDL-AD11 | NDL-B4       | black_friday | video          |       1.47 | 1.04-2.07   | True                 | NDL-AD09 | NDL-U3        |        0.74 | 2.0x      | True        |
| NDL-AS2    | Pre Black Week (16-22 Nov)            | NDL-AD10 | NDL-B2       | black_friday | video          |       1.29 | 0.95-1.75   | False                | NDL-AD09 | NDL-U3        |        0.71 | 1.8x      | False       |
| NDL-AS3    | Black Week + Black Friday (23-30 Nov) | NDL-AD17 | NDL-B4       | black_friday | video          |       1.51 | 1.07-2.13   | True                 | NDL-AD15 | NDL-U3        |        0.72 | 2.1x      | True        |
| NDL-AS3    | Pre Black Week (16-22 Nov)            | NDL-AD13 | NDL-S2       | scarcity     | video          |       1.13 | 0.83-1.54   | False                | NDL-AD15 | NDL-U3        |        0.67 | 1.7x      | False       |
| NDL-AS4    | Black Week + Black Friday (23-30 Nov) | NDL-AD22 | NDL-B2       | black_friday | video          |       2.3  | 1.69-3.13   | False                | NDL-AD20 | NDL-S3        |        1.47 | 1.6x      | False       |
| NDL-AS4    | Pre Black Week (16-22 Nov)            | NDL-AD22 | NDL-B2       | black_friday | video          |       2.46 | 1.81-3.35   | False                | NDL-AD20 | NDL-S3        |        1.39 | 1.8x      | False       |

## Timing: the market day by day

| data                |   ctr |    cpm |   cpc |   cpm_vs_first_day |
|:--------------------|------:|-------:|------:|-------------------:|
| 2026-11-16 00:00:00 | 1.108 | 12.109 | 1.226 |               1    |
| 2026-11-17 00:00:00 | 1.109 | 12.064 | 1.215 |               1    |
| 2026-11-18 00:00:00 | 1.108 | 11.954 | 1.205 |               0.99 |
| 2026-11-19 00:00:00 | 1.115 | 11.821 | 1.169 |               0.98 |
| 2026-11-20 00:00:00 | 1.233 | 11.931 | 1.089 |               0.99 |
| 2026-11-21 00:00:00 | 1.164 | 11.914 | 1.144 |               0.98 |
| 2026-11-22 00:00:00 | 1.174 | 11.827 | 1.138 |               0.98 |
| 2026-11-23 00:00:00 | 1.243 | 13.111 | 1.164 |               1.08 |
| 2026-11-24 00:00:00 | 1.244 | 13.08  | 1.151 |               1.08 |
| 2026-11-25 00:00:00 | 1.242 | 12.94  | 1.14  |               1.07 |
| 2026-11-26 00:00:00 | 1.28  | 12.766 | 1.097 |               1.05 |
| 2026-11-27 00:00:00 | 1.295 | 12.651 | 1.077 |               1.04 |
| 2026-11-28 00:00:00 | 1.235 | 12.587 | 1.118 |               1.04 |
| 2026-11-29 00:00:00 | 1.244 | 12.529 | 1.12  |               1.03 |
| 2026-11-30 00:00:00 | 1.056 | 12.381 | 1.276 |               1.02 |
