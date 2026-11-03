-- 02_staging.sql: typed copy of the columns we use. No rows are removed here.
-- Numbers: commas stripped ("-999,999" and "-999999" both parse); text that
-- does not parse becomes NULL and is counted by 03_validate.sql.
-- The suppression sentinel is KEPT at this stage; 04_clean.sql handles it.
CREATE OR REPLACE MACRO num(x) AS TRY_CAST(replace(trim(x), ',', '') AS DOUBLE);

CREATE OR REPLACE TABLE staging AS
SELECT
    _row_id,
    nullif(trim(hospital_pk), '')                    AS hospital_pk,
    nullif(trim(ccn), '')                            AS ccn,
    hospital_name,
    nullif(trim(state), '')                          AS state,
    hospital_subtype,
    is_metro_micro,
    lower(trim(is_corrected)) IN ('true', 't', '1')  AS is_corrected,
    COALESCE(
        TRY_STRPTIME(trim(collection_week), '%Y/%m/%d'),
        TRY_STRPTIME(trim(collection_week), '%Y-%m-%d'),
        TRY_STRPTIME(trim(collection_week), '%m/%d/%Y'),
        TRY_STRPTIME(trim(collection_week), '%Y-%m-%dT%H:%M:%S.%g')
    )::DATE                                          AS collection_week,
    num({target})                                    AS target_raw,
    num({capacity})                                  AS capacity_raw,
    num(inpatient_beds_used_7_day_coverage)          AS target_coverage,
    num(total_beds_7_day_avg)                        AS total_beds_raw,
    num(inpatient_beds_used_covid_7_day_avg)         AS covid_inpatients_raw,
    num(total_patients_hospitalized_confirmed_influenza_7_day_avg) AS flu_inpatients_raw,
    num(icu_beds_used_7_day_avg)                     AS icu_used_raw,
    num(total_icu_beds_7_day_avg)                    AS icu_beds_raw
FROM raw;
