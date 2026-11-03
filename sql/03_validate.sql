-- 03_validate.sql: one boolean per validation rule, one row per staging row.
-- Rules marked HARD remove the row in 04_clean.sql. Rules marked FLAG keep the
-- row and record the problem, so the team can decide later and measure it.
-- Every rule is COALESCEd to false so a NULL input never silently drops a row.
CREATE OR REPLACE TABLE validation AS
SELECT
    _row_id,
    -- HARD: no hospital key, so the row cannot be placed in any series
    COALESCE(hospital_pk IS NULL, false)                       AS r_missing_key,
    -- HARD: week did not parse
    COALESCE(collection_week IS NULL, false)                   AS r_bad_week,
    -- HARD: outside the study window
    COALESCE(collection_week < DATE '{train_start}'
             OR collection_week > DATE '{test_end}', false)    AS r_out_of_window,
    -- HARD: second report for the same hospital and week (keep the first;
    -- prefer the HHS-corrected record when one exists)
    COALESCE(row_number() OVER (
        PARTITION BY hospital_pk, collection_week
        ORDER BY is_corrected DESC, _row_id
    ) > 1, false)                                              AS r_duplicate,
    -- HARD: target absent or unparseable
    COALESCE(target_raw IS NULL, false)                        AS r_target_missing,
    -- HARD: negative target that is not the suppression sentinel
    COALESCE(target_raw < 0 AND target_raw <> {suppressed}, false) AS r_target_negative,
    -- FLAG: privacy suppression (true value was below 4)
    COALESCE(target_raw = {suppressed}, false)                 AS r_target_suppressed,
    -- FLAG: more beds in use than staffed inpatient beds
    COALESCE(target_raw >= 0 AND capacity_raw > 0
             AND target_raw > capacity_raw, false)             AS r_used_gt_capacity,
    -- FLAG: capacity suppressed or missing
    COALESCE(capacity_raw IS NULL OR capacity_raw = {suppressed}, true) AS r_capacity_unknown
FROM staging;
