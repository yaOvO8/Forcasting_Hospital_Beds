# Decisions log

One line per decision: date, what, why, who. Newest at the bottom. The talk's
"plan vs. what we actually did" section is built from this file.

| Date | Decision | Why | Who |
|---|---|---|---|
| 2026-11-03 | Target `inpatient_beds_used_7_day_avg`, one week ahead | proposal draft | team |
| 2026-11-03 | Split: train 2020-08..2022-12, val 2023-01..06, test 2023-07..2024-04, 20% hospitals held out | time series: no shuffled split | team |
| 2026-11-03 | Suppressed target kept as NULL + separate fill column; scored only on measured rows | dropping removes small hospitals non-randomly; same test rows for every variant | Jiyao |
| 2026-11-03 | "Previous week" = report 4–10 days earlier | HHS changed the collection-week weekday in June 2023 | Jiyao |

## Open (decide at the next meeting)

- [ ] Target: all inpatient beds or ICU beds
- [ ] Geographic scope: all US or one state first
- [ ] Quantiles the model outputs. The newsvendor level for a 3:1 shortfall:idle cost is the 0.75 quantile, so 0.1 / 0.5 / 0.9 is not enough
- [ ] Rule for rows with beds used > beds available (now: kept, flagged)
- [ ] LLM component: yes / no; who confirms a Gemini API key
