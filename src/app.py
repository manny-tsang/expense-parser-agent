import math
import os
import sqlite3
import tempfile
from typing import Optional, Tuple

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
                    return pd.DataFrame(columns=["merchant_id", "merchant_name", "transaction_count"])
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
                        return pd.DataFrame(columns=["merchant_name", "transaction_count"])

            def update_merchant_category(
                self, merchant_id: Optional[int], pattern: str, category_id: int
            ) -> bool:
                if not os.path.exists(self.db_path):
                    return False
                try:
                    with self.get_connection() as conn:
                        cursor = conn.cursor()
                        if merchant_id is not None:
                            cursor.execute(
                                "UPDATE merchant SET category_id = ? WHERE id = ?",
                                (category_id, merchant_id),
                            )
                        if pattern and pattern.strip():
                            clean_pattern = pattern.strip()
                            cursor.execute(
                                """
                                UPDATE merchant 
                                SET category_id = ? 
                                WHERE UPPER(merchant_name) LIKE '%' || UPPER(?) || '%'
                                """,
                                (category_id, clean_pattern),
                            )
                            try:
                                cursor.execute(
                                    'INSERT OR REPLACE INTO "merchant_mapping" (pattern, category_id) VALUES (?, ?)',
                                    (clean_pattern, category_id),
                                )
                            except Exception:
                                pass
                            try:
                                cursor.execute(
                                    """
                                    UPDATE "transaction"
                                    SET category_id = ?
                                    WHERE UPPER(merchant) LIKE '%' || UPPER(?) || '%'
                                    """,
                                    (category_id, clean_pattern),
                                )
                            except Exception:
                                pass
                        conn.commit()
                        return True
                except Exception:
                    return False

            def add_merchant_mapping_rule(self, pattern: str, category_id: int) -> bool:
                return self.update_merchant_category(None, pattern, category_id)

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
        return selected

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

        # Row 1: 2 Columns
        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True, height="stretch"):
                st.subheader("Global merchant mapping")
                st.markdown(
                    "Select an uncategorised merchant and a category to create a mapping. "
                    "Creating this will re-categorise all transactions made at the chosen merchant to the selected category."
                )

                uncat_names = []
                merchant_id_map = {}
                m_col = "merchant_name" if "merchant_name" in uncat_df.columns else "merchant"
                if not uncat_df.empty and m_col in uncat_df.columns:
                    uncat_names = uncat_df[m_col].dropna().tolist()
                    if "merchant_id" in uncat_df.columns:
                        merchant_id_map = dict(zip(uncat_df[m_col], uncat_df["merchant_id"]))

                selected_merchant = st.selectbox(
                    "Merchant",
                    options=["-- Custom Pattern --"] + uncat_names,
                    key="global_merchant_select",
                )

                default_pattern = (
                    "" if selected_merchant == "-- Custom Pattern --" else selected_merchant
                )
                pattern_input = st.text_input(
                    "Merchant pattern / keyword",
                    value=default_pattern,
                    key="global_pattern_input",
                )

                selected_cat_id: Optional[int] = None
                if not categories_df.empty:
                    cat_options = dict(
                        zip(categories_df["category_name"], categories_df["id"])
                    )
                    selected_cat_name = st.selectbox(
                        "Category",
                        options=list(cat_options.keys()),
                        key="global_category_select",
                    )
                    selected_cat_id = cat_options[selected_cat_name]
                else:
                    st.warning("No categories found in database.")

                save_mapping_btn = st.button(
                    "Save mapping", type="primary", key="save_global_mapping"
                )

                if save_mapping_btn:
                    if not pattern_input or not pattern_input.strip():
                        st.error("Please enter a valid merchant pattern / keyword.")
                    elif selected_cat_id is None:
                        st.error("Please select a target category.")
                    else:
                        target_merchant_id = merchant_id_map.get(selected_merchant)
                        if hasattr(self.repo, "update_merchant_category"):
                            success = self.repo.update_merchant_category(
                                target_merchant_id, pattern_input.strip(), selected_cat_id
                            )
                        else:
                            success = self.repo.add_merchant_mapping_rule(
                                pattern_input.strip(), selected_cat_id
                            )
                        if success:
                            st.success(
                                f"Global mapping for '{pattern_input.strip()}' saved successfully!"
                            )
                            st.rerun()
                        else:
                            st.error("Failed to save and apply global merchant mapping.")

        with col2:
            with st.container(border=True, height="stretch"):
                st.subheader("Transaction-level category mapping")
                st.markdown(
                    "Set the category for a specific transaction where the default category mapping may not be correct, "
                    "e.g. a transaction at BP was for groceries instead of fuel as no fuel was purchased, only water. "
                    "Fuel being the default category mapping."
                )

                selected_tx_id: Optional[int] = None
                if not tx_df.empty and "id" in tx_df.columns:
                    tx_df["display_label"] = tx_df.apply(
                        lambda r: f"ID {r['id']} | {r.get('trans_date', '')} | {r.get('merchant', '')} | HKD {r.get('hkd_amount', 0)} | Current: {r.get('category_name', 'Uncategorised')}",
                        axis=1,
                    )
                    tx_options = dict(zip(tx_df["display_label"], tx_df["id"]))
                    selected_tx_label = st.selectbox(
                        "Transaction", options=list(tx_options.keys()), key="tx_select"
                    )
                    selected_tx_id = tx_options[selected_tx_label]
                else:
                    st.info("No transactions available.")

                selected_tx_cat_id: Optional[int] = None
                if not categories_df.empty:
                    cat_options_tx = dict(
                        zip(categories_df["category_name"], categories_df["id"])
                    )
                    selected_tx_cat_name = st.selectbox(
                        "Category",
                        options=list(cat_options_tx.keys()),
                        key="tx_cat_select",
                    )
                    selected_tx_cat_id = cat_options_tx[selected_tx_cat_name]
                else:
                    st.warning("No categories found in database.")

                update_tx_btn = st.button(
                    "Update transaction category",
                    type="primary",
                    key="update_tx_category",
                )

                if update_tx_btn:
                    if selected_tx_id is not None and selected_tx_cat_id is not None:
                        success = self.repo.update_transaction_category(
                            int(selected_tx_id), selected_tx_cat_id
                        )
                        if success:
                            st.success(
                                f"Transaction ID {selected_tx_id} category updated successfully!"
                            )
                            st.rerun()
                        else:
                            st.error("Failed to update transaction category.")
                    else:
                        st.error("Please select both a transaction and a category.")

        # Row 2: Full Width
        st.subheader("Uncategorised merchants")
        st.markdown(
            "List of merchants currently assigned to 'Uncategorised' requiring mapping."
        )

        if not uncat_df.empty:
            m_col = "merchant_name" if "merchant_name" in uncat_df.columns else "merchant"
            display_cols = [c for c in [m_col, "transaction_count"] if c in uncat_df.columns]
            display_uncat_df = uncat_df[display_cols].copy()
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
        else:
            st.info("No uncategorised merchants found.")

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