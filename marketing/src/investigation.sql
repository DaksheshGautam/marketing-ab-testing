-- 01. Source schema
-- Which fields were actually supplied?
PRAGMA table_info(raw_marketing);

-- 02. Source coverage
-- What is the analysis unit and how many outcomes exist?
SELECT COUNT(*) rows, COUNT(DISTINCT "user id") users,
SUM(converted) conversions FROM raw_marketing;

-- 03. Missingness
-- Are exclusions needed for missing source values?
SELECT SUM("user id" IS NULL) user_null,
SUM("test group" IS NULL) group_null, SUM(converted IS NULL) converted_null,
SUM("total ads" IS NULL) ads_null, SUM("most ads day" IS NULL) day_null,
SUM("most ads hour" IS NULL) hour_null FROM raw_marketing;

-- 04. Duplicate user IDs
-- Could repeated users violate the independent-user analysis?
SELECT COUNT(*) duplicate_users, COALESCE(SUM(n-1),0) extra_rows
FROM (SELECT user_id,COUNT(*) n FROM marketing GROUP BY user_id HAVING COUNT(*)>1);

-- 05. Outcome and assignment categories
-- Are group labels and binary outcomes valid?
SELECT test_group,converted,COUNT(*) users FROM marketing
GROUP BY test_group,converted ORDER BY test_group,converted;

-- 06. Range checks
-- Do exposure and time values fit their definitions?
SELECT MIN(total_ads) min_ads,MAX(total_ads) max_ads,
MIN(peak_hour) min_hour,MAX(peak_hour) max_hour,
SUM(total_ads<0 OR peak_hour NOT BETWEEN 0 AND 23) invalid_rows
FROM marketing;

-- 07. Index audit
-- Is the extra index a usable analytical variable?
SELECT COUNT(*) rows,COUNT(DISTINCT "Unnamed: 0") distinct_index,
MIN("Unnamed: 0") first_index,MAX("Unnamed: 0") last_index
FROM raw_marketing;

-- 08. Cleaning reconciliation
-- Did preparation change outcomes or cohort size?
SELECT COUNT(*) users,COUNT(DISTINCT user_id) distinct_users,
SUM(converted) conversions,SUM(total_ads) impressions FROM marketing;

-- 09. Allocation
-- How unequal are the observed arm sizes?
SELECT test_group,COUNT(*) users,
1.0*COUNT(*)/(SELECT COUNT(*) FROM marketing) user_share
FROM marketing GROUP BY test_group;

-- 10. Primary outcomes
-- What are the conversion rates and correct denominators?
SELECT test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) conversion_rate FROM marketing GROUP BY test_group;

-- 11. Exposure volume
-- How much exposure is associated with each arm?
SELECT test_group,SUM(total_ads) impressions,AVG(total_ads) ads_per_user,
AVG(CASE WHEN converted=1 THEN total_ads END) ads_per_converter,
AVG(CASE WHEN converted=0 THEN total_ads END) ads_per_nonconverter
FROM marketing GROUP BY test_group;

-- 12. Frequency-band outcomes
-- How does conversion vary with observed exposure?
SELECT frequency_band,test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) rate,SUM(total_ads) impressions FROM marketing
GROUP BY frequency_band,test_group ORDER BY frequency_band,test_group;

-- 13. Weekday outcomes
-- How do rates vary by peak-exposure weekday?
SELECT day_order,peak_day,test_group,COUNT(*) users,
SUM(converted) conversions,AVG(converted) rate FROM marketing
GROUP BY day_order,peak_day,test_group ORDER BY day_order,test_group;

-- 14. Hour outcomes
-- What is the observed peak-hour conversion profile?
SELECT peak_hour,test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) rate FROM marketing GROUP BY peak_hour,test_group
ORDER BY peak_hour,test_group;

-- 15. Day-hour cells
-- What data support the heatmap?
SELECT day_order,peak_day,peak_hour,test_group,COUNT(*) users,
SUM(converted) conversions,AVG(converted) rate FROM marketing
GROUP BY day_order,peak_day,peak_hour,test_group
ORDER BY day_order,peak_hour,test_group;

-- 16. Sparse day-hour cells
-- Where should heatmap comparisons be treated cautiously?
SELECT test_group,COUNT(*) cells,SUM(n<100) cells_under_100_users,
SUM(c<10) cells_under_10_conversions FROM
(SELECT test_group,peak_day,peak_hour,COUNT(*) n,SUM(converted) c
FROM marketing GROUP BY test_group,peak_day,peak_hour) GROUP BY test_group;

-- 17. Extreme exposures
-- How concentrated is the long tail?
SELECT test_group,COUNT(*) users,SUM(total_ads) impressions,
SUM(converted) conversions FROM marketing WHERE total_ads>202.0
GROUP BY test_group;

-- 18. Exposure-trim sensitivity
-- Does the sign persist after a common tail exclusion?
SELECT test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) rate FROM marketing WHERE total_ads<=202.0
GROUP BY test_group;

-- 19. Outcome by exposure band share
-- How does the exposure mix differ between arms?
SELECT frequency_band,test_group,COUNT(*) users,
1.0*COUNT(*)/SUM(COUNT(*)) OVER(PARTITION BY test_group) within_arm_share
FROM marketing GROUP BY frequency_band,test_group ORDER BY frequency_band,test_group;

-- 20. Counterfactual conversion calculation
-- What would the ad arm produce at the PSA rate?
WITH a AS (SELECT COUNT(*) n,SUM(converted) c FROM marketing WHERE test_group='ad'),
p AS (SELECT AVG(converted) rate FROM marketing WHERE test_group='psa')
SELECT a.n ad_users,a.c observed_ad_conversions,p.rate psa_rate,
a.n*p.rate expected_at_psa_rate,a.c-a.n*p.rate modeled_incremental FROM a,p;

-- 21. Weekday contrasts with multiplicity
-- Which weekday contrasts remain after a common correction?
SELECT segment weekday,n_psa,n_ad,delta*100 lift_pp,
ci_low*100 ci_low_pp,ci_high*100 ci_high_pp,p_value,holm_p
FROM weekday_effects ORDER BY "order";

-- 22. Hour contrasts with multiplicity
-- How much does multiple testing change hour-level evidence?
SELECT segment hour,n_psa,c_psa,n_ad,delta*100 lift_pp,
ci_low*100 ci_low_pp,ci_high*100 ci_high_pp,p_value,holm_p
FROM hour_effects ORDER BY segment;