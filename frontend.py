import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Finance AI Chatbot",
    layout="wide"
)

st.title("Finance AI Chatbot")

BACKEND_URL = "http://127.0.0.1:8000/chat"


def get_currency_symbol(currency):
    currency = (currency or "").upper()
    if currency == "USD":
        return "$"
    elif currency == "INR":
        return "₹"
    elif currency == "EUR":
        return "€"
    return ""


def format_currency_value(x, currency, decimals=2):
    """
    Formats a numeric value into abbreviated currency:
      INR → ₹1.23 Cr   (divided by 1 Crore = 10,000,000)
      USD → $1.23 Mn   (divided by 1 Million = 1,000,000)
    Returns empty string for null/non-numeric values.
    """
    if not isinstance(x, (int, float)) or not pd.notnull(x):
        return ""
    symbol   = get_currency_symbol(currency)
    currency = (currency or "").upper()
    if currency == "INR":
        return f"{symbol}{x / 10_000_000:,.{decimals}f} Cr"
    else:
        return f"{symbol}{x / 1_000_000:,.{decimals}f} Mn"


QUARTER_SORT_KEYWORDS = ["quarter", "fy", "month", "year", "date", "period"]

def strip_currency_suffix(name):
    """Remove redundant currency labels from column headers."""
    for suffix in [" (USD)", " (INR)", " (usd)", " (inr)", " (Usd)", " (Inr)"]:
        name = name.replace(suffix, "")
    return name.strip()

def is_time_column(col):
    """Returns True if column looks like a time/period dimension."""
    col_lower = col.lower()
    return any(kw in col_lower for kw in QUARTER_SORT_KEYWORDS)

def is_metric_column(col):
    col = col.lower()
    return any(word in col for word in [
        "amount", "revenue", "billing", "billed", "tax", "fee", "total",
        "collection", "receipt"
    ])


def reorder_columns(df):
    cols = df.columns.tolist()

    row_pct_cols = [c for c in cols if c == "Row %"]

    id_cols = [
        c for c in cols
        if "id" in c.lower()
        and c not in row_pct_cols
    ]

    name_cols = [
        c for c in cols
        if "name" in c.lower()
        and c not in id_cols
        and c not in row_pct_cols
    ]

    total_cols = [
        c for c in cols
        if c == "Total"
    ]

    metric_cols = [
        c for c in cols
        if is_metric_column(c)
        and c not in id_cols
        and c not in name_cols
        and c not in total_cols
        and c not in row_pct_cols
    ]

    used = id_cols + name_cols + metric_cols + total_cols + row_pct_cols

    other_cols = [
        c for c in cols
        if c not in used
    ]

    # Place Row % immediately after metric cols so it reads as
    # "amount | percentage" rather than being stranded at the far right.
    ordered_cols = (
        id_cols
        + name_cols
        + other_cols
        + metric_cols
        + row_pct_cols
        + total_cols
    )

    return df[ordered_cols]


def apply_display_formatting(df, metadata):
    display = metadata.get("display", {})
    column_map = display.get("columns", {})
    formatting = display.get("formatting", {})

    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    metric_candidates = [
        col for col in numeric_cols
        if is_metric_column(col)
    ]

    if metric_candidates:
        value_col = metric_candidates[-1]
        total_value = df[value_col].sum()

        df["Row %"] = df[value_col].apply(
            lambda x: x / total_value if total_value else 0
        )

        formatting["Row %"] = {
            "type": "percentage",
            "decimals": 1
        }

        # Sort: chronological ASC for time dimensions, value DESC for everything else
        dim_cols = [c for c in df.columns if not is_metric_column(c) and c != "Row %"]
        if dim_cols and is_time_column(dim_cols[0]):
            df = df.sort_values(by=dim_cols[0], ascending=True).reset_index(drop=True)
        else:
            df = df.sort_values(by=value_col, ascending=False).reset_index(drop=True)

        # Grand Total row — numeric cols summed, others left blank
        grand_row = {}
        for col in df.columns:
            if col == "Row %":
                grand_row[col] = 1.0
            elif pd.api.types.is_numeric_dtype(df[col]):
                grand_row[col] = df[col].sum()
            else:
                grand_row[col] = "Grand Total" if col == df.columns[0] else ""
        df.loc[len(df)] = grand_row

    for original_col, rule in formatting.items():
        if original_col in df.columns:
            if rule.get("type") == "currency":
                currency = rule.get("currency", display.get("currency", ""))
                df[original_col] = df[original_col].apply(
                    lambda x: format_currency_value(x, currency)
                )

            elif rule.get("type") == "percentage":
                decimals = rule.get("decimals", 1)

                df[original_col] = df[original_col].apply(
                    lambda x: f"{x:.{decimals}%}" if pd.notnull(x) else ""
                )

    clean_map = {k: strip_currency_suffix(v) for k, v in column_map.items()}
    df = df.rename(columns=clean_map)
    df = reorder_columns(df)

    return df


def add_pivot_totals_and_sort(pivot_df, row_cols):
    numeric_cols = pivot_df.select_dtypes(include="number").columns.tolist()

    pivot_df["Total"] = pivot_df[numeric_cols].sum(axis=1)

    grand_total_value = pivot_df["Total"].sum()

    pivot_df["Row %"] = pivot_df["Total"].apply(
        lambda x: x / grand_total_value if grand_total_value else 0
    )

    pivot_df = pivot_df.sort_values(
        by="Total",
        ascending=False
    )

    grand_total = {}

    for col in pivot_df.columns:
        if col in row_cols:
            grand_total[col] = "Grand Total"
        elif col == "Row %":
            grand_total[col] = 1
        elif pd.api.types.is_numeric_dtype(pivot_df[col]):
            grand_total[col] = pivot_df[col].sum()
        else:
            grand_total[col] = ""

    pivot_df.loc[len(pivot_df)] = grand_total

    return pivot_df


def format_pivot_values(pivot_df, metadata, row_cols):
    display  = metadata.get("display", {})
    currency = display.get("currency", "USD")

    for col in pivot_df.columns:
        if col == "Row %":
            pivot_df[col] = pivot_df[col].apply(
                lambda x: f"{x:.1%}" if pd.notnull(x) else ""
            )
        elif col not in row_cols:
            pivot_df[col] = pivot_df[col].apply(
                lambda x: format_currency_value(x, currency)
            )

    # Explicit column order for dimension pivots:
    # row dimension(s) | Row % | value columns | Total
    special = set(row_cols + ["Row %", "Total"])
    value_cols = [c for c in pivot_df.columns if c not in special]
    row_pct   = ["Row %"] if "Row %" in pivot_df.columns else []
    total_col = ["Total"] if "Total" in pivot_df.columns else []
    ordered   = row_cols + row_pct + value_cols + total_col
    pivot_df  = pivot_df[[c for c in ordered if c in pivot_df.columns]]

    # Sort rows: chronological for time dimensions, by Total DESC otherwise
    # Exclude Grand Total row from sort, re-append after
    grand_mask  = pivot_df[row_cols[0]].astype(str).str.contains("Grand Total", case=False, na=False) if row_cols else pd.Series([False] * len(pivot_df))
    body        = pivot_df[~grand_mask]
    grand_rows  = pivot_df[grand_mask]
    if row_cols and is_time_column(row_cols[0]):
        body = body.sort_values(by=row_cols[0], ascending=True)
    pivot_df = pd.concat([body, grand_rows], ignore_index=True)

    return pivot_df



def apply_metric_pivot_formatting(df, metadata):
    """
    Two display modes depending on whether a row dimension exists:

    A) No dimension (overall split, e.g. "invoice type split"):
       Transposes to: Invoice Type | Amount | Percentage
       Sorted by Amount DESC with a Grand Total row.

    B) With dimension (e.g. "region and invoice type split"):
       dimension(s) | Row % | metric cols | Total
       Sorted by Total DESC with a Grand Total row.
    """
    display         = metadata.get("display", {})
    column_map      = display.get("columns", {})
    currency        = display.get("currency", "USD")
    symbol          = get_currency_symbol(currency)
    row_dims        = metadata.get("rows", [])
    metric_cols_raw = metadata.get("metric_columns", [])

    # Rename SQL aliases to display names (strip currency suffix from headers)
    column_map = {k: strip_currency_suffix(v) for k, v in column_map.items()}
    df = df.rename(columns=column_map)
    renamed_rows    = [column_map.get(r, r) for r in row_dims]
    renamed_metrics = [column_map.get(m, m) for m in metric_cols_raw]
    existing_metrics = [c for c in renamed_metrics if c in df.columns]

    # ── MODE A: no grouping dimension → transpose ──────────────────────────
    if not renamed_rows or all(r not in df.columns for r in renamed_rows):
        # Aggregate each metric across all rows (handles the single-row case too)
        totals = {col: df[col].sum() for col in existing_metrics if col in df.columns}
        grand_total = sum(totals.values())

        rows = []
        for metric_name, amount in totals.items():
            # Strip redundant currency suffix — symbol already shows currency
            clean_name = metric_name.replace(" (USD)", "").replace(" (INR)", "").replace(" (usd)", "").replace(" (inr)", "")
            rows.append({
                "Invoice Type": clean_name,
                "Amount":       amount,
                "Percentage":   amount / grand_total if grand_total else 0,
            })

        result_df = pd.DataFrame(rows)

        # Sort by Amount DESC
        result_df = result_df.sort_values(by="Amount", ascending=False).reset_index(drop=True)

        # Append Grand Total row
        result_df.loc[len(result_df)] = {
            "Invoice Type": "Grand Total",
            "Amount":       grand_total,
            "Percentage":   1.0,
        }

        # Format
        result_df["Amount"] = result_df["Amount"].apply(
            lambda x: format_currency_value(x, currency)
        )
        result_df["Percentage"] = result_df["Percentage"].apply(
            lambda x: f"{x:.1%}"
            if isinstance(x, (int, float)) and pd.notnull(x) else ""
        )

        return result_df

    # ── MODE B: has grouping dimension → wide table ────────────────────────
    # Compute Total and Row % as numeric before formatting
    df["Total"]  = df[existing_metrics].sum(axis=1)
    grand_total  = df["Total"].sum()
    df["Row %"]  = df["Total"].apply(
        lambda x: x / grand_total if grand_total else 0
    )

    # Sort: chronological for time dimensions, by Total DESC otherwise
    if renamed_rows and is_time_column(renamed_rows[0]):
        df = df.sort_values(by=renamed_rows[0], ascending=True).reset_index(drop=True)
    else:
        df = df.sort_values(by="Total", ascending=False).reset_index(drop=True)

    # Grand Total row
    grand_row = {}
    for col in df.columns:
        if col in renamed_rows:
            grand_row[col] = "Grand Total"
        elif col == "Row %":
            grand_row[col] = 1.0
        elif pd.api.types.is_numeric_dtype(df[col]):
            grand_row[col] = df[col].sum()
        else:
            grand_row[col] = ""
    df.loc[len(df)] = grand_row

    # Format Row %
    df["Row %"] = df["Row %"].apply(
        lambda x: f"{x:.1%}"
        if isinstance(x, (int, float)) and pd.notnull(x) else ""
    )

    # Format metric columns and Total
    for col in existing_metrics + ["Total"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: format_currency_value(x, currency)
            )

    # Column order: dimension(s) | Row % | metrics | Total
    ordered   = renamed_rows + ["Row %"] + existing_metrics + ["Total"]
    remaining = [c for c in df.columns if c not in ordered]
    df = df[ordered + remaining]

    # Combined header: "Region ↓  |  Revenue Type →"
    # Derive column label from metric column names
    if renamed_rows:
        sample_metrics = [m.lower() for m in existing_metrics]
        if any(w in " ".join(sample_metrics) for w in ["revenue", "subscription", "implementation", "collection", "amount"]):
            col_label = "Revenue Type →" if any("revenue" in m or "subscription" in m for m in sample_metrics) else "Type →"
        else:
            col_label = "Type →"
        row_label      = renamed_rows[0]
        combined       = f"{row_label} ↓  |  {col_label}"
        df             = df.rename(columns={row_label: combined})

    return df


user_input = st.chat_input("Ask something")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    # ── Backend call ────────────────────────────────────────────────────────
    try:
        response = requests.post(
            BACKEND_URL,
            json={"message": user_input},
            timeout=300
        )
    except requests.exceptions.ReadTimeout:
        st.error("Request timed out after 300 s. The query or Claude response took too long.")
        st.stop()
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to backend at " + BACKEND_URL + ". Is the FastAPI server running?")
        st.stop()

    if response.status_code != 200:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        with st.chat_message("assistant"):
            if response.status_code == 400 and "GROUP BY" in detail:
                # Invalid dimension — extract the bad dimension name cleanly
                import re
                dim_match = re.search(r"dimensions [(](.+?)[)]", detail)
                bad_dims   = dim_match.group(1).replace("'", "").strip() if dim_match else "unknown"
                st.warning(
                    f"I couldn't find **{bad_dims}** as a valid grouping dimension. "
                    f"Try rephrasing using one of: **region, customer, quarter, "
                    f"currency, subsidiary, billing entity**."
                )
            else:
                st.error("Something went wrong. Please try rephrasing your question.")
                with st.expander("Details"):
                    st.code(detail)
        st.stop()

    result   = response.json()
    metadata = result["metadata"]
    data     = result["data"]
    df       = pd.DataFrame(data)

    # ── Render ──────────────────────────────────────────────────────────────
    with st.chat_message("assistant"):
        display     = metadata.get("display", {})
        title       = display.get("title")
        explanation = metadata.get("explanation", "")

        if title:
            st.subheader(title)
        if explanation:
            st.write(explanation)

        with st.expander("Generated SQL"):
            st.code(metadata.get("sql", ""), language="sql")

        visualization = metadata.get("visualization")

        try:
            if visualization == "pivot_table" and metadata.get("pivot_type") == "metric":
                df = apply_metric_pivot_formatting(df, metadata)
                st.dataframe(df, width='stretch', hide_index=True)

            elif visualization == "pivot_table" and metadata.get("pivot_type") == "dimension":
                rows        = metadata["rows"]
                columns     = metadata["columns"]
                values      = metadata["values"][0]
                aggregation = metadata.get("aggregation", "sum")

                pivot_df = df.pivot_table(
                    index=rows,
                    columns=columns,
                    values=values,
                    aggfunc=aggregation,
                    fill_value=0
                ).reset_index()

                pivot_df.columns  = [str(col) for col in pivot_df.columns]
                column_map        = {k: strip_currency_suffix(v) for k, v in display.get("columns", {}).items()}
                pivot_df          = pivot_df.rename(columns=column_map)
                renamed_rows      = [column_map.get(row, row) for row in rows]

                # Combine row + column dimension names in the top-left header
                # e.g. "Receiving Entity ↓  |  Paying Entity →"
                row_label    = column_map.get(rows[0], rows[0]) if rows else ""
                col_label    = column_map.get(columns[0], columns[0]) if columns else ""
                if row_label and col_label:
                    combined_header = f"{row_label} ↓  |  {col_label} →"
                    pivot_df        = pivot_df.rename(columns={row_label: combined_header})
                    renamed_rows    = [combined_header if r == row_label else r for r in renamed_rows]
                pivot_df          = add_pivot_totals_and_sort(pivot_df, renamed_rows)
                pivot_df          = format_pivot_values(pivot_df, metadata, renamed_rows)

                st.dataframe(pivot_df, width='stretch', hide_index=True)

            else:
                df = apply_display_formatting(df, metadata)
                st.dataframe(df, width='stretch', hide_index=True)

        except Exception as render_err:
            st.error(f"Rendering error: {render_err}")
            with st.expander("Debug — raw metadata from Claude"):
                st.json(metadata)
            with st.expander("Debug — raw data columns"):
                st.write(list(df.columns))

        with st.expander("Token usage"):
            st.json(result.get("usage", {}))