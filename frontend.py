import streamlit as st
import requests
import pandas as pd

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


def is_metric_column(col):
    col = col.lower()
    return any(word in col for word in [
        "amount", "revenue", "billing", "billed", "tax", "fee", "total"
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

    ordered_cols = (
        id_cols
        + name_cols
        + other_cols
        + metric_cols
        + total_cols
        + row_pct_cols
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

    for original_col, rule in formatting.items():
        if original_col in df.columns:
            if rule.get("type") == "currency":
                currency = rule.get("currency", display.get("currency", ""))
                decimals = rule.get("decimals", 0)
                symbol = get_currency_symbol(currency)

                df[original_col] = df[original_col].apply(
                    lambda x: f"{symbol}{x:,.{decimals}f}" if pd.notnull(x) else ""
                )

            elif rule.get("type") == "percentage":
                decimals = rule.get("decimals", 1)

                df[original_col] = df[original_col].apply(
                    lambda x: f"{x:.{decimals}%}" if pd.notnull(x) else ""
                )

    df = df.rename(columns=column_map)
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
    display = metadata.get("display", {})
    currency = display.get("currency", "USD")
    symbol = get_currency_symbol(currency)

    for col in pivot_df.columns:
        if col == "Row %":
            pivot_df[col] = pivot_df[col].apply(
                lambda x: f"{x:.1%}" if pd.notnull(x) else ""
            )

        elif col not in row_cols:
            pivot_df[col] = pivot_df[col].apply(
                lambda x: f"{symbol}{x:,.0f}" if pd.notnull(x) else ""
            )

    pivot_df = reorder_columns(pivot_df)

    return pivot_df


user_input = st.chat_input("Ask something")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    response = requests.post(
        BACKEND_URL,
        json={"message": user_input},
        timeout=120
    )

    if response.status_code != 200:
        st.error("Backend error")
        st.write(response.text)

    else:
        result = response.json()

        metadata = result["metadata"]
        data = result["data"]

        df = pd.DataFrame(data)

        with st.chat_message("assistant"):
            display = metadata.get("display", {})
            title = display.get("title")
            explanation = metadata.get("explanation", "")

            if title:
                st.subheader(title)

            if explanation:
                st.write(explanation)

            with st.expander("Generated SQL"):
                st.code(metadata.get("sql", ""), language="sql")

            visualization = metadata.get("visualization")

            if visualization == "pivot_table" and metadata.get("pivot_type") == "dimension":
                rows = metadata["rows"]
                columns = metadata["columns"]
                values = metadata["values"][0]
                aggregation = metadata.get("aggregation", "sum")

                pivot_df = df.pivot_table(
                    index=rows,
                    columns=columns,
                    values=values,
                    aggfunc=aggregation,
                    fill_value=0
                ).reset_index()

                pivot_df.columns = [str(col) for col in pivot_df.columns]

                column_map = display.get("columns", {})
                pivot_df = pivot_df.rename(columns=column_map)

                renamed_rows = [column_map.get(row, row) for row in rows]

                pivot_df = add_pivot_totals_and_sort(
                    pivot_df,
                    renamed_rows
                )

                pivot_df = format_pivot_values(
                    pivot_df,
                    metadata,
                    renamed_rows
                )

                st.dataframe(
                    pivot_df,
                    use_container_width=True,
                    hide_index=True
                )

            else:
                df = apply_display_formatting(df, metadata)

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

            with st.expander("Token usage"):
                st.json(result.get("usage", {}))