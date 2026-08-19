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

        def parse_statement(file_path: str, db_path: str = "db/personal-expense-tracker.db") -> bool:
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
                            t.trans_date, 
                            t.merchant, 
                            c.category_name, 
                            t.txn_amount, 
                            curr.currency_code AS purchase_currency, 
                            t.hkd_amount, 
                            t.fx_rate
                        FROM "transaction" t
                        LEFT JOIN category c ON t.category_id = c.id
                        LEFT JOIN currency curr ON t.purchase_currency_id = curr.id
                        ORDER BY t.trans_date DESC, t.id DESC
                        """
                        return pd.read_sql_query(query, conn)
                except Exception:
                    return pd.DataFrame(
                        columns=[
                            "trans_date",
                            "merchant",
                            "category_name",
                            "txn_amount",
                            "purchase_currency",
                            "hkd_amount",
                            "fx_rate",
                        ]
                    )

            def get_categories(self) -> pd.DataFrame:
                if not os.path.exists(self.db_path):
                    return pd.DataFrame(columns=["id", "category_name"])
                try:
                    with self.get_connection() as conn:
                        query = 'SELECT id, category_name FROM "category" ORDER BY category_name ASC'
                        return pd.read_sql_query(query, conn)
                except Exception:
                    return pd.DataFrame(columns=["id", "category_name"])

            def get_uncategorised_merchants(self) -> pd.DataFrame:
                if not os.path.exists(self.db_path):
                    return pd.DataFrame(columns=["merchant", "transaction_count"])
                try:
                    with self.get_connection() as conn:
                        query = """
                        SELECT t.merchant, COUNT(t.id) AS transaction_count
                        FROM "transaction" t
                        JOIN category c ON t.category_id = c.id
                        WHERE c.category_name = 'Uncategorised'
                        GROUP BY t.merchant
                        ORDER BY transaction_count DESC, t.merchant ASC
                        """
                        return pd.read_sql_query(query, conn)
                except Exception:
                    return pd.DataFrame(columns=["merchant", "transaction_count"])

            def add_merchant_mapping_rule(self, pattern: str, category_id: int) -> bool:
                if not pattern or not pattern.strip():
                    return False
                clean_pattern = pattern.strip()
                try:
                    with self.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            'INSERT OR REPLACE INTO "merchant_mapping" (pattern, category_id) VALUES (?, ?)',
                            (clean_pattern, category_id),
                        )
                        cursor.execute(
                            """
                            UPDATE "transaction"
                            SET category_id = ?
                            WHERE UPPER(merchant) LIKE '%' || UPPER(?) || '%'
                            """,
                            (category_id, clean_pattern),
                        )
                        conn.commit()
                        return True
                except Exception:
                    return False

            def update_transaction_category(self, transaction_id: int, category_id: int) -> bool:
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
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
        }}
        [data-testid="stSidebarContent"] {{
            padding-top: 0rem !important;
        }}

        /* 2. Solid Top Sticky Header & Persistent Title Injection */
        [data-testid="stHeader"] {{
            background-color: #0e1117 !important;
            z-index: 999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }}

        .sticky-page-title {{
            position: fixed;
            top: 0.75rem;
            left: 3.5rem;
            z-index: 1001 !important;
            pointer-events: none;
            font-size: 1.25rem;
            font-weight: 600;
            color: #FFFFFF;
        }}

        /* 3. Main Content Padding */
        .block-container {{
            padding-top: 3.5rem !important;
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

        .metric-card-title {{
            font-size: 0.95rem;
            color: #A0A0A0;
            font-weight: 500;
            margin-bottom: 0.5rem;
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

    def render_sidebar(self) -> str:
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
            with st.container(border=True):
                st.markdown(
                    '<div class="metric-card-title">Upload a PDF statement</div>',
                    unsafe_allow_html=True,
                )
                uploaded_file = st.file_uploader(
                    "Upload PDF", type=["pdf"], label_visibility="collapsed"
                )
                process_btn = st.button(
                    "Process Statement", type="primary", use_container_width=True
                )

        with col2:
            with st.container(border=True):
                st.markdown(
                    f"""<div class="metric-card-container">
                        <div class="metric-card-title">Total transactions uploaded</div>
                        <div class="metric-large">{total_txns}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        with col3:
            with st.container(border=True):
                st.markdown(
                    f"""<div class="metric-card-container">
                        <div class="metric-card-title">Statement period uploaded</div>
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
                            st.error("Error processing statement. Invalid or duplicate format.")
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
        st.markdown("Map uncategorised merchants to categories globally.")

        uncat_df = self.repo.get_uncategorised_merchants()
        categories_df = self.repo.get_categories()

        st.subheader("Uncategorised Merchants")
        if not uncat_df.empty:
            st.dataframe(uncat_df, use_container_width=True, hide_index=True)
        else:
            st.info("No uncategorised merchants found.")

        st.markdown("---")
        st.subheader("Global Merchant Mapping Rule")

        uncat_list = uncat_df["merchant"].tolist() if not uncat_df.empty else []

        col_rule1, col_rule2 = st.columns(2)

        with col_rule1:
            selected_merchant_option = st.selectbox(
                "Select Uncategorised Merchant (or enter custom pattern below)",
                options=["-- Custom Pattern --"] + uncat_list,
            )
            if selected_merchant_option == "-- Custom Pattern --":
                pattern_input = st.text_input("Merchant Pattern / Keyword", value="")
            else:
                pattern_input = st.text_input("Merchant Pattern / Keyword", value=selected_merchant_option)

        with col_rule2:
            selected_cat_id: Optional[int] = None
            if not categories_df.empty:
                cat_options = dict(zip(categories_df["category_name"], categories_df["id"]))
                selected_cat_name = st.selectbox("Target Category", options=list(cat_options.keys()))
                selected_cat_id = cat_options[selected_cat_name]
            else:
                st.warning("No categories found in database.")

        save_rule_btn = st.button("Save & Apply Rule", type="primary")

        if save_rule_btn:
            if not pattern_input or not pattern_input.strip():
                st.error("Please enter a valid merchant pattern.")
            elif selected_cat_id is None:
                st.error("Please select a target category.")
            else:
                success = self.repo.add_merchant_mapping_rule(pattern_input.strip(), selected_cat_id)
                if success:
                    st.success(f"Rule for '{pattern_input.strip()}' saved and applied successfully!")
                    st.rerun()
                else:
                    st.error("Failed to save and apply global merchant rule.")

        st.markdown("---")
        st.subheader("Transaction-Level Category Override")
        st.markdown("Reclassify an individual transaction without creating a global merchant rule.")

        tx_df = self.repo.get_transactions_dataframe()

        if not tx_df.empty and "id" in tx_df.columns:
            tx_df["display_label"] = tx_df.apply(
                lambda r: f"ID {r['id']} | {r['trans_date']} | {r['merchant']} | HKD {r['hkd_amount']} | Current: {r['category_name']}",
                axis=1,
            )
            tx_options = dict(zip(tx_df["display_label"], tx_df["id"]))

            col_tx1, col_tx2 = st.columns(2)
            with col_tx1:
                selected_tx_label = st.selectbox("Select Transaction to Override", options=list(tx_options.keys()))
                selected_tx_id = tx_options[selected_tx_label]

            with col_tx2:
                override_cat_id: Optional[int] = None
                override_cat_name: Optional[str] = None
                if not categories_df.empty:
                    cat_options_override = dict(zip(categories_df["category_name"], categories_df["id"]))
                    override_cat_name = st.selectbox("New Category", options=list(cat_options_override.keys()), key="tx_override_cat")
                    override_cat_id = cat_options_override[override_cat_name]
                else:
                    st.warning("No categories found in database.")

            override_btn = st.button("Override Category for Transaction")

            if override_btn:
                if selected_tx_id is not None and override_cat_id is not None:
                    success = self.repo.update_transaction_category(int(selected_tx_id), override_cat_id)
                    if success:
                        st.success(f"Transaction ID {selected_tx_id} updated to category '{override_cat_name}'.")
                        st.rerun()
                    else:
                        st.error("Failed to update transaction category.")
                else:
                    st.error("Please select both a transaction and a valid target category.")
        else:
            st.info("No transactions available for category override.")

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
            st.info("Dashboard View - Select 'Upload' to ingest statements or 'Categorise' to manage rules.")
        elif selected == "Charts":
            st.info("Charts View - Select 'Upload' to ingest statements or 'Categorise' to manage rules.")


if __name__ == "__main__":
    app = PersonalExpenseTracker()
    app.run()