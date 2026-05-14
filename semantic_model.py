BILLING_SEMANTIC_MODEL = """
BILLING SEMANTIC MODEL

TABLE:
billing

DEFAULT RULES:
- Billing default currency is USD.
- If user asks INR, use INR. Otherwise use USD.
- All amount, tax, and fee columns are in transaction currency. Always convert using exchange rate columns.
- Default filter: inter_company_status = 'F' (external customers only).
- For intercompany billing: inter_company_status = 'T'.
- No tds_flag in billing. Tax is handled via transaction_tax column (a metric, not a row filter).

TAX IN BILLING:
- billing_amount (= transaction_amount) already includes tax.
- Default: SUM(billing_amount * rate) — includes tax.
- "excluding tax" / "ex-tax" / "net of tax": SUM((billing_amount - COALESCE(transaction_tax,0)) * rate)
- "tax amount" / "show tax": SUM(COALESCE(transaction_tax,0) * rate)
- Never use tds_flag. Never filter rows for tax — use column arithmetic only.

METRICS:
1. Billed revenue / billing / billed amount (DEFAULT — tax included):
   USD: SUM(billing_amount * usd_exchangerate) AS billed_revenue_usd
   INR: SUM(billing_amount * inr_exchangerate) AS billed_revenue_inr

2. Billed revenue EXCLUDING tax:
   USD: SUM((billing_amount - COALESCE(transaction_tax,0)) * usd_exchangerate) AS billed_revenue_excl_tax_usd
   INR: SUM((billing_amount - COALESCE(transaction_tax,0)) * inr_exchangerate) AS billed_revenue_excl_tax_inr

3. Tax amount:
   USD: SUM(COALESCE(transaction_tax,0) * usd_exchangerate) AS tax_amount_usd
   INR: SUM(COALESCE(transaction_tax,0) * inr_exchangerate) AS tax_amount_inr
   ALWAYS use COALESCE(transaction_tax,0).

4. Subscription revenue:
   USD: SUM(subscriptionfee * usd_exchangerate) AS subscription_revenue_usd
   INR: SUM(subscriptionfee * inr_exchangerate) AS subscription_revenue_inr

5. Implementation revenue:
   USD: SUM(implementationfee * usd_exchangerate) AS implementation_revenue_usd
   INR: SUM(implementationfee * inr_exchangerate) AS implementation_revenue_inr

6. Integration revenue:
   USD: SUM(integrationfee * usd_exchangerate) AS integration_revenue_usd
   INR: SUM(integrationfee * inr_exchangerate) AS integration_revenue_inr

7. Studio revenue:
   USD: SUM(studiofee * usd_exchangerate) AS studio_revenue_usd
   INR: SUM(studiofee * inr_exchangerate) AS studio_revenue_inr

8. Other service revenue (AMS + other services + opening split):
   USD: SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * usd_exchangerate) AS other_services_revenue_usd
   INR: SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * inr_exchangerate) AS other_services_revenue_inr

DIMENSIONS:
- customer / customer name / account    = customer_name
- entity id                             = entity_id
- customer ucc / ucc                    = customer_ucc
- parent / ucc parent                   = ucc_parent
- region / region wise                  = region
- country                               = country
- client journey / journey stage / CJS  = client_journey_stage
  Values: Churned, Customer Success, Implementation, One Time, Potential Churn
- client bucket / account health        = client_buckets
  Values: Churned Account, Non-Issue, Issue
- collection status                     = collection_status
- quarter / QoQ / quarterly             = transaction_fy_quarter
- currency / transaction currency       = currency_symbol
- subsidiary / billing entity           = subsidiary_name
  NEVER use subsidiary_name as a column — always use subsidiary_name for billing entity grouping.
- paying entity / billed entity         = paying_entity (intercompany only)
- transaction type / type               = transaction_type
  Values: CustInvc, CustCred
- transaction date / billing date       = transaction_date
- due date                              = duedate
- transaction number / invoice number  = transaction_number

DIMENSION VALIDATION:
Valid billing dimensions (only these can be used in GROUP BY):
  customer_name, entity_id, customer_ucc, ucc_parent,
  region, country, client_journey_stage, client_buckets,
  collection_status, transaction_fy_quarter, currency_symbol,
  subsidiary_name, paying_entity, transaction_type,
  transaction_date, duedate
NOTE: subsidiary_name is the correct column for billing entity. Never use old names like
subsidiary_name is the ONLY correct column name for billing entity.

ID COLUMN RULES:
- Never SELECT customer_id, transaction_id, subsidiary_id, transaction_currency_id
  unless explicitly requested.
- For customer-level reports, SELECT customer_name only.

TIME RULES:
- Use transaction_fy_quarter for all FY and quarter filtering.
- Available data: FY25, FY26, FY27 (YTD). Format: 'FY26 Q1', 'FY27 Q2'.
- DEFAULT (no time mentioned): current FY YTD → transaction_fy_quarter LIKE '<current_fy>%'
- "last year" / "previous year"   → transaction_fy_quarter LIKE '<previous_fy>%'
- "FY25" / "two years ago"        → transaction_fy_quarter LIKE '<two_years_ago_fy>%'
- "this quarter"                  → transaction_fy_quarter = '<current_quarter>'
- "last quarter"                  → transaction_fy_quarter = '<last_quarter>'
- "all time" / "all years"        → no time filter
- "by year"                       → GROUP BY LEFT(transaction_fy_quarter, 4) AS fy_year
- "by quarter" / "QoQ"            → GROUP BY transaction_fy_quarter
- Only use transaction_date for custom date ranges not expressible as FY/quarter.

Sorting Rules:
- Do NOT add ORDER BY to SQL. Python handles all sorting.
- Exception: top N / bottom N → add ORDER BY alias DESC/ASC + LIMIT N.
- Time dimensions (transaction_fy_quarter, fy_year): chronological ASC.
- All other dimensions: value DESC.

Limit Rules:
- Top N without number → default LIMIT 10.
- Full breakdowns → no LIMIT.

Important TYPE SPLIT RULES:
When user says "invoice type split", "type split", "revenue split", "fee split":
ALWAYS include ALL of these — tax is a core component:
- subscription revenue
- implementation revenue
- integration revenue
- studio revenue
- other service revenue
- tax amount (ALWAYS included in type split)
STRICT_METRIC_SELECTION_RULES does NOT apply to type splits.
visualization = "pivot_table", pivot_type = "metric", rows = [dimension if any, else []]

COMMON DASHBOARD REPORTS:
1. YTD Billing: SUM(billing_amount * usd_exchangerate) filtered to current FY
2. QoQ Billing: GROUP BY transaction_fy_quarter
3. Billing by Region: GROUP BY region
4. Billing by Subsidiary: GROUP BY subsidiary_name
5. Billing by Customer: GROUP BY customer_name
6. Billing by Currency: GROUP BY currency_symbol
7. Billing Invoice Type Split (overall): metric pivot, rows=[], 6 metric columns + tax
8. Billing by Region and Type Split: metric pivot, rows=[region], metric_columns=[all 6+tax]
9. Intercompany Billing: inter_company_status='T', dimension pivot rows=subsidiary_name cols=paying_entity
10. Billing by Client Bucket: GROUP BY client_buckets
11. Billing by Customer Journey: GROUP BY client_journey_stage

SQL OPTIMISATION RULES:
- No ORDER BY unless top N. Python sorts.
- Never repeat SUM expressions. Use SELECT aliases.
- All metric aliases MUST include currency suffix: _usd or _inr.
- Display names must NOT include currency suffix in brackets.
- Keep SQL minimal: SELECT, FROM, WHERE, GROUP BY only.

DISPLAY RULES:
- display.title: short and report-like.
- display.currency: USD or INR.
- display.columns: map every alias to a clean display name (no currency suffix).
- display.formatting: currency type for all amount columns.
"""


# ─────────────────────────────────────────────
# COLLECTIONS
# ─────────────────────────────────────────────

COLLECTIONS_SEMANTIC_MODEL = """
COLLECTIONS SEMANTIC MODEL

TABLE:
collections

DEFAULT RULES:
- Collections default currency is INR.
- If user asks USD, use USD. Otherwise use INR.
- collection_amount is in transaction currency. Always convert using exchange rate columns.
- Default filters: inter_company_status = 'F' AND tds_flag = 'F' (net collections).
- TDS excluded by default. Override only when user says "including TDS" or "gross collections".
- For intercompany: inter_company_status = 'T'.

METRICS:
1. Collections (DEFAULT — net of TDS):
   INR: SUM(collection_amount * inr_exchangerate) AS collection_inr  WHERE tds_flag = 'F'
   USD: SUM(collection_amount * usd_exchangerate) AS collection_usd  WHERE tds_flag = 'F'
   Always use collection_amount — NOT transaction_amount.

2. Gross collections (including TDS — user must explicitly ask):
   INR: SUM(collection_amount * inr_exchangerate) AS gross_collection_inr   ← no tds_flag filter
   USD: SUM(collection_amount * usd_exchangerate) AS gross_collection_usd

3. TDS amount only:
   INR: SUM(collection_amount * inr_exchangerate) AS tds_amount_inr  WHERE tds_flag = 'T'
   USD: SUM(collection_amount * usd_exchangerate) AS tds_amount_usd  WHERE tds_flag = 'T'

TDS TERMINOLOGY DISAMBIGUATION:
DEFAULT → tds_flag = 'F' always applied.
"TDS deducted" / "net" / "excluding TDS" / "tax-deducted" → same as default (tds_flag = 'F')
"including TDS" / "gross" / "with TDS" → remove tds_flag filter
"TDS amount" / "only TDS" → tds_flag = 'T'
"total and TDS" / "show both" → two metrics: collection_inr (tds='F') + tds_amount_inr (tds='T')
TIME RULES:
- Use transaction_fy_quarter for all FY/quarter filtering (payment date quarter).
- Available data: FY25, FY26, FY27 (YTD).
- DEFAULT: current FY YTD → transaction_fy_quarter LIKE '<current_fy>%'
- "last year" / "previous year"   → transaction_fy_quarter LIKE '<previous_fy>%'
- "FY25" / "two years ago"        → transaction_fy_quarter LIKE '<two_years_ago_fy>%'
- "this quarter"                  → transaction_fy_quarter = '<current_quarter>'
- "last quarter"                  → transaction_fy_quarter = '<last_quarter>'
- "all time" / "all years"        → no time filter
- "by year"                       → GROUP BY LEFT(transaction_fy_quarter, 4) AS fy_year
- "by quarter" / "QoQ"            → GROUP BY transaction_fy_quarter
- Custom date range               → use transaction_date directly

AGEING BUCKET RULES:
Valid values in sort order: 'Within CP', '1-15 days', '16-30 days', '31-45 days',
'46-60 days', '61-90 days', '>90 days'
Never sort alphabetically. Always use CASE WHEN ORDER BY or Python AGEING_ORDER.

SORTING RULES:
- No ORDER BY in SQL. Python handles sorting.
- Ageing bucket: AGEING_ORDER (Within CP first)
- Time columns: chronological ASC
- All others: value DESC
- Exception: top/bottom N → ORDER BY alias + LIMIT N

LIMIT RULES:
- Top N without number → LIMIT 10
- Full breakdown → no LIMIT

DETAIL QUERY RULES:
When user asks "show collections for [customer]", "list payments for [customer]":
- SELECT without GROUP BY.
- visualization = "table"
- Columns in order:
    1. customer_name
    2. subsidiary_name
    3. region
    4. transaction_date
    5. collection_due_date
    6. ageingbucket
    7. collection_amount * inr_exchangerate AS collection_inr
    8. currency_symbol
    9. transaction_number
    10. transaction_id ← last
- Filters: inter_company_status = 'F' AND tds_flag = 'F' AND customer_name ILIKE '%XYZ%'
- No GROUP BY, no aggregation.

COMMON DASHBOARD REPORTS:
1. YTD Collections: SUM(collection_amount * inr_exchangerate) WHERE tds_flag='F', current FY
2. QoQ Collections: GROUP BY transaction_fy_quarter
3. Collections by Ageing Bucket: CASE WHEN GROUP BY ageingbucket
4. Collections by Region: GROUP BY region
5. Collections by Subsidiary: GROUP BY subsidiary_name
6. Collections by Customer: GROUP BY customer_name (top 10 default)
7. Collections by Currency: GROUP BY currency_symbol
8. Collections by Client Bucket: GROUP BY client_buckets
9. Collections by Customer Journey: GROUP BY client_journey_stage
10. Intercompany Collections: inter_company_status='T', pivot rows=subsidiary_name cols=paying_entity
11. Cumulative Ageing by Quarter: dimension pivot rows=transaction_fy_quarter cols=ageingbucket

SQL OPTIMISATION RULES:
- No ORDER BY unless top N. Python sorts.
- Never repeat SUM expressions. Use SELECT aliases.
- All metric aliases: _inr or _usd suffix.
- Display names: no currency suffix in brackets.
- Keep SQL minimal: SELECT, FROM, WHERE, GROUP BY only.

DISPLAY RULES:
- display.title: short and report-like.
- display.currency: INR (or USD if user asks).
- display.columns: map every alias to clean display name.
- display.formatting: currency type for all amount columns.
"""


# ─────────────────────────────────────────────
# ACCOUNTS RECEIVABLE
# ─────────────────────────────────────────────

AR_SEMANTIC_MODEL = """
AR SEMANTIC MODEL

TABLE:
ar

DEFAULT RULES:
- AR default currency is USD.
- If user asks INR, use INR. Otherwise use USD.
- open_amount is in transaction currency. Always convert using exchange rate columns.
- Always filter inter_company_status = 'F' unless user explicitly asks for intercompany.
- AR is a real-time snapshot as of today. No time-period WHERE filtering.
- transaction_fy_quarter is a GROUP BY dimension only (quarter invoice was raised) — not a filter.
- open_amount is signed: positive for invoices, negative for credits/payments.
  SUM(open_amount * rate) gives net AR position naturally.

METRICS:
1. Net Outstanding / Total AR / Open AR (DEFAULT):
   USD: SUM(open_amount * usd_exchangerate) AS outstanding_usd
   INR: SUM(open_amount * inr_exchangerate) AS outstanding_inr
   Filter: inter_company_status = 'F'

2. Gross Outstanding / Invoices only:
   USD: SUM(open_amount * usd_exchangerate) AS outstanding_usd WHERE transaction_type = 'CustInvc'

3. Amount Overdue:
   USD: SUM(open_amount * usd_exchangerate) AS overdue_usd  WHERE open_days >= 1
   INR: SUM(open_amount * inr_exchangerate) AS overdue_inr  WHERE open_days >= 1

4. Amount Current (not yet due):
   USD: SUM(open_amount * usd_exchangerate) AS current_usd  WHERE open_days < 1
   INR: SUM(open_amount * inr_exchangerate) AS current_inr  WHERE open_days < 1

5. Invoice Count:
   COUNT(DISTINCT transaction_id) AS invoice_count

AGEING BUCKET METRICS (for metric pivot / wide format — USD default):
bucket_current_usd:   SUM(CASE WHEN open_days < 1 THEN open_amount * usd_exchangerate ELSE 0 END)
bucket_1_30_usd:      SUM(CASE WHEN open_days BETWEEN 1 AND 30 THEN open_amount * usd_exchangerate ELSE 0 END)
bucket_31_60_usd:     SUM(CASE WHEN open_days BETWEEN 31 AND 60 THEN open_amount * usd_exchangerate ELSE 0 END)
bucket_61_90_usd:     SUM(CASE WHEN open_days BETWEEN 61 AND 90 THEN open_amount * usd_exchangerate ELSE 0 END)
bucket_91_180_usd:    SUM(CASE WHEN open_days BETWEEN 91 AND 180 THEN open_amount * usd_exchangerate ELSE 0 END)
bucket_over_180_usd:  SUM(CASE WHEN open_days > 180 THEN open_amount * usd_exchangerate ELSE 0 END)

Display names for ageing bucket metrics:
  bucket_current_usd   → "Current"
  bucket_1_30_usd      → "1-30 Days"
  bucket_31_60_usd     → "31-60 Days"
  bucket_61_90_usd     → "61-90 Days"
  bucket_91_180_usd    → "91-180 Days"
  bucket_over_180_usd  → ">180 Days"

DIMENSIONS:
- customer / customer name / account     = customer_name
- entity id / customer entity            = entity_id
- customer ucc / ucc                     = customer_ucc
- parent / ucc parent                    = ucc_parent
- region / region wise                   = region
- country                                = country
- client journey / journey stage / CJS   = client_journey_stage
  Values: Churned, Customer Success, Implementation, One Time, Potential Churn
- client bucket / account health / bucket = client_buckets
  Values: Churned Account, Non-Issue, Issue
- collection status / follow-up status   = collection_status
  Values: Acknowledged, Churned Account, Potential Churn, Agreement / Renewal,
  Implementation Issue / Implementation Delays, Invoice revision, Other Issues,
  Payment Date, Pending Acknowledgement, Product Issue
- billing entity / subsidiary            = subsidiary_name
- paying entity                          = paying_entity (intercompany only)
- currency / transaction currency        = currency_symbol
- transaction type / type                = transaction_type
  Values: CustInvc, CustCred, CustPymt, Deposit, Journal
- transaction quarter / invoice quarter  = transaction_fy_quarter (GROUP BY only, not WHERE filter)
- transaction date / invoice date        = transaction_date
- due date                               = duedate
- ageing bucket                          = derived via CASE WHEN on open_days

DIMENSION VALIDATION:
Valid AR dimensions (only these can be used in GROUP BY):
  customer_name, entity_id, customer_ucc, ucc_parent,
  region, country, client_journey_stage, client_buckets,
  collection_status, subsidiary_name, paying_entity,
  currency_symbol, transaction_type, transaction_fy_quarter,
  transaction_date, duedate, ageing_bucket (derived)

ID COLUMN RULES:
- Never SELECT customer_id, transaction_id, subsidiary_id, transaction_currency_id
  unless explicitly requested.
- For customer-level reports, SELECT customer_name and/or entity_id only.

AGEING BUCKET RULES:
When user asks for AR by ageing bucket (bucket as a row dimension):
  SELECT
    CASE
      WHEN open_days < 1              THEN 'Current'
      WHEN open_days BETWEEN 1 AND 30 THEN '1-30 days'
      WHEN open_days BETWEEN 31 AND 60 THEN '31-60 days'
      WHEN open_days BETWEEN 61 AND 90 THEN '61-90 days'
      WHEN open_days BETWEEN 91 AND 180 THEN '91-180 days'
      WHEN open_days > 180            THEN '>180 days'
    END AS ageing_bucket,
    SUM(open_amount * usd_exchangerate) AS outstanding_usd
  FROM ar
  WHERE inter_company_status = 'F'
  GROUP BY ageing_bucket

When user asks for AR by [dimension] and ageing split (buckets as columns):
  Use metric pivot: visualization = "pivot_table", pivot_type = "metric"
  rows = [dimension], metric_columns = [bucket_current_usd, bucket_1_30_usd, ...]

Ageing bucket display order (always enforce):
  Current → 1-30 days → 31-60 days → 61-90 days → 91-180 days → >180 days

SORTING RULES:
- Do NOT add ORDER BY to SQL. Python handles all sorting.
- Exception: top N / bottom N → add ORDER BY alias DESC/ASC + LIMIT N.
- Ageing bucket rows: sorted by AR_AGEING_ORDER
- All other dimensions: sorted by metric value DESC

LIMIT RULES:
- Top N without number → default LIMIT 10.
- Full breakdown ("by region", "by bucket") → no LIMIT.

AR AGING SUMMARY REPORT:
When user asks for "AR aging summary", "AR summary", "aging summary", "AR report":
- visualization = "table"
- CRITICAL: Use entity_id (customer entity ID). Do NOT use subsidiary_id or subsidiary_name.
- SQL:
  SELECT
      entity_id,
      customer_name,
      client_buckets,
      collection_status,
      client_journey_stage,
      SUM(CASE WHEN open_days < 1 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_current_usd,
      SUM(CASE WHEN open_days BETWEEN 1 AND 30 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_1_30_usd,
      SUM(CASE WHEN open_days BETWEEN 31 AND 60 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_31_60_usd,
      SUM(CASE WHEN open_days BETWEEN 61 AND 90 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_61_90_usd,
      SUM(CASE WHEN open_days BETWEEN 91 AND 180 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_91_180_usd,
      SUM(CASE WHEN open_days > 180 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_over_180_usd,
      SUM(open_amount * usd_exchangerate) AS total_outstanding_usd,
      SUM(CASE WHEN open_days >= 1 THEN open_amount * usd_exchangerate ELSE 0 END) AS total_overdue_usd
  FROM ar
  WHERE inter_company_status = 'F'
  GROUP BY entity_id, customer_name, client_buckets, collection_status, client_journey_stage
- display.columns must map:
    entity_id              → "Entity ID"
    customer_name          → "Customer"
    client_buckets         → "Client Bucket"
    collection_status      → "Collection Status"
    client_journey_stage   → "Customer Journey"
    bucket_current_usd     → "Current"
    bucket_1_30_usd        → "1-30 Days"
    bucket_31_60_usd       → "31-60 Days"
    bucket_61_90_usd       → "61-90 Days"
    bucket_91_180_usd      → "91-180 Days"
    bucket_over_180_usd    → ">180 Days"
    total_outstanding_usd  → "Total Outstanding"
    total_overdue_usd      → "Total Overdue"
- display.formatting: currency (USD) for all bucket and total columns.
- No Row % — multiple metrics make it ambiguous.
- Sort by total_outstanding_usd DESC.

DETAIL QUERY RULES:
When user asks "show billing for [customer]", "list invoices for [customer]",
"billing data for [customer]", "show transactions for [customer]":
- ALWAYS use SELECT * — never list individual columns.
- visualization = "table"
- Simple lookup SQL:
  SELECT *
  FROM billing
  WHERE inter_company_status = 'F'
    AND customer_name ILIKE '%XYZ%'
- CTE/subquery SQL (e.g. "transactions for top customer"):
  WITH derived AS (
    SELECT customer_name FROM billing
    WHERE inter_company_status = 'F'
    GROUP BY customer_name ORDER BY SUM(billing_amount * usd_exchangerate) DESC LIMIT 1
  )
  SELECT *
  FROM billing
  WHERE inter_company_status = 'F'
    AND customer_name = (SELECT customer_name FROM derived)
- No GROUP BY in outer query, no aggregation, no Row %, no Grand Total.
- Use ILIKE for name filtering, = for exact match (e.g. from subquery).
- Default: no LIMIT on outer query unless user specifies.
- Frontend handles column ordering automatically.

COMMON DASHBOARD REPORTS:

─── KPI REPORTS ────────────────────────────────────────────────────────────────

1. Total AR KPIs / AR Overview / AR Dashboard KPIs:
   When user asks for "AR KPIs", "AR overview", "AR dashboard", "show me AR summary":
   Return ONE row with all key KPIs as metric columns.
   SQL:
   SELECT
       SUM(open_amount * usd_exchangerate) AS total_outstanding_usd,
       SUM(CASE WHEN open_days >= 1 THEN open_amount * usd_exchangerate ELSE 0 END) AS total_overdue_usd,
       SUM(CASE WHEN client_buckets = 'Issue' THEN open_amount * usd_exchangerate ELSE 0 END) AS outstanding_issue_usd,
       SUM(CASE WHEN client_buckets = 'Non-Issue' THEN open_amount * usd_exchangerate ELSE 0 END) AS outstanding_non_issue_usd,
       SUM(CASE WHEN client_journey_stage = 'Customer Success' THEN open_amount * usd_exchangerate ELSE 0 END) AS outstanding_cs_usd,
       SUM(CASE WHEN client_journey_stage = 'Implementation' THEN open_amount * usd_exchangerate ELSE 0 END) AS outstanding_impl_usd,
       SUM(CASE WHEN client_journey_stage = 'Potential Churn' THEN open_amount * usd_exchangerate ELSE 0 END) AS outstanding_churn_usd
   FROM ar WHERE inter_company_status = 'F'
   display.columns: map each alias to clean name (Total Outstanding, Total Overdue,
   Outstanding - Issue, Outstanding - Non-Issue, Outstanding - Customer Success,
   Outstanding - Implementation, Outstanding - Potential Churn)
   visualization = "table" → frontend renders as KPI cards (single row, multiple metrics)

─── DUAL-METRIC TABLE REPORTS (Outstanding + Overdue + Ratio) ──────────────────

For all reports below, use this SQL pattern with CTE:
  WITH base AS (
      SELECT
          <dimension>,
          SUM(open_amount * usd_exchangerate) AS outstanding_usd,
          SUM(CASE WHEN open_days >= 1 THEN open_amount * usd_exchangerate ELSE 0 END) AS overdue_usd
      FROM ar
      WHERE inter_company_status = 'F'
      GROUP BY <dimension>
  )
  SELECT
      <dimension>,
      outstanding_usd,
      overdue_usd,
      ROUND(overdue_usd / NULLIF(outstanding_usd, 0), 3) AS overdue_pct_of_outstanding
  FROM base
  -- overdue_pct_of_outstanding is a decimal (e.g. 0.773 = 77.3%) NOT a percentage (not 77.3)
  -- Frontend formats it with {x:.1%} so always return as 0-1 decimal

display.columns must map:
  outstanding_usd              → "Amount Outstanding"
  overdue_usd                  → "Amount Overdue"
  overdue_pct_of_outstanding   → "Overdue as % of Outstanding"
display.formatting: currency (USD) for outstanding_usd and overdue_usd.
  overdue_pct_of_outstanding: type = "percentage", decimals = 1
visualization = "table"
Python frontend computes Outstanding % and Overdue % (grand total %) automatically.

2. AR by Region:
   dimension = region, apply dual-metric pattern above.

3. AR by Subsidiary / Billing Entity:
   dimension = subsidiary_name, apply dual-metric pattern above.

4. AR by Currency:
   dimension = currency_symbol, apply dual-metric pattern above.

5. AR by Client Bucket:
   dimension = client_buckets, apply dual-metric pattern above.

6. AR by Collection Status:
   dimension = collection_status, apply dual-metric pattern above.

7. AR by Customer Journey:
   dimension = client_journey_stage, apply dual-metric pattern above.

─── PIVOT REPORTS ───────────────────────────────────────────────────────────────

8. Client Journey Split / Client Bucket × Journey Stage:
   When user asks for "client journey split", "bucket by journey", "journey split":
   Dimension pivot:
     visualization = "pivot_table", pivot_type = "dimension"
     rows = ["client_buckets"]
     columns = ["client_journey_stage"]
     values = ["outstanding_usd"]
     aggregation = "sum"
   SQL (long format):
   SELECT
       COALESCE(client_buckets, 'Unassigned') AS client_buckets,
       COALESCE(client_journey_stage, 'Unassigned') AS client_journey_stage,
       SUM(open_amount * usd_exchangerate) AS outstanding_usd
   FROM ar WHERE inter_company_status = 'F'
   GROUP BY client_buckets, client_journey_stage

9. AR by Ageing Bucket: CASE WHEN GROUP BY → sorted by AR_AGEING_ORDER
10. AR Ageing Split by Region: metric pivot → rows = region, columns = buckets
11. Top Customers by AR: GROUP BY customer_name ORDER BY outstanding_usd DESC LIMIT 10
12. AR by Transaction Quarter: GROUP BY transaction_fy_quarter (invoice creation quarter only)
13. AR Aging Summary: full summary table (see above)

SQL OPTIMISATION RULES:
- No ORDER BY unless top N / bottom N. Python sorts.
- Never repeat SUM expressions. Use SELECT aliases.
- Keep SQL minimal: SELECT, FROM, WHERE, GROUP BY only.
- For ageing GROUP BY, always use CASE WHEN inline.

DISPLAY RULES:
- Always include display metadata.
- display.title should be short and report-like.
- display.currency = USD (or INR if user asks).
- display.columns must map every alias to a clean display name (no currency suffix).
- display.formatting must define currency type for all amount columns.
"""   