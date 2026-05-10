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