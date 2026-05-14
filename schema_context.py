BILLING_CONTEXT = """
Table/View name: billing

Default Currency: USD

Business purpose:
Invoice and credit note billing data. Analyse billed revenue, tax, invoice type splits,
customers, regions, subsidiaries, currencies, and inter-company billing.

Grain: One row per billing transaction (CustInvc or CustCred).

Default filter: inter_company_status = 'F'.

Columns:
transaction_id: Unique internal ID of the billing transaction.
transaction_number: Human-readable transaction number (e.g. INV-00123).
transaction_type: CustInvc or CustCred.
transaction_currency_id: ID of transaction currency.
transaction_date: Date the transaction was created.
duedate: Due date of the invoice.
transaction_amount: Total amount in transaction currency. Also aliased as billing_amount.
billing_amount: Same as transaction_amount. Primary metric column for billing.
transaction_amount_paid: Amount paid so far.
transaction_amount_unpaid: Amount still outstanding.
transaction_tax: Tax amount in transaction currency. Use COALESCE(transaction_tax,0).
transaction_exchange_rate: Base exchange rate (used internally for fee calculations).
memo: Transaction memo field.
transaction_fy_quarter: FY quarter of transaction date. Example: FY26 Q1, FY27 Q2.
inr_exchangerate: Rate from transaction currency to INR.
usd_exchangerate: Rate from transaction currency to USD.
customer_id: Internal customer ID.
customer_ucc: Unique customer code.
customer_name: Customer company name.
ucc_parent: UCC of parent company.
entity_id: Customer entity ID.
region: Mapped region name of the customer.
country: Country of the customer.
client_journey_stage: Churned, Customer Success, Implementation, One Time, Potential Churn.
client_buckets: Churned Account, Non-Issue, Issue.
collection_status: Collection follow-up status.
subsidiary_id: ID of billing subsidiary.
subsidiary_name: Name of billing entity / subsidiary.
paying_entity: Paying entity name (intercompany only).
currency_symbol: Symbol of transaction currency.
inter_company_status: T = intercompany, F = external.
subscriptionfee: Subscription revenue in transaction currency.
implementationfee: Implementation revenue in transaction currency.
integrationfee: Integration revenue in transaction currency.
studiofee: Studio revenue in transaction currency.
otherservicesfee: Other services revenue in transaction currency.
openingsplitfee: Opening split revenue in transaction currency.
amsfee: AMS revenue in transaction currency.

Currency Rules:
- All amount, tax, and fee columns are in transaction currency.
- USD: multiply by usd_exchangerate. INR: multiply by inr_exchangerate.
- Default: USD. Never use pre-computed currency columns.

Metric Conversion Rules:
- Billed revenue (incl tax) USD: SUM(billing_amount * usd_exchangerate) AS billed_revenue_usd
- Billed revenue (incl tax) INR: SUM(billing_amount * inr_exchangerate) AS billed_revenue_inr
- Billed revenue excl tax USD: SUM((billing_amount - COALESCE(transaction_tax,0)) * usd_exchangerate) AS billed_revenue_excl_tax_usd
- Billed revenue excl tax INR: SUM((billing_amount - COALESCE(transaction_tax,0)) * inr_exchangerate) AS billed_revenue_excl_tax_inr
- Tax USD: SUM(COALESCE(transaction_tax,0) * usd_exchangerate) AS tax_amount_usd
- Tax INR: SUM(COALESCE(transaction_tax,0) * inr_exchangerate) AS tax_amount_inr
- Subscription USD: SUM(subscriptionfee * usd_exchangerate) AS subscription_revenue_usd
- Implementation USD: SUM(implementationfee * usd_exchangerate) AS implementation_revenue_usd
- Integration USD: SUM(integrationfee * usd_exchangerate) AS integration_revenue_usd
- Studio USD: SUM(studiofee * usd_exchangerate) AS studio_revenue_usd
- Other services USD: SUM((COALESCE(amsfee,0)+COALESCE(otherservicesfee,0)+COALESCE(openingsplitfee,0)) * usd_exchangerate) AS other_services_revenue_usd

Common Query Rules:
- Default: inter_company_status = 'F'.
- Quarterly: GROUP BY transaction_fy_quarter.
- Region: GROUP BY region.
- Subsidiary: GROUP BY subsidiary_name.
- Currency: GROUP BY currency_symbol.
- Only SELECT. Never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- PostgreSQL syntax only.
"""

STRICT_METRIC_SELECTION_RULES = """
Metric Selection Rules:

- Only return metrics explicitly requested by the user.
- Do not add additional metrics unless the user asks for them.
- Do not add billed tax, counts, averages, or percentages unless explicitly requested.
- Do not add transaction counts unless explicitly requested.
- Do not add explanatory KPIs automatically.
- Keep output minimal and aligned to user request.

Examples:

User:
"Show billing by transaction currency mix"

Correct:
- currency_symbol (dimension)
- billed revenue only: SUM(billing_amount * usd_exchangerate)

Wrong:
- transaction count
- tax amount
- averages
- percentages

User:
"Show billing by currency with tax"

Correct:
- billed revenue: SUM(billing_amount * usd_exchangerate)
- tax amount: SUM(COALESCE(transaction_tax,0) * usd_exchangerate)

User:
"Show billing by region"

Correct:
- billed revenue only: SUM(billing_amount * usd_exchangerate)

Only include extra metrics if the user explicitly asks for:
- count
- tax
- average
- percentage
- mix %
- contribution %
- transaction count

EXCEPTION - Invoice / Revenue Type Split:
Tax amount is ALWAYS included when user asks for any type split / invoice split / revenue split.
It is a core component of the split definition, not an extra metric.
"""


PRESENTATION_RULES = """
Presentation Rules:

There are 4 possible visualization types:
1. table
2. bar_chart
3. line_chart
4. pivot_table

-----------------------------------
STANDARD TABLE RULES
-----------------------------------

Use:
- table for detailed records
- bar_chart for rankings/comparisons
- line_chart for trends over time

Examples:
- top customers -> bar_chart
- quarterly trend -> line_chart
- raw invoice listing -> table

-----------------------------------
PIVOT TABLE RULES
-----------------------------------

If the user asks for:
- pivot
- matrix
- cross tab
- rows and columns
- "X in rows and Y in columns"

then use:
visualization = "pivot_table"

There are TWO pivot types.

-----------------------------------
1. DIMENSION PIVOT
-----------------------------------

Use when:
- rows and columns are both dimensions/categories

Examples:
- region in rows and quarter in columns
- subsidiary in rows and region in columns

Return JSON format:

{
  "visualization": "pivot_table",
  "pivot_type": "dimension",
  "rows": ["dimension"],
  "columns": ["dimension"],
  "values": ["metric"],
  "aggregation": "sum"
}

Rules:
- SQL should return LONG format data.
- Do NOT hardcode pivot SQL.
- Do NOT generate CASE WHEN pivot columns.
- Python frontend will pivot dynamically.
- Use currency conversion inside SQL based on selected reporting currency.
- For billing, if currency is not mentioned, default to USD.
- For USD billing metrics, multiply transaction currency amounts by usd_exchangerate.
- For INR billing metrics, multiply transaction currency amounts by inr_exchangerate.

Example SQL:
SELECT
    region,
    transaction_fy_quarter,
    SUM(billing_amount * usd_exchangerate) AS billed_revenue_usd
FROM billing
WHERE inter_company_status = 'F'
GROUP BY region, transaction_fy_quarter

-----------------------------------
2. METRIC PIVOT
-----------------------------------

Use when:
- columns are multiple metrics/measures

Examples:
- region in rows and invoice split in columns
- customer in rows and revenue split in columns
- quarter in rows and subscription vs implementation vs other services in columns

Available billing metric columns in transaction currency:
- subscriptionfee
- implementationfee
- integrationfee
- studiofee
- otherservicesfee
- openingsplitfee
- amsfee

Invoice split metric grouping:
- subscription revenue = subscriptionfee
- implementation revenue = implementationfee
- integration revenue = integrationfee
- studio revenue = studiofee
- other services revenue = amsfee + otherservicesfee + openingsplitfee

Return JSON format:

{
  "visualization": "pivot_table",
  "pivot_type": "metric",
  "rows": ["dimension"],
  "metric_columns": [
      "subscription_revenue_usd",
      "implementation_revenue_usd",
      "integration_revenue_usd",
      "studio_revenue_usd",
      "other_services_revenue_usd"
  ],
  "aggregation": "sum"
}

Rules:
- SQL should aggregate metric columns directly.
- Do NOT unpivot metrics.
- Return one row per grouping dimension.
- Use currency conversion inside SQL based on selected reporting currency.
- For billing, if currency is not mentioned, default to USD.
- For USD billing metrics, multiply transaction currency amounts by usd_exchangerate.
- For INR billing metrics, multiply transaction currency amounts by inr_exchangerate.
- Metric aliases must include the selected currency suffix, for example _usd or _inr.

Example SQL:
SELECT
    region,
    SUM(subscriptionfee * usd_exchangerate) AS subscription_revenue_usd,
    SUM(implementationfee * usd_exchangerate) AS implementation_revenue_usd,
    SUM(integrationfee * usd_exchangerate) AS integration_revenue_usd,
    SUM(studiofee * usd_exchangerate) AS studio_revenue_usd,
    SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * usd_exchangerate) AS other_services_revenue_usd
FROM billing
WHERE inter_company_status = 'F'
GROUP BY region

-----------------------------------
DISPLAY RULES
-----------------------------------

Always include a display object in JSON.

display must contain:
- title: user-friendly report title
- currency: selected reporting currency, for example USD or INR
- columns: mapping of SQL output aliases to user-friendly column names
- formatting: formatting rules for numeric columns

Example display object:

"display": {
  "title": "Billing by Region and Quarter",
  "currency": "USD",
  "columns": {
    "region": "Region",
    "transaction_fy_quarter": "Financial Quarter",
    "billed_revenue_usd": "Billed Revenue (USD)"
  },
  "formatting": {
    "billed_revenue_usd": {
      "type": "currency",
      "currency": "USD",
      "decimals": 0
    }
  }
}

-----------------------------------
GENERAL RULES
-----------------------------------

- Use PostgreSQL syntax only.
- Only SELECT statements allowed.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
- Use only tables and columns provided in context.
- Return valid JSON only.
- Do not include markdown or code fences.
- Only include JSON fields relevant to the query type.
"""


# ─────────────────────────────────────────────
# COLLECTIONS
# ─────────────────────────────────────────────

COLLECTIONS_CONTEXT = """
Table/View name: collections

Default Currency: INR

Business purpose:
Payment/collection data linked to invoices. Analyse collected amounts, collection timelines,
ageing buckets, customers, regions, subsidiaries, and inter-company collections.

Grain: One row per payment-to-invoice link.

Default filters: inter_company_status = 'F' AND tds_flag = 'F'.

Columns:
transaction_id: Unique internal ID of the collection/payment transaction.
transaction_number: Human-readable transaction number.
transaction_type: CustPymt, Deposit, or Journal.
transaction_currency_id: ID of transaction currency.
transaction_date: Date of the payment/collection.
duedate: Due date of the payment transaction.
transaction_amount: Total of the payment transaction (one payment may cover multiple invoices).
transaction_amount_paid: Amount paid.
transaction_amount_unpaid: Amount unpaid.
transaction_tax: Tax on the transaction.
memo: Memo field (used to derive tds_flag).
transaction_fy_quarter: FY quarter of payment date. Example: FY26 Q1.
collection_due_date: Due date of the linked invoice.
collection_amount: Amount applied to this specific invoice. USE THIS for all metrics.
inr_exchangerate: Rate from transaction currency to INR.
usd_exchangerate: Rate from transaction currency to USD.
customer_id: Internal customer ID.
customer_ucc: Unique customer code.
customer_name: Customer company name.
ucc_parent: UCC of parent company.
entity_id: Customer entity ID.
region: Mapped region name of the customer.
country: Country of the customer.
client_journey_stage: Churned, Customer Success, Implementation, One Time, Potential Churn.
client_buckets: Churned Account, Non-Issue, Issue.
collection_status: Collection follow-up status.
subsidiary_id: ID of billing subsidiary.
subsidiary_name: Name of billing entity / subsidiary.
paying_entity: Paying entity name (intercompany only).
currency_symbol: Symbol of transaction currency.
inter_company_status: T = intercompany, F = external.
tds_flag: T = TDS payment (memo contains 'tds'), F = regular collection.
ageingbucket: Ageing relative to invoice due date.
  Values (in order): 'Within CP', '1-15 days', '16-30 days', '31-45 days',
  '46-60 days', '61-90 days', '>90 days'

Currency Rules:
- collection_amount is in transaction currency.
- INR: collection_amount * inr_exchangerate. USD: collection_amount * usd_exchangerate.
- Default: INR. Never use pre-computed currency columns.

Metric Conversion Rules:
- Net collections INR (default): SUM(collection_amount * inr_exchangerate) WHERE tds_flag = 'F'
- Net collections USD: SUM(collection_amount * usd_exchangerate) WHERE tds_flag = 'F'
- Gross collections INR (incl TDS): SUM(collection_amount * inr_exchangerate)
- TDS amount INR: SUM(collection_amount * inr_exchangerate) WHERE tds_flag = 'T'

Common Query Rules:
- Default: inter_company_status = 'F' AND tds_flag = 'F'.
- Quarterly: GROUP BY transaction_fy_quarter.
- Ageing: GROUP BY ageingbucket (never sort alphabetically).
- Region: GROUP BY region.
- Subsidiary: GROUP BY subsidiary_name.
- Currency: GROUP BY currency_symbol.
- Only SELECT. Never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- PostgreSQL syntax only.
"""


# ─────────────────────────────────────────────
# ACCOUNTS RECEIVABLE (AR)
AR_CONTEXT = """
Table/View name: ar

Default Currency: USD

Business purpose:
Open AR transactions - invoices, credit notes, and payments representing the net outstanding
receivable position as of today.

Grain: One row per open transaction. open_amount is signed (positive=invoice, negative=credit).
SUM(open_amount) gives net AR naturally.

Default filter: inter_company_status = 'F'.
AR is a real-time snapshot - no time-period WHERE filtering.
transaction_fy_quarter is a GROUP BY dimension only (invoice creation quarter).

Columns:
transaction_id: Unique internal ID.
transaction_number: Human-readable transaction number.
transaction_type: CustInvc, CustCred, CustPymt, Deposit, Journal.
transaction_currency_id: ID of transaction currency.
transaction_date: Date transaction was created.
duedate: Due date of the invoice.
transaction_amount: Total amount of the transaction.
transaction_amount_paid: Amount paid so far.
transaction_amount_unpaid: Amount still outstanding.
transaction_tax: Tax on the transaction.
transaction_fy_quarter: FY quarter the transaction was raised. GROUP BY only, never WHERE.
inr_exchangerate: Rate from transaction currency to INR.
usd_exchangerate: Rate from transaction currency to USD.
customer_id: Internal customer ID.
customer_ucc: Unique customer code.
customer_name: Customer company name.
ucc_parent: UCC of parent company.
entity_id: Customer entity ID.
region: Mapped region name of the customer.
country: Country of the customer.
client_journey_stage: Churned, Customer Success, Implementation, One Time, Potential Churn.
client_buckets: Churned Account, Non-Issue, Issue.
collection_status: Collection follow-up status.
subsidiary_id: ID of billing subsidiary.
subsidiary_name: Name of billing entity / subsidiary.
paying_entity: Paying entity name (intercompany only).
currency_symbol: Symbol of transaction currency.
inter_company_status: T = intercompany, F = external.
open_days: CURRENT_DATE - COALESCE(duedate, transaction_date). Positive = overdue.
open_amount: Net open amount in transaction currency. Positive=invoice, negative=credit.

Currency Rules:
- open_amount is in transaction currency.
- USD: open_amount * usd_exchangerate. INR: open_amount * inr_exchangerate.
- Default: USD. Never use pre-computed currency columns.

Metric Definitions:
- Net Outstanding USD: SUM(open_amount * usd_exchangerate)
- Overdue USD: SUM(open_amount * usd_exchangerate) WHERE open_days >= 1
- Current USD: SUM(open_amount * usd_exchangerate) WHERE open_days < 1

Ageing Bucket Definitions:
- Current: open_days < 1
- 1-30 days: open_days BETWEEN 1 AND 30
- 31-60 days: open_days BETWEEN 31 AND 60
- 61-90 days: open_days BETWEEN 61 AND 90
- 91-180 days: open_days BETWEEN 91 AND 180
- >180 days: open_days > 180

Ageing Bucket SQL (wide format, USD default):
SUM(CASE WHEN open_days < 1 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_current_usd,
SUM(CASE WHEN open_days BETWEEN 1 AND 30 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_1_30_usd,
SUM(CASE WHEN open_days BETWEEN 31 AND 60 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_31_60_usd,
SUM(CASE WHEN open_days BETWEEN 61 AND 90 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_61_90_usd,
SUM(CASE WHEN open_days BETWEEN 91 AND 180 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_91_180_usd,
SUM(CASE WHEN open_days > 180 THEN open_amount * usd_exchangerate ELSE 0 END) AS bucket_over_180_usd

Common Query Rules:
- Always filter inter_company_status = 'F' unless user asks for intercompany.
- AR is always as of today - no time-period WHERE filtering.
- transaction_fy_quarter: GROUP BY only.
- No tds_flag in AR.
- PostgreSQL syntax only. Only SELECT queries.
"""