-- 01_raw.sql: load the CSV exactly as received.
-- Every column stays text, so nothing is silently converted or lost here.
-- _row_id records file order, so every later count can be traced to a row.
CREATE OR REPLACE TABLE raw AS
SELECT
    row_number() OVER () AS _row_id,
    *
FROM read_csv(
    '{raw_csv}',
    header = true,
    all_varchar = true,
    sample_size = -1
);
