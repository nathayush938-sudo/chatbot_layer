BILLING_SEMANTIC_MODEL = """
BILLING SEMANTIC MODEL

TABLE:
billing

DEFAULT RULES:
- Billing default currency is USD.
- If user asks INR, use INR.
- If user asks USD or does not mention currency, use USD.
- All amount, tax, and fee columns are in transaction currency.
- Convert to USD using usd_exchangerate.
- Convert to INR using inr_exchangerate.
- Default billing filter is external customers only: inter_company_status = 'F'.
- For intercompany billing, use inter_company_status = 'T'.

METRICS:
1. Billing / billed revenue / billed amount / revenue:
   USD: SUM(billed_amt * usd_exchangerate) AS billed_revenue_usd
   INR: SUM(billed_amt * inr_exchangerate) AS billed_revenue_inr

2. Tax / tax amount:
   USD: SUM(COALESCE(billed_tax_amt, 0) * usd_exchangerate) AS tax_amount_usd
   INR: SUM(COALESCE(billed_tax_amt, 0) * inr_exchangerate) AS tax_amount_inr
   IMPORTANT: always use COALESCE(billed_tax_amt, 0) to handle NULL tax values.
   Always use the full alias tax_amount_usd or tax_amount_inr — never just tax_amount.
   Always include "tax_amount_usd": "Tax Amount" or "tax_amount_inr": "Tax Amount"
   in display.columns.

3. Subscription revenue:
   USD: SUM(subscriptionfee * usd_exchangerate) AS subscription_revenue_usd
   INR: SUM(subscriptionfee * inr_exchangerate) AS subscription_revenue_inr

4. Implementation revenue:
   USD: SUM(implementationfee * usd_exchangerate) AS implementation_revenue_usd
   INR: SUM(implementationfee * inr_exchangerate) AS implementation_revenue_inr

5. Integration revenue:
   USD: SUM(integrationfee * usd_exchangerate) AS integration_revenue_usd
   INR: SUM(integrationfee * inr_exchangerate) AS integration_revenue_inr

6. Studio revenue:
   USD: SUM(studiofee * usd_exchangerate) AS studio_revenue_usd
   INR: SUM(studiofee * inr_exchangerate) AS studio_revenue_inr

7. Other service revenue:
   USD: SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * usd_exchangerate) AS other_service_revenue_usd
   INR: SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * inr_exchangerate) AS other_service_revenue_inr

DIMENSIONS:
- region / region wise = region_name
- customer / client / account / billed customer = customer_name
- customer id = customer_id
- quarter / QoQ / quarter-on-quarter / quarterly = fy_quarter
- currency / transaction currency / currency mix = txn_currency_symbol
- billing entity / subsidiary / billing subsidiary / entity = billingentity
  NEVER use subsidiary_name — always use billingentity for entity-level grouping
- billed entity = billedentity
- billing number / invoice number = billing_number
- billing date / invoice date = billing_date
- country = subsidiary_country

TIME RULES:
- Use fy_quarter column for all FY and quarter filtering (format: 'FY26 Q1', 'FY26 Q2', etc.).
- fy_quarter is pre-computed in the view; use it freely in both WHERE and GROUP BY.
- Only use billing_date directly for custom date ranges not expressible as FY/quarter.
- If no time period is specified, default to the previous complete FY
  (e.g. fy_quarter LIKE 'FY26%'). The exact label is provided in the system prompt.
- YTD = filter fy_quarter LIKE '<current_fy>%' as provided in the system prompt.
- Specific FY = fy_quarter LIKE 'FY26%'.
- Specific quarter = fy_quarter = 'FY26 Q2'.
- QoQ / quarter-on-quarter = GROUP BY fy_quarter, ORDER BY fy_quarter ASC.
- Quarterly = GROUP BY fy_quarter.

Sorting Rules:

- Do NOT add ORDER BY to SQL. Python handles all sorting after the query returns.
- Python sort logic:
    - Time dimensions (fy_quarter, date, month, year, period): sorted chronologically ASC
    - All other dimensions (region, customer, entity, currency): sorted by metric value DESC
- Exception: if user asks for "top N" or "bottom N", add ORDER BY + LIMIT N in SQL
  because the DB must rank before limiting.
  For top N: ORDER BY primary_metric_alias DESC LIMIT N
  For bottom N: ORDER BY primary_metric_alias ASC LIMIT N
  Always use SELECT aliases in ORDER BY, never repeat full expressions.

Limit Rules:
- For "top N" or "bottom N" requests, always add LIMIT N to the query.
- Do not use subqueries or ROW_NUMBER() for simple top N ranking; use ORDER BY + LIMIT.
- If the user asks for a ranked/top/bottom report but does not mention a number, apply LIMIT 10 by default.
- If the user asks for the "full list", "all customers", "all regions", or similar, do not apply any LIMIT.
- Examples:
    "top 5 customers"         → LIMIT 5
    "top customers"           → LIMIT 10 (default)
    "bottom 3 regions"        → ORDER BY metric ASC LIMIT 3
    "all customers"           → no LIMIT
    "full list of customers"  → no LIMIT

Important TYPE SPLIT RULES:
When user says:
- billing type split
- type split
- invoice type split
- revenue split
- fee split
- split by type
- invoice split
- revenue type split

ALWAYS include ALL of these metric columns — no exceptions, regardless of other rules:
- subscription revenue
- implementation revenue
- integration revenue
- studio revenue
- other service revenue
- tax amount   ← ALWAYS included in type split, even without explicit mention

Tax amount is a CORE part of invoice type split by definition.
STRICT_METRIC_SELECTION_RULES does NOT apply to type splits — include all 6 columns always.

CRITICAL: Always return visualization = "pivot_table" and pivot_type = "metric" for type splits.
NEVER return visualization = "table" for a type split, even if there is no grouping dimension.
When there is no grouping dimension (overall split only):
  - visualization = "pivot_table"
  - pivot_type = "metric"
  - rows = []   ← empty list, no dimension
  - metric_columns = [all the revenue + tax aliases]
  - SQL has no GROUP BY
When a dimension is present (e.g. region, quarter):
  - visualization = "pivot_table"
  - pivot_type = "metric"
  - rows = [dimension]
  - metric_columns = [all 6 revenue + tax aliases]
  - SQL has GROUP BY dimension


REPORT STRUCTURE RULES:
1. If user asks one dimension only:
   Example: "billing by region"
   Return normal grouped table:
   GROUP BY region_name

2. If user asks top/bottom/highest/lowest:
   Return ranking table ordered by selected metric.

3. If user asks quarter-on-quarter, QoQ, quarterly, or trend:
   Group by fy_quarter.

4. If user asks dimension + type split:
   Example: "region and type split"
   Return metric pivot:
   rows = region_name
   metric_columns = revenue split metrics

5. If user asks two dimensions with split/mix/breakdown:
   Example: "currency mix by quarter"
   Return dimension pivot:
   rows = first dimension
   columns = second dimension
   values = billed revenue

6. If user asks intercompany billing by billing entity and billed entity:
   Return dimension pivot:
   rows = billing_entity
   columns = billed_entity
   values = billed amount
   filter inter_company_status = 'T'

7. Do not add extra metrics automatically.
   If user asks billing by currency, only return billed revenue.
   Do not add transaction count, tax, percentage, average unless user asks.

COMMON DASHBOARD REPORTS:
1. YTD Billing - Invoice Type Split:
   metric pivot with rows = invoice type metrics, values = amount and percentage if user asks percentage.

2. QoQ Billing - Invoice Type Split:
   metric pivot with rows = fy_quarter and metric columns = subscription, implementation, integration, studio, other service, tax only if asked.

3. Billing Currency Mix:
   dimension pivot with rows = txn_currency_symbol, columns = fy_quarter, values = billed revenue.

4. YTD Billing - Billing Entity Split:
   grouped table by billingentity, value = billed revenue.

5. Top Billed Customers:
   grouped table by customer_name, value = billed revenue, ordered descending.

6. YTD Billing - Region Split:
   grouped table by region_name, value = billed revenue.

7. Intercompany Billing:
   dimension pivot with rows = billingentity, columns = billedentity, values = billed amount, filter inter_company_status = 'T'.

DIMENSION VALIDATION:
Valid billing dimensions (only these can be used in GROUP BY):
  region_name, customer_name, customer_id, fy_quarter,
  txn_currency_symbol, billingentity, billedentity,
  billing_number, billing_date, subsidiary_country
NOTE: subsidiary_name is NOT a valid dimension. Use billingentity instead.

If the user mentions a word that is NOT in this list as a grouping dimension:
- Do NOT use it as a GROUP BY column.
- Do NOT silently ignore it and return an aggregate with no GROUP BY.
- Set explanation to clearly state: "'<word>' is not a valid dimension.
  Valid dimensions are: region, customer, quarter, currency, subsidiary, etc."
- Still generate the best possible SQL (e.g. overall total if no valid dimension given).

DIMENSION VALIDATION:
Valid collections dimensions (only these can be used in GROUP BY):
  region_name, customer_name, customer_id, fy_quarter,
  txn_currency_symbol, billing_entity, billed_entity,
  payment_number, payment_date, invoice_number, invoice_date,
  due_date, subsidiary_country, ageingbucket

If the user mentions a word that is NOT in this list as a grouping dimension:
- Do NOT use it as a GROUP BY column.
- Do NOT silently ignore it and return an aggregate with no GROUP BY.
- Set explanation to clearly state: "'<word>' is not a valid dimension.
  Valid dimensions are: region, customer, quarter, currency, billing entity, ageing bucket, etc."
- Still generate the best possible SQL (e.g. overall total if no valid dimension given).

DISPLAY RULES:
- Always include display metadata.
- display.title should be short and report-like.
- display.currency should be USD or INR.
- display.columns should map SQL aliases to clean display names.
- display.formatting should define currency formatting for all amount columns.

SQL OPTIMISATION RULES:
- Do NOT add ORDER BY to SQL unless it is a top N / bottom N query. Python sorts the results.
- Never repeat full SUM expressions anywhere. Always use SELECT aliases.
- Keep SQL minimal: SELECT, FROM, WHERE, GROUP BY only. No ORDER BY unless top/bottom N.
- Always use fy_quarter for time filtering (not billing_date) unless user gives a custom date range.
  Good: WHERE fy_quarter LIKE 'FY26%'
  Bad:  WHERE billing_date >= '2025-04-01' AND billing_date <= '2026-03-31'
- All metric aliases MUST include a currency suffix: _usd or _inr. Never use bare aliases like
  tax_amount, subscription_revenue. Always: tax_amount_usd, subscription_revenue_usd, etc.
- display.columns MUST map every SQL alias to a clean display name.
  Every alias in SELECT must have a corresponding entry in display.columns.
- Display names must NOT include the currency suffix in brackets.
  Bad:  "subscription_revenue_usd": "Subscription Revenue (USD)"
  Good: "subscription_revenue_usd": "Subscription Revenue"
  The currency symbol ($, ₹) on the formatted amount already communicates the currency.
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
- If user asks USD, use USD.
- If user asks INR or does not mention currency, use INR.
- collection_amt is in transaction currency. Always convert using exchange rate columns.
- Default filter: inter_company_status = 'F' (external customers only).
- TDS is INCLUDED by default. Only exclude TDS when user explicitly asks for
  "net collections", "collections excluding tax", or "excluding TDS".
- For intercompany collections, use inter_company_status = 'T'.

METRICS:
1. Collections / collected amount / receipts / payments received / gross collections:
   INR: SUM(collection_amt * inr_exchangerate) AS collection_inr
   USD: SUM(collection_amt * usd_exchangerate) AS collection_usd
   Filter: no tds_flag filter (include all rows)

2. Net collections / collections excluding TDS / collections excluding tax /
   collections net of TDS / after TDS / TDS deducted / total collections minus TDS /
   collections TDS-deducted:
   INR: SUM(collection_amt * inr_exchangerate) AS net_collection_inr  WHERE tds_flag = 'F'
   USD: SUM(collection_amt * usd_exchangerate) AS net_collection_usd  WHERE tds_flag = 'F'
   Filter: tds_flag = 'F' (exclude TDS rows)

3. TDS amount / TDS collected / tax deducted / only TDS / show TDS:
   INR: SUM(collection_amt * inr_exchangerate) AS tds_amount_inr  WHERE tds_flag = 'T'
   USD: SUM(collection_amt * usd_exchangerate) AS tds_amount_usd  WHERE tds_flag = 'T'
   Filter: tds_flag = 'T' (only TDS rows)

TDS TERMINOLOGY DISAMBIGUATION:
- "TDS deducted" / "net of TDS" / "after TDS" / "excluding TDS" / "TDS-deducted"
  / "total minus TDS" / "collections TDS deducted" / "tax-deducted" / "tax deducted"
  / "collections, tax-deducted" / "collections net" / "net collection"
  → ALL mean net collections → ONE metric only → filter tds_flag = 'F'
  → Do NOT return both total_collections and tds_amount together

- "TDS amount" / "TDS collected" / "show TDS" / "only TDS" / "tax deducted at source"
  / "show me TDS" / "how much TDS"
  → mean the TDS component only → ONE metric → filter tds_flag = 'T'

- "gross collections" / "total collections" / "all collections" (with no TDS mention)
  → include all rows → no tds_flag filter

- "total collections and TDS" / "collections with TDS breakup" / "show both"
  → TWO metrics: total_collections_inr (no tds filter) + tds_amount_inr (tds_flag = 'T')

CRITICAL: If the user uses "tax-deducted" or "TDS-deducted" as a QUALIFIER after
"total collections", treat it as a filter (net collections), NOT as a second metric.
"total collections, tax-deducted" = net collections only = tds_flag = 'F', ONE column.

DIMENSIONS:
- region / region wise = region_name
- customer / client / account = customer_name
- customer id = customer_id
- quarter / QoQ / quarterly = fy_quarter
- currency / transaction currency / currency mix = txn_currency_symbol
- subsidiary / billing entity = billing_entity
- billed entity = billed_entity (intercompany only)
- payment number = payment_number
- payment date = payment_date
- invoice number = invoice_number
- invoice date = invoice_date
- due date = due_date
- country = subsidiary_country
- ageing / aging / bucket / delay bucket = ageingbucket

AGEING BUCKET RULES:
- Valid ageingbucket values in logical order:
    'Within CP', '1-15 days', '16-30 days', '31-45 days', '46-60 days', '61-90 days', '>90 days'
- Never sort ageingbucket alphabetically. Always use CASE WHEN for ORDER BY:
    ORDER BY CASE ageingbucket
      WHEN 'Within CP'  THEN 1
      WHEN '1-15 days'  THEN 2
      WHEN '16-30 days' THEN 3
      WHEN '31-45 days' THEN 4
      WHEN '46-60 days' THEN 5
      WHEN '61-90 days' THEN 6
      WHEN '>90 days'   THEN 7
    END

TIME RULES:
- Use fy_quarter column for all FY and quarter filtering (format: 'FY26 Q1', 'FY26 Q2', etc.).
- fy_quarter is pre-computed in the view; use it freely in both WHERE and GROUP BY.
- Only use payment_date directly for custom date ranges not expressible as FY/quarter.
- If no time period is specified, default to the previous complete FY
  (e.g. fy_quarter LIKE 'FY26%'). The exact label is provided in the system prompt.
- YTD = filter fy_quarter LIKE '<current_fy>%' as provided in the system prompt.
- Specific FY = fy_quarter LIKE 'FY26%'.
- Specific quarter = fy_quarter = 'FY26 Q2'.
- QoQ / quarter-on-quarter = GROUP BY fy_quarter, ORDER BY fy_quarter ASC.
- Quarterly = GROUP BY fy_quarter.

SORTING RULES:
- Do NOT add ORDER BY to SQL. Python handles all sorting after the query returns.
- Exception: if user asks for "top N" or "bottom N", add ORDER BY + LIMIT N in SQL
  because the DB must rank before limiting.
  For top N: ORDER BY primary_metric_alias DESC LIMIT N
  For bottom N: ORDER BY primary_metric_alias ASC LIMIT N
  Always use SELECT aliases in ORDER BY, never repeat full expressions.
- Exception: ageing bucket reports — use CASE WHEN ORDER BY in SQL so bucket order
  is always correct regardless of Python sorting:
  ORDER BY CASE ageingbucket
    WHEN 'Within CP'  THEN 1
    WHEN '1-15 days'  THEN 2
    WHEN '16-30 days' THEN 3
    WHEN '31-45 days' THEN 4
    WHEN '46-60 days' THEN 5
    WHEN '61-90 days' THEN 6
    WHEN '>90 days'   THEN 7
  END

LIMIT RULES:
- For "top N" or "bottom N" requests, always add LIMIT N to the query.
- Do not use subqueries or ROW_NUMBER() for simple top N ranking; use ORDER BY + LIMIT.
- If the user asks for a ranked/top/bottom report but does not mention a number, apply LIMIT 10 by default.
- If the user asks for the "full list", "all customers", "all regions", or similar, do not apply any LIMIT.
- Examples:
    "top 5 customers"         → LIMIT 5
    "top customers"           → LIMIT 10 (default)
    "bottom 3 regions"        → ORDER BY metric ASC LIMIT 3
    "all customers"           → no LIMIT
    "full list of customers"  → no LIMIT

REPORT STRUCTURE RULES:
1. One dimension only:
   Example: "collections by region"
   Return grouped table: GROUP BY region_name, ORDER BY collection_usd DESC

2. Top/bottom customers or entities:
   Return ranking table ordered by collection metric DESC.

3. Quarterly / QoQ:
   Group by fy_quarter, ORDER BY fy_quarter ASC.

4. Ageing analysis:
   Group by ageingbucket, use CASE WHEN ORDER BY.
   Example: "collections by ageing bucket"

5. Ageing + dimension (pivot):
   Example: "collections by region and ageing bucket"
   Return dimension pivot:
     rows = region_name
     columns = ageingbucket
     values = collection_usd
   SQL returns LONG format. Frontend pivots dynamically.

6. Intercompany collections:
   Filter inter_company_status = 'T'.
   Use billing_entity and billed_entity dimensions.
   Example: dimension pivot with rows = billing_entity, columns = billed_entity.

7. Net collections / excluding TDS:
   Add tds_flag = 'F' to WHERE clause.

8. Currency mix:
   Group by txn_currency_symbol (and optionally fy_quarter for QoQ).

9. Do not add extra metrics automatically.
   If user asks collections by region, only return collection amount.
   Do not add TDS amount, count, or percentages unless user asks.

COMMON DASHBOARD REPORTS:
1. YTD Collections - Region Split:
   Grouped table by region_name, value = collection_usd, filter fy_quarter LIKE 'FY26%'.

2. QoQ Collections:
   Grouped table by fy_quarter, value = collection_usd, ORDER BY fy_quarter ASC.

3. Collections by Ageing Bucket:
   Grouped table by ageingbucket, value = collection_usd, ORDER BY CASE WHEN ageing sort.

4. Collections by Ageing and Region:
   Dimension pivot: rows = region_name, columns = ageingbucket, values = collection_usd.

5. Top Customers by Collections:
   Grouped table by customer_name, value = collection_usd, ORDER BY collection_usd DESC.

6. Collections Currency Mix:
   Grouped table or dimension pivot: rows = txn_currency_symbol,
   columns = fy_quarter (if QoQ requested), values = collection_usd.

7. Net Collections (Excluding TDS):
   Any of the above with tds_flag = 'F' added to WHERE.

8. Intercompany Collections:
   Dimension pivot: rows = billing_entity, columns = billed_entity,
   values = collection_usd, filter inter_company_status = 'T'.

9. YTD Collections - Billing Entity Split:
   Grouped table by billing_entity, value = collection_usd, filter fy_quarter LIKE 'FY26%'.

DISPLAY RULES:
- Always include display metadata.
- display.title should be short and report-like.
- display.currency should be USD or INR.
- display.columns should map SQL aliases to clean display names.
- display.formatting should define currency formatting for all amount columns.

SQL OPTIMISATION RULES:
- Do NOT add ORDER BY to SQL unless it is a top N / bottom N or ageing bucket query. Python sorts results.
- Never repeat full SUM expressions anywhere. Always use SELECT aliases.
- Keep SQL minimal: SELECT, FROM, WHERE, GROUP BY only. No ORDER BY unless top/bottom N or ageing.
- Always use fy_quarter for time filtering (not payment_date) unless user gives a custom date range.
  Good: WHERE fy_quarter LIKE 'FY26%'
  Bad:  WHERE payment_date >= '2025-04-01' AND payment_date <= '2026-03-31'
"""