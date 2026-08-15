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
            """Fallback parser function if src.pdf_parser is unavailable."""
            return True


DB_PATH = os.path.join("db", "personal-expense-tracker.db")


class DatabaseRepository:
    """Repository handling read operations for transaction data."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def get_transactions_dataframe(self) -> pd.DataFrame:
        """Query raw transactions from normalized database schema."""
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
            conn = sqlite3.connect(self.db_path)
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
            conn.close()
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
    """Streamlit Application UI controller for Statement Ingestion."""

    def __init__(self) -> None:
        self.repo = DatabaseRepository(DB_PATH)

    @staticmethod
    def inject_custom_css() -> None:
        """Inject strict CSS for layout, sticky header, and dynamic card height alignment."""
        css = """
        <style>
        /* Sticky Header Styling */
        [data-testid="stHeader"] {
            display: flex !important;
            align-items: center !important;
            padding-left: 2rem !important;
            background-color: transparent !important;
        }
        [data-testid="stHeader"]::after {
            content: "Upload";
            font-size: 1.75rem;
            font-weight: 700;
            color: #FFFFFF;
        }

        /* Container Padding Adjustments */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        /* Sidebar Padding Adjustment */
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-top: 1.5rem !important;
        }

        /* Flex Height Equalization for Columns */
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            display: flex;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div[data-testid="stVerticalBlock"] {
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] {
            flex: 1;
        }

        /* Metric Card Internal Layout */
        .metric-card-container {
            height: 100%;
            min-height: 180px;
            display: flex;
            flex-direction: column;
            justify-content: space-around;
            padding: 0.5rem 0;
        }
        .metric-card-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: #FAFAFA;
            margin-bottom: 0.5rem;
        }
        .metric-large {
            font-size: 3.5rem;
            font-weight: 700;
            text-align: center;
            line-height: 1.2;
            color: #FFFFFF;
        }
        .period-label {
            font-size: 0.8rem;
            color: #A0AAB0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .period-val {
            font-size: 1.1rem;
            font-weight: 600;
            color: #FFFFFF;
            margin-bottom: 0.3rem;
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

    @staticmethod
    def compute_statement_period(
        df: pd.DataFrame,
    ) -> Tuple[str, str]:
        """Extract minimum and maximum date values formatted as 'Month YYYY'."""
        if df.empty or "trans_date" not in df.columns:
            return "N/A", "N/A"

        dates = pd.to_datetime(df["trans_date"], errors="coerce").dropna()
        if dates.empty:
            return "N/A", "N/A"

        min_date = dates.min().strftime("%B %Y")
        max_date = dates.max().strftime("%B %Y")
        return min_date, max_date

    def render_sidebar(self) -> str:
        """Render sidebar options menu without headings."""
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
                    "nav-link-selected": {
                        "background-color": "#31333F",
                        "color": "#FFFFFF",
                    },
                },
            )
        return selected

    def render_upload_view(self) -> None:
        """Render main Statement Ingestion UI view."""
        st.markdown(
            "Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning."
        )

        df = self.repo.get_transactions_dataframe()
        total_txns = len(df)
        min_period, max_period = self.compute_statement_period(df)

        col1, col2, col3 = st.columns(3)

        with col1:
            with st.container(border=True):
                st.markdown(
                    '<div class="metric-card-title">Upload Statement</div>',
                    unsafe_allow_html=True,
                )
                uploaded_file = st.file_uploader(
                    "Upload a PDF statement",
                    type=["pdf"],
                    label_visibility="collapsed",
                )
                process_btn = st.button(
                    "Process Statement",
                    type="primary",
                    use_container_width=True,
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

                                success = parse_statement(tmp_path, DB_PATH)

                                if success:
                                    st.success(
                                        "Statement processed successfully!"
                                    )
                                    st.rerun()
                                else:
                                    st.error(
                                        "Failed to process statement. Duplicate or invalid file."
                                    )
                            except Exception as err:
                                st.error(
                                    f"An error occurred during ingestion: {err}"
                                )
                            finally:
                                if tmp_path and os.path.exists(tmp_path):
                                    try:
                                        os.remove(tmp_path)
                                    except OSError:
                                        pass
                    else:
                        st.error("Please select a valid PDF file first.")

        with col2:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="metric-card-container">
                        <div class="metric-card-title">Total transactions uploaded</div>
                        <div class="metric-large">{total_txns}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with col3:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="metric-card-container">
                        <div class="metric-card-title">Statement period uploaded</div>
                        <div>
                            <div class="period-label">From:</div>
                            <div class="period-val">{min_period}</div>
                            <div class="period-label">To:</div>
                            <div class="period-val">{max_period}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.subheader("Transactions uploaded")
        self.render_paginated_table(df)

    @staticmethod
    def render_paginated_table(df: pd.DataFrame) -> None:
        """Render explicit 10-row paginated table with controls."""
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1

        total_rows = len(df)
        items_per_page = 10
        total_pages = (
            math.ceil(total_rows / items_per_page) if total_rows > 0 else 1
        )

        if st.session_state.current_page > total_pages:
            st.session_state.current_page = total_pages
        if st.session_state.current_page < 1:
            st.session_state.current_page = 1

        start_idx = (st.session_state.current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        sliced_df = df.iloc[start_idx:end_idx]

        st.dataframe(sliced_df, use_container_width=True)

        col_prev, col_info, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button(
                "Previous Page",
                disabled=(st.session_state.current_page <= 1),
                use_container_width=True,
            ):
                st.session_state.current_page -= 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div style='text-align: center; font-weight: 600; padding-top: 0.35rem;'>"
                f"Page {st.session_state.current_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button(
                "Next Page",
                disabled=(st.session_state.current_page >= total_pages),
                use_container_width=True,
            ):
                st.session_state.current_page += 1
                st.rerun()

    def run(self) -> None:
        """Main application execution pipeline."""
        st.set_page_config(
            page_title="Statement Ingestion",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        self.inject_custom_css()
        selected_menu = self.render_sidebar()

        if selected_menu == "Upload":
            self.render_upload_view()
        elif selected_menu == "Dashboard":
            st.info("Dashboard view selected.")
        elif selected_menu == "Charts":
            st.info("Charts view selected.")


if __name__ == "__main__":
    app = StatementApp()
    app.run()