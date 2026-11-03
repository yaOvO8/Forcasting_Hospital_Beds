-- 04_clean.sql: the table models train on.
-- Measured and filled-in values live in SEPARATE columns:
--   y_measured  : the reported value, NULL when suppressed
--   y_fill_mid  : our filled-in value, only where the report was suppressed
-- Same rule for every feature that can carry the sentinel: *_measured is NULL
-- when suppressed. Nothing filled in is ever written into a *_measured column.
CREATE OR REPLACE MACRO measured(x) AS CASE WHEN x = {suppressed} OR x < 0 THEN NULL ELSE x END;

CREATE OR REPLACE TABLE clean AS
SELECT
    s.hospital_pk,
    s.collection_week,
    s.state,
    s.ccn,
    s.hospital_subtype,
    s.is_metro_micro,
    s.is_corrected,
    measured(s.target_raw)                                  AS y_measured,
    v.r_target_suppressed                                   AS is_suppressed,
    CASE WHEN v.r_target_suppressed THEN {fill} END         AS y_fill_mid,
    s.target_coverage,
    measured(s.capacity_raw)                                AS capacity_measured,
    v.r_used_gt_capacity                                    AS flag_used_gt_capacity,
    measured(s.total_beds_raw)                              AS total_beds_measured,
    measured(s.covid_inpatients_raw)                        AS covid_inpatients_measured,
    measured(s.flu_inpatients_raw)                          AS flu_inpatients_measured,
    measured(s.icu_used_raw)                                AS icu_used_measured,
    measured(s.icu_beds_raw)                                AS icu_beds_measured,
    s._row_id
FROM staging s
JOIN validation v USING (_row_id)
WHERE NOT (v.r_missing_key OR v.r_bad_week OR v.r_out_of_window
           OR v.r_duplicate OR v.r_target_missing OR v.r_target_negative)
ORDER BY s.hospital_pk, s.collection_week;
