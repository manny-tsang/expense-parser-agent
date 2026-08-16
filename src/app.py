import math
import os
import re
import sqlite3
import tempfile
from typing import Optional, Tuple

import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:

        def parse_statement(file_path: str, db_path: str) -> bool:
            return False


DB_PATH = "db/personal-expense-tracker.db"


class DatabaseRepository:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return sqlite3.connect(self.db_path)

    def get_transactions_dataframe(self) -> pd.DataFrame:
        if not os.path.exists(self.db_path):
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
                df = pd.read_sql_query(query, conn)
                return df
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


class StatementApp:
    def __init__(self) -> None:
        self.repo = DatabaseRepository()

    @staticmethod
    def inject_css() -> None:
        css = """
        <style>
        /* 1. Flush Sidebar Top Alignment */
        [data-testid="stSidebarHeader"] {
            display: none !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 0.5rem !important;
        }
        [data-testid="stSidebarContent"] {
            padding-top: 0rem !important;
            margin-top: 0rem !important;
        }

        /* 2. Solid Left-Aligned Sticky Header */
        [data-testid="stHeader"] {
            background-color: #0e1117 !important;
            z-index: 999 !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: center !important;
            padding-left: 2rem !important;
        }

        [data-testid="stHeader"]::before {
            content: "Upload";
            font-size: 1.75rem;
            font-weight: 700;
            color: #FFFFFF;
            margin-right: auto;
        }

        .block-container {
            padding-top: 4rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

/* 3. Equal Column Height Match across all 3 Cards */
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            display: flex !important;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            width: 100% !important;
            display: flex !important;
            flex: 1 !important;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
            width: 100% !important;
            min-height: 215px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
        }

        .metric-card-container {
            height: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            padding: 0.25rem 0 !important;
        }

        .metric-large {
            font-size: 8.8rem;
            font-weight: bold;
            color: #FFFFFF;
            line-height: 1.1;
            margin-top: 0.5rem;
        }

        .metric-card-title {
            font-size: 0.95rem;
            color: #A0A0A0;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .period-label {
            font-size: 0.85rem;
            color: #808495;
            margin-top: 0.25rem;
        }

        .period-val {
            font-size: 2rem;
            font-weight: 600;
            color: #FFFFFF;
            margin-bottom: 0.25rem;
        }
        </style>
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
                options=["Dashboard", "Upload", "Charts"],
                icons=["house", "cloud-upload", "bar-chart"],
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
                        else:
                            st.error("Error processing statement. Invalid or duplicate format.")
                    except Exception as e:
                        st.error(f"Error processing statement: {e}")
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)
            else:
                st.warning("Please select a PDF file to process.")

        # Show success banner if flag exists, then clear it
        if st.session_state.pop("upload_success", False):
            st.success("Statement processed successfully!")

        st.write("")
        st.subheader("Transactions uploaded")

        total_rows = len(df)
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

        page_df = df.iloc[start_idx:end_idx]
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

    def run(self) -> None:
        st.set_page_config(
            page_title="Statement Ingestion & Operational Dashboard",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        self.inject_css()
        selected = self.render_sidebar()

        if selected == "Upload":
            self.render_upload_page()
        elif selected == "Dashboard":
            st.info("Dashboard View - Select 'Upload' to ingest statements.")
        elif selected == "Charts":
            st.info("Charts View - Select 'Upload' to ingest statements.")


if __name__ == "__main__":
    app = StatementApp()
    app.run()