from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from sqlalchemy import create_engine, text
import pandas as pd
import os

from schema_context import (
    BILLING_CONTEXT,
    COLLECTIONS_CONTEXT,
    PRESENTATION_RULES,
    STRICT_METRIC_SELECTION_RULES,
)
from semantic_model import BILLING_SEMANTIC_MODEL, COLLECTIONS_SEMANTIC_MODEL

app = FastAPI()

api_key = os.getenv("ANTHROPIC_API_KEY")
database_url = os.getenv("DATABASE_URL")

client = Anthropic(api_key=api_key)
engine = create_engine(database_url) if database_url else None


class ChatRequest(BaseModel):
    message: str


TOOLS = [
    {
        "name": "generate_sql_response",
        "description": "Generate SQL and display metadata for finance analytics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "sql": {"type": "string"},
                "visualization": {
                    "type": "string",
                    "enum": ["table", "bar_chart", "line_chart", "pivot_table"]
                },
                "pivot_type": {
                    "type": "string",
                    "enum": ["dimension", "metric"]
                },
                "rows": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "values": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "metric_columns": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "aggregation": {"type": "string"},
                "explanation": {"type": "string"},
                "display": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "currency": {"type": "string"},
                        "columns": {
                            "type": "object",
                            "additionalProperties": {"type": "string"}
                        },
                        "formatting": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "currency": {"type": "string"},
                                    "decimals": {"type": "integer"}
                                }
                            }
                        }
                    },
                    "required": ["title", "columns"]
                }
            },
            "required": [
                "intent",
                "sql",
                "visualization",
                "explanation",
                "display"
            ]
        }
    }
]


# ─────────────────────────────────────────────
# DOMAIN ROUTING
# ─────────────────────────────────────────────

COLLECTION_KEYWORDS = [
    "collection", "collections", "collected",
    "receipt", "receipts",
    "payment received", "payments received",
    "outstanding", "overdue",
    "ageing", "aging", "age bucket", "ageing bucket", "aging bucket",
    "dso", "days sales outstanding",
    "tds", "tax deducted",
    "net collection", "net collections",
    "delay", "delayed", "days late",
    "due date", "past due",
    "collection by", "collect",
]

BILLING_KEYWORDS = [
    "billing", "billed", "bill",
    "invoice", "invoiced",
    "revenue",
    "subscription fee", "implementation fee",
    "integration fee", "studio fee",
    "other service",
    "billed amount", "billed revenue",
    "subscriptionfee", "implementationfee",
]


def classify_domain(message: str) -> str:
    """
    Returns 'collections' or 'billing' based on keyword scoring.
    Collections keywords take priority over billing when scores are tied
    because billing is the legacy domain and collections is the new one.
    Defaults to 'billing' if no keywords match.
    """
    msg = message.lower()

    collection_score = sum(1 for kw in COLLECTION_KEYWORDS if kw in msg)
    billing_score = sum(1 for kw in BILLING_KEYWORDS if kw in msg)

    if collection_score > billing_score:
        return "collections"
    return "billing"


def build_system_prompt(domain: str) -> str:
    if domain == "collections":
        return f"""
You are a finance analytics assistant specializing in collections.

Use the following table/view context:

{COLLECTIONS_CONTEXT}

{PRESENTATION_RULES}

{STRICT_METRIC_SELECTION_RULES}

{COLLECTIONS_SEMANTIC_MODEL}

Core Rules:
- Generate PostgreSQL queries only.
- Only SELECT statements are allowed.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
- Use only the tables and columns provided in the context.
- SQL should be production-safe and readable.
- Do not use markdown.
- Do not generate text JSON.
- Always use the provided tool to return structured output.

Default Filters:
- Always apply inter_company_status = 'F' unless user asks for intercompany.
- TDS is included by default. Only add tds_flag = 'F' when user asks for
  "net collections", "excluding TDS", or "collections excluding tax".

Currency Rules:
- Default reporting currency is INR unless user asks for USD.
- collection_amt is in transaction currency.
- Convert to INR using: collection_amt * inr_exchangerate
- Convert to USD using: collection_amt * usd_exchangerate
- Never use pre-computed collection_amt_usd or collection_amt_inr columns.

Ageing Bucket Rules:
- Valid buckets in order: 'Within CP', '1-15 days', '16-30 days', '31-45 days',
  '46-60 days', '61-90 days', '>90 days'.
- Never sort ageingbucket alphabetically.
- Always use CASE WHEN ORDER BY for ageing bucket reports.

Display Rules:
- Always include display metadata.
- display.title should be user-friendly.
- display.currency should match the selected reporting currency.
- display.columns should map SQL aliases to clean column names.
- display.formatting should define currency formatting for amount columns.
"""

    # Default: billing
    return f"""
You are a finance analytics assistant.

Use the following table/view context:

{BILLING_CONTEXT}

{PRESENTATION_RULES}

{STRICT_METRIC_SELECTION_RULES}

{BILLING_SEMANTIC_MODEL}

Core Rules:
- Generate PostgreSQL queries only.
- Only SELECT statements are allowed.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
- Use only the tables and columns provided in the context.
- SQL should be production-safe and readable.
- Do not use markdown.
- Do not generate text JSON.
- Always use the provided tool to return structured output.

Currency Rules:
- Follow the default currency defined in the relevant context.
- For billing, default currency is USD unless the user explicitly asks for INR.
- Billing amount/fee/tax columns are in transaction currency.
- Convert using usd_exchangerate or inr_exchangerate inside SQL.
- Do not use billed_amt_usd, billed_amt_inr, billed_tax_amt_usd, or billed_tax_amt_inr.

Display Rules:
- Always include display metadata.
- display.title should be user-friendly.
- display.currency should match the selected reporting currency.
- display.columns should map SQL aliases to clean column names.
- display.formatting should define currency formatting for amount columns.
"""


# ─────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────

def validate_sql(sql: str) -> str:
    cleaned = sql.strip().lower()

    blocked_words = [
        "insert", "update", "delete", "drop",
        "alter", "truncate", "create"
    ]

    if not cleaned.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed.")

    if any(word in cleaned for word in blocked_words):
        raise HTTPException(status_code=400, detail="Unsafe SQL detected.")

    return sql


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "FastAPI is running",
        "api_key_loaded": api_key is not None,
        "database_loaded": database_url is not None
    }


@app.post("/chat")
def chat(request: ChatRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not loaded")

    if not engine:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not loaded")

    domain = classify_domain(request.message)
    system_prompt = build_system_prompt(domain)

    try:
        claude_response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": request.message}
            ],
            tools=TOOLS,
            tool_choice={
                "type": "tool",
                "name": "generate_sql_response"
            }
        )

        parsed = None

        for block in claude_response.content:
            if block.type == "tool_use":
                parsed = block.input
                break

        if parsed is None:
            raise HTTPException(
                status_code=500,
                detail="Claude did not return structured tool output"
            )

        sql = validate_sql(parsed["sql"])

        df = pd.read_sql_query(text(sql), engine)

        return {
            "metadata": parsed,
            "data": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "domain": domain,
            "usage": {
                "input_tokens": claude_response.usage.input_tokens,
                "output_tokens": claude_response.usage.output_tokens
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))