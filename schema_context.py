BILLING_CONTEXT = """
Table/View name: billing

Default Currency:
USD

Business purpose:
This view contains invoice and credit note billing data. It is used to analyze billed revenue, billed tax, invoice splits, customers, regions, subsidiaries, currencies, and inter-company billing.

Grain:
One row per billing transaction/invoice/credit note.

Important filters:
- inter_company_status = 'T' means inter-company transaction.
- inter_company_status = 'F' means external customer transaction.

Columns:

billing_id:
Unique transaction ID for the billing transaction.

txntobaseexchangerate:
Exchange rate from transaction currency to base currency.

billed_tax_amt:
Tax amount in transaction currency.

billed_amt:
Total billed amount in transaction currency.

subscriptionfee:
Subscription revenue component in transaction currency.

implementationfee:
Implementation revenue component in transaction currency.

integrationfee:
Integration revenue component in transaction currency.

studiofee:
Studio revenue component in transaction currency.

otherservicesfee:
Other services revenue component in transaction currency.

openingsplitfee:
Opening split revenue component in transaction currency.

amsfee:
AMS revenue component in transaction currency.

billing_number:
Invoice or credit note number.

billing_date:
Billing transaction date.

fy_quarter:
Financial year quarter, example FY26 Q1.

customer_id:
Customer/entity ID.

customer_name:
Customer name.

region_name:
Standard mapped region name.

txn_currency_id:
Transaction currency ID.

txn_currency_symbol:
Transaction currency symbol.

inr_exchangerate:
Exchange rate used to convert transaction currency to INR.

usd_exchangerate:
Exchange rate used to convert transaction currency to USD.

subsidiary_id:
Subsidiary ID.

subsidiary_name:
Subsidiary Name.

billingentity:
Billing subsidiary.

billedentity:
Billed entity.

subsidiary_country:
Billing subsidiary country.

inter_company_status:
T if inter-company transaction, F if external customer transaction.

Currency Rules:
- All amount, tax, and fee columns are stored in transaction currency.
- To report in USD, multiply the transaction currency amount by usd_exchangerate.
- To report in INR, multiply the transaction currency amount by inr_exchangerate.
- Billing default reporting currency is USD.
- If user does not specify currency, report in USD.
- If user asks for INR, use INR conversion.
- If user asks for USD, use USD conversion.
- Never use billed_amt_usd, billed_amt_inr, billed_tax_amt_usd, or billed_tax_amt_inr because these columns do not exist.
- Always calculate reporting currency amounts inside SQL using exchange rate columns.

Metric Conversion Rules:
- Billed revenue in USD: SUM(billed_amt * usd_exchangerate) AS billed_revenue_usd
- Billed revenue in INR: SUM(billed_amt * inr_exchangerate) AS billed_revenue_inr
- Billed tax in USD: SUM(billed_tax_amt * usd_exchangerate) AS billed_tax_usd
- Billed tax in INR: SUM(billed_tax_amt * inr_exchangerate) AS billed_tax_inr
- Subscription revenue in USD: SUM(subscriptionfee * usd_exchangerate) AS subscription_revenue_usd
- Subscription revenue in INR: SUM(subscriptionfee * inr_exchangerate) AS subscription_revenue_inr
- Implementation revenue in USD: SUM(implementationfee * usd_exchangerate) AS implementation_revenue_usd
- Implementation revenue in INR: SUM(implementationfee * inr_exchangerate) AS implementation_revenue_inr
- Integration revenue in USD: SUM(integrationfee * usd_exchangerate) AS integration_revenue_usd
- Integration revenue in INR: SUM(integrationfee * inr_exchangerate) AS integration_revenue_inr
- Studio revenue in USD: SUM(studiofee * usd_exchangerate) AS studio_revenue_usd
- Studio revenue in INR: SUM(studiofee * inr_exchangerate) AS studio_revenue_inr
- Other services revenue in USD: SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * usd_exchangerate) AS other_services_revenue_usd
- Other services revenue in INR: SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * inr_exchangerate) AS other_services_revenue_inr

Common query rules:
- For external customer reporting, filter inter_company_status = 'F'.
- For inter-company reporting, filter inter_company_status = 'T'.
- If user does not mention inter-company, default to inter_company_status = 'F'.
- For invoice type split, use subscription, implementation, integration, studio, and other services.
- Other Services = amsfee + otherservicesfee + openingsplitfee.
- For quarterly analysis, group by fy_quarter.
- For customer-level analysis, group by customer_name and customer_id.
- For region-level analysis, group by region_name.
- For subsidiary-level analysis, group by subsidiary_name.
- For billing currency analysis, group by txn_currency_symbol.
- Use PostgreSQL syntax only.
- Only generate SELECT queries.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE.
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
- transaction currency
- billed revenue only

Wrong:
- transaction count
- billed tax
- averages
- percentages

User:
"Show billing by currency with tax"

Correct:
- billed revenue
- billed tax

User:
"Show billing by region"

Correct:
- billed revenue only

Only include extra metrics if the user explicitly asks for:
- count
- tax
- average
- percentage
- mix %
- contribution %
- transaction count
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
    region_name,
    fy_quarter,
    SUM(billed_amt * usd_exchangerate) AS billed_revenue_usd
FROM billing
WHERE inter_company_status = 'F'
GROUP BY region_name, fy_quarter

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
    region_name,
    SUM(subscriptionfee * usd_exchangerate) AS subscription_revenue_usd,
    SUM(implementationfee * usd_exchangerate) AS implementation_revenue_usd,
    SUM(integrationfee * usd_exchangerate) AS integration_revenue_usd,
    SUM(studiofee * usd_exchangerate) AS studio_revenue_usd,
    SUM((COALESCE(amsfee,0) + COALESCE(otherservicesfee,0) + COALESCE(openingsplitfee,0)) * usd_exchangerate) AS other_services_revenue_usd
FROM billing
WHERE inter_company_status = 'F'
GROUP BY region_name

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
    "region_name": "Region",
    "fy_quarter": "Financial Quarter",
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