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
   USD: SUM(billed_tax_amt * usd_exchangerate) AS tax_amount_usd
   INR: SUM(billed_tax_amt * inr_exchangerate) AS tax_amount_inr

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
- subsidiary / billing entity = subsidiary_name
- billed entity = billed_entity
- billing entity = billing_entity
- billing number / invoice number = billing_number
- billing date / invoice date = billing_date
- country = subsidiary_country

TIME RULES:
- YTD means current financial year to date.
- Current financial year is FY26.
- For YTD, filter fy_quarter LIKE 'FY26%'.
- QoQ / quarter-on-quarter means group by fy_quarter.
- Quarterly means group by fy_quarter.

Sorting Rules:

- Unless user explicitly asks alphabetical ordering, reports should be ordered by business importance/value.
- For grouped tables:
  ORDER BY primary metric DESC

- For pivots/matrices:
  row entities should be ordered by total metric DESC.
  column entities should also preferably follow total metric DESC.

- Region splits, customer splits, subsidiary splits:
  order by billed revenue DESC.

- Top reports:
  always order by metric DESC.

- Do not default to alphabetical ordering unless explicitly requested.

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

Interpret as metric pivot with these columns:
- subscription revenue
- implementation revenue
- integration revenue
- studio revenue
- other service revenue
- tax amount


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
   grouped table by subsidiary_name, value = billed revenue.

5. Top Billed Customers:
   grouped table by customer_name, value = billed revenue, ordered descending.

6. YTD Billing - Region Split:
   grouped table by region_name, value = billed revenue.

7. Intercompany Billing:
   dimension pivot with rows = subsidiary_name AS billing_entity, columns = customer_name AS billed_entity, values = billed amount, filter inter_company_status = 'T'.

DISPLAY RULES:
- Always include display metadata.
- display.title should be short and report-like.
- display.currency should be USD or INR.
- display.columns should map SQL aliases to clean display names.
- display.formatting should define currency formatting for all amount columns.
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
1. Collections / collected amount / receipts / payments received:
   INR: SUM(collection_amt * inr_exchangerate) AS collection_inr
   USD: SUM(collection_amt * usd_exchangerate) AS collection_usd

2. Net collections / collections excluding TDS / collections excluding tax:
   INR: SUM(collection_amt * inr_exchangerate) AS net_collection_inr  WHERE tds_flag = 'F'
   USD: SUM(collection_amt * usd_exchangerate) AS net_collection_usd  WHERE tds_flag = 'F'

3. TDS amount / tax collected:
   INR: SUM(collection_amt * inr_exchangerate) AS tds_amount_inr  WHERE tds_flag = 'T'
   USD: SUM(collection_amt * usd_exchangerate) AS tds_amount_usd  WHERE tds_flag = 'T'

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
- YTD means current financial year to date.
- Current financial year is FY26.
- For YTD, filter fy_quarter LIKE 'FY26%'.
- QoQ / quarter-on-quarter means group by fy_quarter.
- Quarterly means group by fy_quarter.

SORTING RULES:
- For grouped tables: ORDER BY primary metric DESC.
- For ageing bucket reports: ORDER BY ageingbucket using the CASE WHEN sort defined above.
- For top/bottom reports: always order by metric DESC.
- Do not default to alphabetical ordering unless explicitly requested.

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
"""