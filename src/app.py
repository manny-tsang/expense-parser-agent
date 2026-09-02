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


class PersonalExpenseTracker:
    def __init__(self) -> None:
        self.repo = DatabaseRepository(DB_PATH)

    @staticmethod
    def inject_css(page_title: str) -> None:
        css = f"""
        <style>
        /* 1. Sidebar Header & Collapse Toggle Alignment */
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
                options=["Dashboard", "Upload", "Categorise", "Charts"],
                icons=["house", "cloud-upload", "tag", "bar-chart"],
                default_index=1,
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
        df = self.repo.get_transactions_dataframe()
        total_txns = len(df)
        period_from, period_to = self.get_date_range(df)

        col1, col2, col3 = st.columns(3)

        with col1:
            with st.container(border=True, height="stretch"):
                # st.markdown(
                #     '<div class="metric-card-container">Upload a PDF statement</div>',
                #     unsafe_allow_html=True,
                # )
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

                        result = parse_statement(tmp_path, DB_PATH)
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

        display_cols = [
            c
            for c in [
                "trans_date",
                "merchant",
                "category_name",
                "txn_amount",
                "purchase_currency",
                "hkd_amount",
                "fx_rate",
            ]
            if c in df.columns
        ]
        display_df = df[display_cols] if not df.empty and display_cols else df

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
        tx_df = self.repo.get_transactions_dataframe()

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

        tx_ids: List[Optional[int]] = [None]
        tx_display_map: Dict[Optional[int], str] = {None: "Select a transaction"}
        tx_cat_map: Dict[Optional[int], str] = {None: ""}

        if not tx_df.empty and "id" in tx_df.columns:
            for _, row in tx_df.iterrows():
                tx_id = row["id"]
                if pd.notna(tx_id):
                    tx_id_int = int(tx_id)
                    tx_ids.append(tx_id_int)

                    trans_date = str(row.get("trans_date", ""))
                    merchant_name = str(row.get("merchant", ""))
                    curr = str(row.get("purchase_currency") or "HKD")
                    amt = row.get("txn_amount", 0.0)
                    try:
                        amt_str = f"{float(amt):.2f}"
                    except (ValueError, TypeError):
                        amt_str = str(amt)

                    tx_display_map[
                        tx_id_int
                    ] = f"{trans_date} | {merchant_name} | {curr} {amt_str}"

                    cat_val = row.get("category_name")
                    tx_cat_map[tx_id_int] = (
                        str(cat_val) if pd.notna(cat_val) and cat_val else ""
                    )

        col1, col2, col3 = st.columns(3)

        with col1:
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

        with col2:
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

                current_merchant_cat = merchant_cat_map.get(
                    selected_merchant if selected_merchant != "Select a merchant" else "", ""
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

        with col3:
            with st.container(border=True, height="stretch"):
                st.subheader("Update transaction category")
                st.markdown(
                    "Update the category for a single transaction where the default category is not suitable. Example: 'BP' transaction not for 'Fuel'."
                )

                selected_tx_id = st.selectbox(
                    "Transaction",
                    options=tx_ids,
                    format_func=lambda tx_id: tx_display_map.get(
                        tx_id, "Select a transaction"
                    ),
                    key="selected_tx_dropdown",
                )

                current_tx_cat = tx_cat_map.get(selected_tx_id, "")

                subcol1, subcol2 = st.columns(2)

                with subcol1:
                    st.text_input(
                        "Current category",
                        value=current_tx_cat,
                        disabled=True,
                        key=f"current_cat_display_{selected_tx_id}",
                    )

                with subcol2:
                    selected_new_cat = st.selectbox(
                        "New category",
                        options=["Select a category"] + category_list,
                        key="tx_cat_select",
                    )

                update_tx_btn = st.button(
                    "Update transaction category",
                    type="primary",
                    key="update_tx_category",
                )

                if update_tx_btn:
                    if (
                        selected_tx_id is None
                        or selected_new_cat == "Select a category"
                    ):
                        st.error(
                            "Please select both a transaction and a new category before updating."
                        )
                    elif selected_new_cat == current_tx_cat:
                        st.error(
                            "'Current category' and 'New category' must not be the same."
                        )
                    else:
                        new_c_id = cat_name_to_id.get(selected_new_cat, 1)
                        confirm_tx_category_dialog(
                            current_tx_cat,
                            selected_new_cat,
                            int(selected_tx_id),
                            new_c_id,
                        )

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

        # Prepare base dataframe with datetime conversion
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

        # Row 1 Layout: Donut Chart (Col 1) and Filter Control Card (Col 2)
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

        # Apply filtering
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

        # Determine non-AUD transactions
        has_non_aud = False
        if not filtered_df.empty and "purchase_currency" in filtered_df.columns:
            non_aud_mask = filtered_df["purchase_currency"].astype(str).str.upper().ne("AUD")
            has_non_aud = bool(non_aud_mask.any())

        # Render Donut Chart (Col 1)
        with col1:
            with st.container(border=True, height="stretch"):
                st.subheader("Expense Category Breakdown")
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

        # Row 2: Expense Category Statistics Table
        st.write("")
        with st.container(border=True):
            st.subheader("Expense Category Statistics")
            st.markdown(
                "Monthly averages calculated across the selected date range for direct import into budget spreadsheets."
            )

            if filtered_df.empty:
                st.info("No transaction data available for statistics.")
            else:
                # Calculate months in range N
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

                    # Apply outlier visual indicator (asterisk)
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


if __name__ == "__main__":
    app = PersonalExpenseTracker()
    app.run()