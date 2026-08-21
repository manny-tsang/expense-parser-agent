import math
import os
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

try:
    from src.pdf_parser import DatabaseRepository, parse_statement
except ImportError:
    try:
        from pdf_parser import DatabaseRepository, parse_statement
    except ImportError:

        def parse_statement(
            file_path: str, db_path: str = "db/personal-expense-tracker.db"
        ) -> bool:
            return False

        class DatabaseRepository:  # type: ignore
            def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
                self.db_path = db_path

            def get_connection(self) -> sqlite3.Connection:
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                return sqlite3.connect(self.db_path)

            def get_transactions_dataframe(self) -> pd.DataFrame:
                if not os.path.exists(self.db_path):
                    return pd.DataFrame(
                        columns=[
                            "id",
                            "trans_date",
                            "merchant",
                            "category_name",
                            "txn_amount",
                            "purchase_currency",
                            "hkd_amount",
                            "fx_rate",
                            "category_id",
                        ]
                    )
                try:
                    with self.get_connection() as conn:
                        query = """
                        SELECT 
                            t.id,
                            t.trans_date, 
                            m.merchant_name AS merchant, 
                            COALESCE(override_cat.category_name, default_cat.category_name) AS category_name, 
                            t.txn_amount, 
                            curr.currency_code AS purchase_currency, 
                            t.hkd_amount, 
                            t.fx_rate,
                            t.category_id
                        FROM "transaction" t
                        JOIN merchant m ON t.merchant_id = m.id
                        LEFT JOIN category default_cat ON m.category_id = default_cat.id
                        LEFT JOIN category override_cat ON t.category_id = override_cat.id
                        LEFT JOIN currency curr ON t.purchase_currency_id = curr.id
                        ORDER BY t.trans_date DESC, t.id DESC
                        """
                        return pd.read_sql_query(query, conn)
                except Exception:
                    try:
                        with self.get_connection() as conn:
                            query_fallback = """
                            SELECT 
                                t.id,
                                t.trans_date, 
                                t.merchant, 
                                c.category_name, 
                                t.txn_amount, 
                                curr.currency_code AS purchase_currency, 
                                t.hkd_amount, 
                                t.fx_rate,
                                t.category_id
                            FROM "transaction" t
                            LEFT JOIN category c ON t.category_id = c.id
                            LEFT JOIN currency curr ON t.purchase_currency_id = curr.id
                            ORDER BY t.trans_date DESC, t.id DESC
                            """
                            return pd.read_sql_query(query_fallback, conn)
                    except Exception:
                        return pd.DataFrame(
                            columns=[
                                "id",
                                "trans_date",
                                "merchant",
                                "category_name",
                                "txn_amount",
                                "purchase_currency",
                                "hkd_amount",
                                "fx_rate",
                                "category_id",
                            ]
                        )

            def get_categories(self) -> pd.DataFrame:
                if not os.path.exists(self.db_path):
                    return pd.DataFrame(columns=["id", "category_name"])
                try:
                    with self.get_connection() as conn:
                        query = (
                            'SELECT id, category_name FROM "category" ORDER BY category_name ASC'
                        )
                        return pd.read_sql_query(query, conn)
                except Exception:
                    return pd.DataFrame(columns=["id", "category_name"])

            def get_uncategorised_merchants(self) -> pd.DataFrame:
                if not os.path.exists(self.db_path):
                    return pd.DataFrame(
                        columns=["merchant_id", "merchant_name", "transaction_count"]
                    )
                try:
                    with self.get_connection() as conn:
                        query = """
                        SELECT 
                            m.id AS merchant_id,
                            m.merchant_name, 
                            COUNT(t.id) AS transaction_count
                        FROM "transaction" t
                        JOIN merchant m ON t.merchant_id = m.id
                        WHERE m.category_id = 1 AND t.category_id IS NULL
                        GROUP BY m.id, m.merchant_name
                        ORDER BY transaction_count DESC, m.merchant_name ASC
                        """
                        return pd.read_sql_query(query, conn)
                except Exception:
                    try:
                        with self.get_connection() as conn:
                            query_fallback = """
                            SELECT 
                                t.merchant AS merchant_name, 
                                COUNT(t.id) AS transaction_count
                            FROM "transaction" t
                            LEFT JOIN category c ON t.category_id = c.id
                            WHERE c.category_name = 'Uncategorised' OR t.category_id = 1 OR t.category_id IS NULL
                            GROUP BY t.merchant
                            ORDER BY transaction_count DESC, t.merchant ASC
                            """
                            return pd.read_sql_query(query_fallback, conn)
                    except Exception:
                        return pd.DataFrame(
                            columns=["merchant_name", "transaction_count"]
                        )

            def update_merchant_category(
                self, merchant_id_or_name: Union[int, str], category_id: int
            ) -> bool:
                if not os.path.exists(self.db_path):
                    return False
                try:
                    with self.get_connection() as conn:
                        cursor = conn.cursor()
                        if isinstance(merchant_id_or_name, int):
                            cursor.execute(
                                "UPDATE merchant SET category_id = ? WHERE id = ?",
                                (category_id, merchant_id_or_name),
                            )
                        else:
                            cursor.execute(
                                "UPDATE merchant SET category_id = ? WHERE merchant_name = ?",
                                (category_id, str(merchant_id_or_name)),
                            )
                        conn.commit()
                        return True
                except Exception:
                    return False

            def update_transaction_category(
                self, transaction_id: int, category_id: int
            ) -> bool:
                if not os.path.exists(self.db_path):
                    return False
                try:
                    with self.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            'UPDATE "transaction" SET category_id = ? WHERE id = ?',
                            (category_id, transaction_id),
                        )
                        conn.commit()
                        return True
                except Exception:
                    return False


DB_PATH = "db/personal-expense-tracker.db"


@st.dialog("Confirm Merchant Mapping")
def confirm_merchant_mapping_dialog(
    selected_merchant: str,
    selected_category: str,
    target_id: Any,
    cat_id: int,
    repo: DatabaseRepository,
) -> None:
    st.write(
        f"Are you sure you want to map all transactions for '{selected_merchant}' to '{selected_category}'?"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", key="dialog_cancel_global"):
            st.session_state["show_global_dialog"] = False
            st.rerun()
    with col2:
        if st.button("Save", type="primary", key="dialog_save_global"):
            repo.update_merchant_category(target_id, cat_id)
            st.session_state["show_global_dialog"] = False
            st.rerun()


@st.dialog("Confirm Transaction Category Update")
def confirm_tx_category_dialog(
    current_cat_name: str,
    selected_new_cat: str,
    selected_tx_id: int,
    new_cat_id: int,
    repo: DatabaseRepository,
) -> None:
    st.write(
        f"Are you sure you want to update this transaction's category from '{current_cat_name}' to '{selected_new_cat}'?"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", key="dialog_cancel_tx"):
            st.session_state["show_tx_dialog"] = False
            st.rerun()
    with col2:
        if st.button("Update", type="primary", key="dialog_update_tx"):
            repo.update_transaction_category(selected_tx_id, new_cat_id)
            st.session_state["show_tx_dialog"] = False
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
                default_index=0,
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
                st.markdown(
                    '<div class="metric-card-container">Upload a PDF statement</div>',
                    unsafe_allow_html=True,
                )
                uploaded_file = st.file_uploader(
                    "Upload PDF", type=["pdf"], label_visibility="collapsed"
                )
                process_btn = st.button(
                    "Process Statement", type="primary", use_container_width=True
                )

        with col2:
            with st.container(border=True, height="stretch"):
                st.markdown(
                    f"""<div class="metric-card-container">
                        <div>Total transactions uploaded</div>
                        <div class="metric-large">{total_txns}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        with col3:
            with st.container(border=True, height="stretch"):
                st.markdown(
                    f"""<div class="metric-card-container">
                        <div>Statement period uploaded</div>
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
                use_container_width=True,
            ):
                st.session_state["current_page"] += 1
                st.rerun()

    def render_categorise_page(self) -> None:
        uncat_df = self.repo.get_uncategorised_merchants()
        categories_df = self.repo.get_categories()
        tx_df = self.repo.get_transactions_dataframe()

        category_list: List[str] = []
        cat_name_to_id: Dict[str, int] = {}
        if not categories_df.empty and "category_name" in categories_df.columns:
            category_list = categories_df["category_name"].dropna().tolist()
            cat_name_to_id = dict(
                zip(categories_df["category_name"], categories_df["id"])
            )

        uncat_list: List[str] = []
        merchant_id_map: Dict[str, Any] = {}
        m_col = (
            "merchant_name" if "merchant_name" in uncat_df.columns else "merchant"
        )
        if not uncat_df.empty and m_col in uncat_df.columns:
            uncat_list = uncat_df[m_col].dropna().tolist()
            if "merchant_id" in uncat_df.columns:
                merchant_id_map = dict(zip(uncat_df[m_col], uncat_df["merchant_id"]))

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

        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True, height="stretch"):
                st.subheader("Merchant mapping")
                st.markdown(
                    "Select an uncategorised merchant and a category to create a mapping. "
                    "Saving this mapping will re-categorise ALL transactions made at the chosen merchant to the selected category."
                )

                selected_merchant = st.selectbox(
                    "Merchant",
                    options=["Select a merchant"] + uncat_list,
                    key="global_merchant_select",
                )

                selected_category = st.selectbox(
                    "Category",
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
                            "Please select both a merchant and a category before saving."
                        )
                    else:
                        st.session_state["show_global_dialog"] = True

        if st.session_state.get("show_global_dialog", False):
            selected_m = st.session_state.get(
                "global_merchant_select", "Select a merchant"
            )
            selected_c = st.session_state.get(
                "global_category_select", "Select a category"
            )
            if selected_m != "Select a merchant" and selected_c != "Select a category":
                target_id = merchant_id_map.get(selected_m, selected_m)
                cat_id = cat_name_to_id.get(selected_c, 1)
                confirm_merchant_mapping_dialog(
                    selected_m, selected_c, target_id, cat_id, self.repo
                )

        with col2:
            with st.container(border=True, height="stretch"):
                st.subheader("Update transaction category")
                st.markdown(
                    "Set the category for a specific transaction where the default category mapping may not be correct, "
                    "e.g. a transaction at BP was for groceries instead of fuel as no fuel was purchased, only water. "
                    "Fuel being the default category mapping."
                )

                selected_tx_id = st.selectbox(
                    "Transaction",
                    options=tx_ids,
                    format_func=lambda tx_id: tx_display_map.get(
                        tx_id, "Select a transaction"
                    ),
                    key="selected_tx_dropdown",
                )

                subcol1, subcol2 = st.columns(2)

                with subcol1:
                    st.text_input(
                        "Current category",
                        value=tx_cat_map.get(selected_tx_id, ""),
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
                    else:
                        st.session_state["show_tx_dialog"] = True

        if st.session_state.get("show_tx_dialog", False):
            sel_tx_id = st.session_state.get("selected_tx_dropdown")
            sel_new_c = st.session_state.get("tx_cat_select", "Select a category")
            if sel_tx_id is not None and sel_new_c != "Select a category":
                cur_cat = tx_cat_map.get(sel_tx_id, "")
                new_c_id = cat_name_to_id.get(sel_new_c, 1)
                confirm_tx_category_dialog(
                    cur_cat, sel_new_c, int(sel_tx_id), new_c_id, self.repo
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

    def run(self) -> None:
        st.set_page_config(
            page_title="Personal Expense Tracker",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        selected = self.render_sidebar()
        self.inject_css(selected)

        if selected == "Upload":
            self.render_upload_page()
        elif selected == "Categorise":
            self.render_categorise_page()
        elif selected == "Dashboard":
            st.info(
                "Dashboard View - Select 'Upload' to ingest statements or 'Categorise' to manage rules."
            )
        elif selected == "Charts":
            st.info(
                "Charts View - Select 'Upload' to ingest statements or 'Categorise' to manage rules."
            )


if __name__ == "__main__":
    app = PersonalExpenseTracker()
    app.run()