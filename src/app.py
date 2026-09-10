import math
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_option_menu import option_menu

try:
    from src.pdf_parser import parse_statement
    from src.repository import DatabaseRepository
except ImportError:
    from pdf_parser import parse_statement
    from repository import DatabaseRepository

DB_PATH = "db/personal-expense-tracker.db"


@st.dialog("Confirm new category", width="small")
def confirm_add_category_dialog(category_name: str) -> None:
    st.write(f"Please confirm the addition of the new '{category_name}' category.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, key="dialog_cancel_add_cat"):
            st.rerun()
    with col2:
        if st.button(
            "Add", type="primary", use_container_width=True, key="dialog_confirm_add_cat"
        ):
            repo = DatabaseRepository(DB_PATH)
            repo.add_category(category_name)
            st.rerun()


@st.dialog("Confirm mapping", width="small")
def confirm_merchant_mapping_dialog(
    selected_merchant: str,
    current_cat_name: str,
    selected_new_cat: str,
    target_id: Any,
    new_cat_id: int,
) -> None:
    st.write(
        f"Please confirm that all transactions for '{selected_merchant}' are to be updated from '{current_cat_name}' to '{selected_new_cat}'?"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, key="dialog_cancel_global"):
            st.rerun()
    with col2:
        if st.button(
            "Save", type="primary", use_container_width=True, key="dialog_save_global"
        ):
            repo = DatabaseRepository(DB_PATH)
            repo.update_merchant_category(target_id, new_cat_id)
            st.rerun()


@st.dialog("Confirm transaction category update", width="small")
def confirm_tx_category_dialog(
    current_cat_name: str,
    selected_new_cat: str,
    selected_tx_id: int,
    new_cat_id: int,
) -> None:
    st.write(
        f"Please confirm that this transaction's category is to be updated from '{current_cat_name}' to '{selected_new_cat}'?"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, key="dialog_cancel_tx"):
            st.rerun()
    with col2:
        if st.button(
            "Update", type="primary", use_container_width=True, key="dialog_update_tx"
        ):
            repo = DatabaseRepository(DB_PATH)
            repo.update_transaction_category(selected_tx_id, new_cat_id)
            st.rerun()


@st.dialog("Confirm transaction update", width="small")
def confirm_update_transaction_dialog(
    selected_tx_id: int,
    new_cat_id: Optional[int],
    new_cat_name: Optional[str],
    new_aud: Optional[float],
    new_fx: Optional[float],
) -> None:
    st.write("Please confirm that you wish to update this transaction with the following details:")
    if new_cat_name:
        st.write(f"- **Category:** {new_cat_name}")
    if new_aud is not None:
        st.write(f"- **Amount ($AUD):** ${new_aud:,.2f}")
    if new_fx is not None:
        st.write(f"- **FX rate:** {new_fx:.5f}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, key="dialog_cancel_search_update"):
            st.rerun()
    with col2:
        if st.button(
            "Update", type="primary", use_container_width=True, key="dialog_confirm_search_update"
        ):
            repo = DatabaseRepository(DB_PATH)
            repo.update_transaction_details(
                transaction_id=selected_tx_id,
                category_id=new_cat_id,
                txn_amount=new_aud,
                fx_rate=new_fx,
            )
            st.rerun()


class PersonalExpenseTracker:
    def __init__(self) -> None:
        self.repo = DatabaseRepository(DB_PATH)

    @staticmethod
    def inject_css(page_title: str) -> None:
        css = f"""
        <style>
        /* 1. Sidebar Header Alignment */
        [data-testid="stSidebarHeader"] {{
            display: none !important;
        }}
        section[data-testid="stSidebar"] > div:first-child {{
            padding: 0.5rem !important;
        }}
        [data-testid="stSidebarContent"] {{
            padding-top: 0rem !important;
        }}

        /* 2. Solid Top Sticky Header & Persistent Title Injection */
        [data-testid="stHeader"] {{
            background-color: #0e1117 !important;
            z-index: 999 !important;
        }}

        .sticky-page-title {{
            position: fixed;
            top: 0.2rem;
            left: 14.5rem;
            z-index: 1000 !important;
            pointer-events: none;
            font-size: 2rem;
            font-weight: 600;
            color: #FFFFFF;
        }}

        /* 3. Main Content Padding */
        .block-container {{
            padding-top: 4rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }}

        /* 4. Equal Card Dimensions & Border Wrapper Lock (215px min-height) */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            min-height: 215px !important;
            flex: 1 !important;
        }}

        .metric-card-container {{
            height: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            padding: 0.25rem 0 !important;
        }}

        /* 5. Content Typography & Card Sizing */
        .metric-large {{
            font-size: 8.8rem !important;
            font-weight: bold !important;
            line-height: 1.1 !important;
            color: #FFFFFF !important;
            margin-top: 0.5rem !important;
        }}

        .period-label {{
            font-size: 0.85rem !important;
            color: #808495 !important;
            margin-top: 0.25rem !important;
        }}

        .period-val {{
            font-size: 2rem !important;
            font-weight: 600 !important;
            color: #FFFFFF !important;
            margin-bottom: 0.25rem !important;
        }}
        </style>
        <div class="sticky-page-title">{page_title}</div>
        """
        st.markdown(css, unsafe_allow_html=True)

    @staticmethod
    def get_date_range(df: pd.DataFrame) -> Tuple[str, str]:
        if df.empty or "trans_date" not in df.columns:
            return "N/A", "N/A"

        try:
            parsed_dates = pd.to_datetime(
                df["trans_date"].dropna(), errors="coerce"
            ).dropna()
            if parsed_dates.empty:
                return "N/A", "N/A"
            min_date = parsed_dates.min().strftime("%B %Y")
            max_date = parsed_dates.max().strftime("%B %Y")
            return min_date, max_date
        except Exception:
            return "N/A", "N/A"

    @staticmethod
    def render_sidebar() -> str:
        with st.sidebar:
            selected = option_menu(
                menu_title=None,
                options=["Dashboard", "Upload", "Categorise", "Charts", "Search"],
                icons=["house", "cloud-upload", "tag", "bar-chart", "search"],
                default_index=4,
                styles={
                    "container": {
                        "padding": "0!important",
                        "background-color": "transparent",
                    },
                    "icon": {"color": "#FFFFFF", "font-size": "1rem"},
                    "nav-link": {
                        "color": "#FFFFFF",
                        "font-size": "0.95rem",
                        "text-align": "left",
                        "margin": "0px",
                        "--hover-color": "#262730",
                    },
                    "nav-link-selected": {"background-color": "#31333F"},
                },
            )
        return str(selected)

    def render_upload_page(self) -> None:
        st.markdown(
            "Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning."
        )

        df = self.repo.get_transactions_dataframe()
        total_txns = len(df)
        period_from, period_to = self.get_date_range(df)

        col1, col2, col3 = st.columns(3)

        with col1:
            with st.container(border=True, height="stretch"):
                st.subheader("Upload a PDF statement")
                uploaded_file = st.file_uploader(
                    "Upload PDF", type=["pdf"], label_visibility="collapsed"
                )
                process_btn = st.button(
                    "Process Statement", type="primary", use_container_width=True
                )

        with col2:
            with st.container(border=True, height="stretch"):
                st.subheader("Total transactions uploaded")
                st.markdown(
                    f"""<div class="metric-card-container">
                        <div class="metric-large">{total_txns}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        with col3:
            with st.container(border=True, height="stretch"):
                st.subheader("Statement period uploaded")
                st.markdown(
                    f"""<div class="metric-card-container">
                        <div class="period-label">From:</div>
                        <div class="period-val">{period_from}</div>
                        <div class="period-label">To:</div>
                        <div class="period-val">{period_to}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        if process_btn:
            if uploaded_file is not None:
                with st.spinner("Processing statement..."):
                    tmp_path: Optional[str] = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".pdf"
                        ) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        result = parse_statement(
                            tmp_path, db_path=DB_PATH, original_filename=uploaded_file.name
                        )
                        if isinstance(result, pd.DataFrame) and not result.empty:
                            st.session_state["upload_success"] = True
                            st.rerun()
                        elif isinstance(result, bool) and result:
                            st.session_state["upload_success"] = True
                            st.rerun()
                        else:
                            st.error(
                                "Error processing statement. Invalid or duplicate format."
                            )
                    except Exception as e:
                        st.error(f"Error processing statement: {e}")
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)
            else:
                st.warning("Please select a PDF file to process.")

        if st.session_state.pop("upload_success", False):
            st.success("Statement processed successfully!")

        st.write("")
        st.subheader("Transactions uploaded")
        st.markdown(
            "This is a list of the raw transactions as they've been imported from the uploaded PDF statement."
        )

        col_mapping = {
            "trans_date": "Transaction Date",
            "merchant": "Merchant",
            "category_name": "Category",
            "txn_amount": "Amount",
            "purchase_currency": "Currency",
            "hkd_amount": "HKD Amount",
            "fx_rate": "FX Rate",
        }

        display_cols = [c for c in col_mapping.keys() if c in df.columns]
        display_df = (
            df[display_cols].rename(columns=col_mapping)
            if not df.empty
            else pd.DataFrame(columns=list(col_mapping.values()))
        )

        total_rows = len(display_df)
        page_size = 10
        total_pages = max(1, math.ceil(total_rows / page_size))

        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 1

        if st.session_state["current_page"] > total_pages:
            st.session_state["current_page"] = total_pages
        if st.session_state["current_page"] < 1:
            st.session_state["current_page"] = 1

        current_page = st.session_state["current_page"]
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size

        page_df = display_df.iloc[start_idx:end_idx]
        st.dataframe(page_df, use_container_width=True, hide_index=True)

        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 2, 1])

        with ctrl_col1:
            if st.button(
                "Previous Page",
                disabled=(current_page <= 1),
                key="tx_prev_page",
                use_container_width=True,
            ):
                st.session_state["current_page"] -= 1
                st.rerun()

        with ctrl_col2:
            st.markdown(
                f"<div style='text-align: center; padding-top: 0.5rem; color: #FAFAFA;'>Page {current_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )

        with ctrl_col3:
            if st.button(
                "Next Page",
                disabled=(current_page >= total_pages),
                key="tx_next_page",
                use_container_width=True,
            ):
                st.session_state["current_page"] += 1
                st.rerun()

    def render_categorise_page(self) -> None:
        uncat_df = self.repo.get_uncategorised_merchants()
        categories_df = self.repo.get_categories()
        merchants_df = self.repo.get_merchants()

        category_list: List[str] = []
        cat_name_to_id: Dict[str, int] = {}
        if not categories_df.empty and "category_name" in categories_df.columns:
            category_list = categories_df["category_name"].dropna().tolist()
            cat_name_to_id = dict(
                zip(categories_df["category_name"], categories_df["id"])
            )

        merchant_list: List[str] = []
        merchant_cat_map: Dict[str, str] = {}
        merchant_id_map: Dict[str, Any] = {}
        if not merchants_df.empty and "merchant_name" in merchants_df.columns:
            merchant_list = merchants_df["merchant_name"].dropna().tolist()
            merchant_cat_map = dict(
                zip(
                    merchants_df["merchant_name"],
                    merchants_df["category_name"].fillna(""),
                )
            )
            merchant_id_map = dict(
                zip(merchants_df["merchant_name"], merchants_df["merchant_id"])
            )

        row1_col1, row1_col2 = st.columns(2)

        with row1_col1:
            with st.container(border=True, height="stretch"):
                st.subheader("Add new category")
                st.markdown(
                    "Adding a new category for merchants that do not fit pre-defined "
                    "categories enables more accurate financial statistics."
                )

                new_cat_input = st.text_input(
                    "Category name", max_chars=50, key="new_category_name_input"
                )

                add_cat_btn = st.button(
                    "Add category", type="primary", key="add_new_category_btn"
                )

                if add_cat_btn:
                    trimmed_cat = new_cat_input.strip()
                    if not trimmed_cat:
                        st.error("Category name cannot be empty.")
                    elif not re.match(r"^[A-Za-z\s&\-\/]+$", trimmed_cat):
                        st.error(
                            "Category name contains invalid characters. Only letters, spaces, ampersands (&), hyphens (-), and slashes (/) are allowed."
                        )
                    elif any(c.lower() == trimmed_cat.lower() for c in category_list):
                        st.error(f"Category '{trimmed_cat}' already exists.")
                    else:
                        confirm_add_category_dialog(trimmed_cat)

        with row1_col2:
            with st.container(border=True, height="stretch"):
                st.subheader("Merchant mapping")
                st.markdown(
                    "Select a merchant and a category to update its mapping, re-categorising ALL transactions made at the selected merchant."
                )

                selected_merchant = st.selectbox(
                    "Merchant",
                    options=["Select a merchant"] + merchant_list,
                    key="global_merchant_select",
                )

                current_merchant_cat = (
                    merchant_cat_map.get(selected_merchant, "")
                    if selected_merchant != "Select a merchant"
                    else ""
                )

                subcol1, subcol2 = st.columns(2)

                with subcol1:
                    st.text_input(
                        "Current category",
                        value=current_merchant_cat,
                        disabled=True,
                        key=f"merchant_current_cat_display_{selected_merchant}",
                    )

                with subcol2:
                    selected_category = st.selectbox(
                        "New category",
                        options=["Select a category"] + category_list,
                        key="global_category_select",
                    )

                save_mapping_btn = st.button(
                    "Save mapping", type="primary", key="save_global_mapping"
                )

                if save_mapping_btn:
                    if (
                        selected_merchant == "Select a merchant"
                        or selected_category == "Select a category"
                    ):
                        st.error(
                            "Please select both a merchant and a new category before saving."
                        )
                    elif selected_category == current_merchant_cat:
                        st.error(
                            "'Current category' and 'New category' must not be the same."
                        )
                    else:
                        target_id = merchant_id_map.get(
                            selected_merchant, selected_merchant
                        )
                        new_cat_id = cat_name_to_id.get(selected_category, 1)
                        confirm_merchant_mapping_dialog(
                            selected_merchant,
                            current_merchant_cat,
                            selected_category,
                            target_id,
                            new_cat_id,
                        )

        st.write("")

        st.subheader("Uncategorised merchants")
        st.markdown(
            "List of merchants currently assigned to 'Uncategorised' requiring mapping."
        )

        display_uncat_df = pd.DataFrame(columns=["Merchant", "Instances"])
        if not uncat_df.empty:
            m_col = (
                "merchant_name" if "merchant_name" in uncat_df.columns else "merchant"
            )
            if m_col in uncat_df.columns and "transaction_count" in uncat_df.columns:
                display_uncat_df = uncat_df[[m_col, "transaction_count"]].copy()
                display_uncat_df = display_uncat_df.rename(
                    columns={m_col: "Merchant", "transaction_count": "Instances"}
                )

        page_size = 5
        total_rows = len(display_uncat_df)
        total_pages = max(1, math.ceil(total_rows / page_size))

        if "uncat_current_page" not in st.session_state:
            st.session_state["uncat_current_page"] = 1

        if st.session_state["uncat_current_page"] > total_pages:
            st.session_state["uncat_current_page"] = total_pages
        if st.session_state["uncat_current_page"] < 1:
            st.session_state["uncat_current_page"] = 1

        current_page = st.session_state["uncat_current_page"]
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size

        page_df = display_uncat_df.iloc[start_idx:end_idx]
        st.dataframe(page_df, use_container_width=True, hide_index=True)

        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 2, 1])

        with ctrl_col1:
            if st.button(
                "Previous Page",
                disabled=(current_page <= 1),
                key="uncat_prev_page",
                use_container_width=True,
            ):
                st.session_state["uncat_current_page"] -= 1
                st.rerun()

        with ctrl_col2:
            st.markdown(
                f"<div style='text-align: center; padding-top: 0.5rem; color: #FAFAFA;'>Page {current_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )

        with ctrl_col3:
            if st.button(
                "Next Page",
                disabled=(current_page >= total_pages),
                key="uncat_next_page",
                use_container_width=True,
            ):
                st.session_state["uncat_current_page"] += 1
                st.rerun()

    def render_charts_page(self) -> None:
        raw_df = self.repo.get_transactions_dataframe()
        categories_df = self.repo.get_categories()

        category_list: List[str] = []
        if not categories_df.empty and "category_name" in categories_df.columns:
            category_list = categories_df["category_name"].dropna().tolist()

        df = raw_df.copy() if not raw_df.empty else pd.DataFrame()
        if not df.empty and "trans_date" in df.columns:
            df["trans_date_dt"] = pd.to_datetime(df["trans_date"], errors="coerce")
        else:
            df["trans_date_dt"] = pd.Series(dtype="datetime64[ns]")

        if "txn_amount" in df.columns:
            df["txn_amount"] = pd.to_numeric(df["txn_amount"], errors="coerce").fillna(0.0)
        else:
            df["txn_amount"] = 0.0

        if "category_name" not in df.columns:
            df["category_name"] = "Uncategorised"
        df["category_name"] = df["category_name"].fillna("Uncategorised")

        col1, col2 = st.columns([3, 2])

        with col2:
            with st.container(border=True, height="stretch"):
                st.subheader("Filters")
                date_preset = st.radio(
                    "Date Range",
                    options=[
                        "This Month",
                        "Last 3 Months",
                        "Last 6 Months",
                        "Year to Date",
                        "All Time",
                    ],
                    index=0,
                    horizontal=True,
                    key="charts_date_preset",
                )

                custom_date = st.date_input(
                    "Custom Date Range",
                    value=(),
                    key="charts_custom_date",
                )

                selected_categories = st.multiselect(
                    "Filter Categories",
                    options=category_list if category_list else df["category_name"].unique().tolist(),
                    default=category_list if category_list else df["category_name"].unique().tolist(),
                    key="charts_category_filter",
                )

                outlier_threshold = st.number_input(
                    "Highlight Outliers Above ($)",
                    value=1000,
                    step=100,
                    key="charts_outlier_threshold",
                )

        today = pd.Timestamp.today().normalize()
        start_date: Optional[pd.Timestamp] = None
        end_date: Optional[pd.Timestamp] = None

        if custom_date and isinstance(custom_date, (list, tuple)) and len(custom_date) == 2:
            start_date = pd.Timestamp(custom_date[0])
            end_date = pd.Timestamp(custom_date[1])
        else:
            if date_preset == "This Month":
                start_date = today.replace(day=1)
                end_date = today
            elif date_preset == "Last 3 Months":
                start_date = today - pd.DateOffset(months=3)
                end_date = today
            elif date_preset == "Last 6 Months":
                start_date = today - pd.DateOffset(months=6)
                end_date = today
            elif date_preset == "Year to Date":
                start_date = pd.Timestamp(year=today.year, month=1, day=1)
                end_date = today
            elif date_preset == "All Time":
                start_date = None
                end_date = None

        filtered_df = df.copy()
        if not filtered_df.empty:
            if start_date is not None:
                filtered_df = filtered_df[filtered_df["trans_date_dt"] >= start_date]
            if end_date is not None:
                filtered_df = filtered_df[filtered_df["trans_date_dt"] <= end_date]
            if selected_categories:
                filtered_df = filtered_df[filtered_df["category_name"].isin(selected_categories)]

        has_non_aud = False
        if not filtered_df.empty and "purchase_currency" in filtered_df.columns:
            non_aud_mask = filtered_df["purchase_currency"].astype(str).str.upper().ne("AUD")
            has_non_aud = bool(non_aud_mask.any())

        with col1:
            with st.container(border=True, height="stretch"):
                st.subheader("Expense category breakdown")
                if filtered_df.empty:
                    st.info("No transactions found for the selected filter criteria.")
                else:
                    cat_summary = (
                        filtered_df.groupby("category_name")["txn_amount"]
                        .sum()
                        .reset_index()
                    )
                    cat_summary.columns = ["Category", "Total Spend (AUD)"]
                    total_spend = cat_summary["Total Spend (AUD)"].sum()

                    fig = go.Figure(
                        data=[
                            go.Pie(
                                labels=cat_summary["Category"],
                                values=cat_summary["Total Spend (AUD)"],
                                hole=0.55,
                                textinfo="percent+label",
                                hoverinfo="label+value+percent",
                                hovertemplate="<b>%{label}</b><br>Total Spend: $%{value:,.2f}<br>Share: %{percent}<extra></extra>",
                                marker=dict(
                                    colors=px.colors.qualitative.Plotly
                                ),
                            )
                        ]
                    )

                    fig.update_layout(
                        annotations=[
                            dict(
                                text=f"<b>Total Spend</b><br>${total_spend:,.2f}",
                                x=0.5,
                                y=0.5,
                                font=dict(size=18, color="#FFFFFF"),
                                showarrow=False,
                            )
                        ],
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=-0.2,
                            xanchor="center",
                            x=0.5,
                            font=dict(color="#FFFFFF"),
                        ),
                        margin=dict(l=20, r=20, t=30, b=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#FFFFFF"),
                    )

                    st.plotly_chart(fig, use_container_width=True)

                if has_non_aud:
                    st.caption("ℹ️ Transactions in currencies other than AUD")

        st.write("")
        with st.container(border=True):
            st.subheader("Expense category statistics")
            st.markdown(
                "Monthly averages calculated across the selected date range for direct import into budget spreadsheets."
            )

            if filtered_df.empty:
                st.info("No transaction data available for statistics.")
            else:
                valid_dates = filtered_df["trans_date_dt"].dropna()
                if not valid_dates.empty:
                    min_date = valid_dates.min()
                    max_date = valid_dates.max()
                    days_diff = max(0, (max_date - min_date).days)
                    n_months = max(1.0, days_diff / 30.44)
                else:
                    n_months = 1.0

                total_all_spend = filtered_df["txn_amount"].sum()

                grouped = (
                    filtered_df.groupby("category_name")
                    .agg(
                        total_spend=("txn_amount", "sum"),
                        txn_count=("id" if "id" in filtered_df.columns else "txn_amount", "count"),
                        max_single_txn=("txn_amount", "max"),
                    )
                    .reset_index()
                )

                grouped = grouped.sort_values(by="total_spend", ascending=False)

                table_rows = []
                for _, row in grouped.iterrows():
                    cat_val = row["category_name"]
                    t_spend = float(row["total_spend"])
                    m_avg = t_spend / n_months
                    pct_share = (t_spend / total_all_spend * 100) if total_all_spend > 0 else 0.0
                    t_count = int(row["txn_count"])
                    m_single = float(row["max_single_txn"])

                    is_outlier = m_single > outlier_threshold
                    max_single_str = f"${m_single:,.2f}*" if is_outlier else f"${m_single:,.2f}"

                    table_rows.append(
                        {
                            "Category": cat_val,
                            "Total Spend (AUD)": f"${t_spend:,.2f}",
                            "Monthly Average (AUD)": f"${m_avg:,.2f}",
                            "% of Total": f"{pct_share:.1f}%",
                            "Txn Count": t_count,
                            "Max Single Txn (AUD)": max_single_str,
                        }
                    )

                stats_df = pd.DataFrame(table_rows)
                st.dataframe(stats_df, use_container_width=True, hide_index=True)

    def render_search_page(self) -> None:
        st.markdown(
            "Search historical transactions across merchant, amount, or date, and select any record from the results table to view its full details and perform category or FX rate overrides."
        )

        categories_df = self.repo.get_categories()
        category_list: List[str] = []
        cat_name_to_id: Dict[str, int] = {}
        if not categories_df.empty and "category_name" in categories_df.columns:
            category_list = categories_df["category_name"].dropna().tolist()
            cat_name_to_id = dict(
                zip(categories_df["category_name"], categories_df["id"])
            )

        # Row 1: Search Criteria Card
        with st.container(border=True):
            st.subheader("Search criteria")
            col_in1, col_in2, col_in3 = st.columns(3)

            with col_in1:
                search_merchant = st.text_input(
                    "Merchant name", key="search_merchant_input"
                )

            with col_in2:
                search_amount = st.number_input(
                    "Transaction amount",
                    value=None,
                    step=10.0,
                    key="search_amount_input",
                )

            with col_in3:
                search_date = st.date_input(
                    "Transaction date",
                    value=None,
                    key="search_date_input",
                )

        # Filter Parameters Calculation
        query_param = (
            search_merchant.strip() if search_merchant and search_merchant.strip() else None
        )
        amount_param = (
            float(search_amount) if search_amount is not None and search_amount > 0 else None
        )
        date_param = search_date.strftime("%Y-%m-%d") if search_date is not None else None

        search_df = self.repo.search_transactions(
            query=query_param,
            category_ids=None,
            start_date=date_param,
            end_date=date_param,
            min_amount=amount_param,
            max_amount=amount_param,
        )

        st.write("")

        # Row 2: Search Results Table (Full Width, 5 Rows Per Page)
        if search_df.empty:
            st.info("No matching records were found.")
        else:
            col_mapping = {
                "trans_date": "Transaction date",
                "merchant_name": "Merchant name",
                "category_name": "Category",
                "txn_amount": "Transaction amount",
                "hkd_amount": "HKD amount",
                "fx_rate": "FX rate",
            }

            display_cols = [c for c in col_mapping.keys() if c in search_df.columns]
            full_display_df = search_df[display_cols].rename(columns=col_mapping)

            page_size = 5
            total_rows = len(full_display_df)
            total_pages = max(1, math.ceil(total_rows / page_size))

            if "search_current_page" not in st.session_state:
                st.session_state["search_current_page"] = 1

            if st.session_state["search_current_page"] > total_pages:
                st.session_state["search_current_page"] = total_pages
            if st.session_state["search_current_page"] < 1:
                st.session_state["search_current_page"] = 1

            current_page = st.session_state["search_current_page"]
            start_idx = (current_page - 1) * page_size
            end_idx = start_idx + page_size

            page_display_df = full_display_df.iloc[start_idx:end_idx]
            page_search_df = search_df.iloc[start_idx:end_idx].reset_index(drop=True)

            event = st.dataframe(
                page_display_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="search_results_dataframe",
            )

            ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 2, 1])

            with ctrl_col1:
                if st.button(
                    "Previous Page",
                    disabled=(current_page <= 1),
                    key="search_prev_page",
                    use_container_width=True,
                ):
                    st.session_state["search_current_page"] -= 1
                    st.rerun()

            with ctrl_col2:
                st.markdown(
                    f"<div style='text-align: center; padding-top: 0.5rem; color: #FAFAFA;'>Page {current_page} of {total_pages}</div>",
                    unsafe_allow_html=True,
                )

            with ctrl_col3:
                if st.button(
                    "Next Page",
                    disabled=(current_page >= total_pages),
                    key="search_next_page",
                    use_container_width=True,
                ):
                    st.session_state["search_current_page"] += 1
                    st.rerun()

            selected_row_idx = 0
            if hasattr(event, "selection") and event.selection:
                rows = getattr(event.selection, "rows", []) or []
                if isinstance(rows, list) and len(rows) > 0:
                    selected_row_idx = rows[0]

            if selected_row_idx >= len(page_search_df):
                selected_row_idx = 0

            sel_row = page_search_df.iloc[selected_row_idx]
            selected_tx_id = sel_row["id"]

            st.write("")

            # Row 3: Edit Transaction Card
            with st.container(border=True):
                st.subheader("Edit transaction")

                if (
                    "last_selected_tx_id" not in st.session_state
                    or st.session_state["last_selected_tx_id"] != selected_tx_id
                ):
                    st.session_state["last_selected_tx_id"] = selected_tx_id
                    st.session_state["search_edit_cat_select"] = "Select a new category"
                    st.session_state["search_edit_aud"] = ""
                    st.session_state["search_edit_fx"] = ""

                edit_col1, edit_col2 = st.columns(2)

                with edit_col1:
                    st.markdown("**Transaction details**")

                    tx_date = str(sel_row.get("trans_date") or "")
                    tx_merchant = str(sel_row.get("merchant_name") or "")
                    tx_amt = sel_row.get("txn_amount")
                    tx_hkd = sel_row.get("hkd_amount")
                    tx_fx = sel_row.get("fx_rate")

                    amt_str = f"${float(tx_amt):,.2f}" if tx_amt is not None else ""
                    hkd_str = f"${float(tx_hkd):,.2f}" if tx_hkd is not None else ""
                    fx_str = f"{float(tx_fx):.5f}" if tx_fx is not None else ""

                    st.text_input(
                        "Transaction date",
                        value=tx_date,
                        disabled=True,
                        key=f"read_date_{selected_tx_id}",
                    )
                    st.text_input(
                        "Merchant",
                        value=tx_merchant,
                        disabled=True,
                        key=f"read_merchant_{selected_tx_id}",
                    )
                    st.text_input(
                        "Transaction amount",
                        value=amt_str,
                        disabled=True,
                        key=f"read_amt_{selected_tx_id}",
                    )
                    st.text_input(
                        "HKD amount",
                        value=hkd_str,
                        disabled=True,
                        key=f"read_hkd_{selected_tx_id}",
                    )
                    st.text_input(
                        "FX rate",
                        value=fx_str,
                        disabled=True,
                        key=f"read_fx_{selected_tx_id}",
                    )

                with edit_col2:
                    st.markdown("**Update transaction**")

                    edit_cat = st.selectbox(
                        "Category",
                        options=["Select a new category"] + category_list,
                        key="search_edit_cat_select",
                    )

                    edit_aud = st.text_input(
                        "Transaction amount ($AUD)",
                        placeholder="Enter $AUD amount",
                        key="search_edit_aud",
                    )

                    edit_fx = st.text_input(
                        "FX rate",
                        placeholder="Enter exchange rate",
                        key="search_edit_fx",
                    )

                    cat_val = str(edit_cat) if edit_cat else "Select a new category"
                    aud_val = str(edit_aud).strip() if edit_aud else ""
                    fx_val = str(edit_fx).strip() if edit_fx else ""

                    cat_selected = cat_val != "Select a new category"
                    cat_valid = cat_selected and bool(re.match(r"^[A-Za-z\s&\-\/]+$", cat_val))

                    aud_provided = aud_val != ""
                    fx_provided = fx_val != ""
                    partial_pair = (aud_provided and not fx_provided) or (not aud_provided and fx_provided)

                    aud_numeric = (
                        aud_provided
                        and bool(re.match(r"^[0-9.]+$", aud_val))
                        and (aud_val.count(".") <= 1)
                    )
                    fx_numeric = (
                        fx_provided
                        and bool(re.match(r"^[0-9.]+$", fx_val))
                        and (fx_val.count(".") <= 1)
                    )

                    pair_provided = aud_provided or fx_provided
                    pair_valid = aud_provided and fx_provided and aud_numeric and fx_numeric

                    # In-Line Validation Warnings
                    if partial_pair:
                        st.error("Transaction amount ($AUD) and FX rate must be updated together.")

                    if cat_selected and not re.match(r"^[A-Za-z\s&\-\/]+$", cat_val):
                        st.error("Input must contain ONLY letters, spaces, ampersands (&), hyphens (-), or slashes (/).")

                    has_non_numeric_error = False
                    if aud_provided and not aud_numeric:
                        st.error("Input must contain ONLY numbers and periods ( . )")
                        has_non_numeric_error = True

                    if fx_provided and not fx_numeric and not has_non_numeric_error:
                        st.error("Input must contain ONLY numbers and periods ( . )")

                    button_enabled = (
                        (cat_valid if cat_selected else True)
                        and (pair_valid if pair_provided else True)
                        and (cat_selected or pair_provided)
                    )

                    update_btn = st.button(
                        "Update transaction",
                        type="primary",
                        disabled=not button_enabled,
                        key="search_update_tx_btn",
                    )

                    if update_btn and button_enabled:
                        new_cat_id = cat_name_to_id.get(cat_val) if cat_selected else None
                        new_cat_name = cat_val if cat_selected else None
                        new_aud = float(aud_val) if pair_valid else None
                        new_fx = float(fx_val) if pair_valid else None

                        confirm_update_transaction_dialog(
                            selected_tx_id=selected_tx_id,
                            new_cat_id=new_cat_id,
                            new_cat_name=new_cat_name,
                            new_aud=new_aud,
                            new_fx=new_fx,
                        )

    def run(self) -> None:
        st.set_page_config(
            page_title="Personal Expense Tracker",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        selected = self.render_sidebar()
        page_title = "Charts" if selected == "Charts" else selected
        self.inject_css(page_title)

        if selected == "Upload":
            self.render_upload_page()
        elif selected == "Categorise":
            self.render_categorise_page()
        elif selected == "Dashboard":
            st.info(
                "Dashboard View - Select 'Upload' to ingest statements or 'Categorise' to manage rules."
            )
        elif selected == "Charts":
            self.render_charts_page()
        elif selected == "Search":
            self.render_search_page()


if __name__ == "__main__":
    app = PersonalExpenseTracker()
    app.run()