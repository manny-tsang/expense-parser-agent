import math
import os
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
        parse_statement = None


class DatabaseRepository:
    """Repository class for querying transaction and statement data."""

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        self.db_path = db_path

    def get_transactions_dataframe(self) -> pd.DataFrame:
        """
        Queries raw transactions from the normalized database schema.
        
        Returns:
            pd.DataFrame: Transactions dataset.
        """
        columns = [
            "trans_date",
            "merchant",
            "category_name",
            "txn_amount",
            "purchase_currency",
            "hkd_amount",
            "fx_rate",
        ]

        if not os.path.exists(self.db_path):
            return pd.DataFrame(columns=columns)

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
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return pd.DataFrame(columns=columns)

    def has_statements(self) -> bool:
        """
        Checks if statement logs exist in the database.
        
        Returns:
            bool: True if statement records exist, False otherwise.
        """
        if not os.path.exists(self.db_path):
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM statement_log")
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return False


class UIApp:
    """Main Streamlit Operational Dashboard Application."""

    def __init__(self) -> None:
        self.repo = DatabaseRepository()

    @staticmethod
    def inject_custom_css() -> None:
        """Injects custom CSS for padding alignment, card heights, and typography."""
        css = """
        <style>
        /* Top Margin Alignment */
        [data-testid="stSidebarContent"] {
            padding-top: 1.5rem !important;
        }

        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        /* Uniform Card Dimensions */
        [data-testid="stVerticalBlockBorderWrapper"] {
            min-height: 240px !important;
        }

        .metric-card-container {
            min-height: 240px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 0.5rem;
        }

        /* Scaled Typography Rules */
        .metric-large {
            font-size: 5rem !important;
            font-weight: 800 !important;
            line-height: 1 !important;
            color: #FFFFFF !important;
            margin-top: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }

        .period-label {
            color: #A0A0A0 !important;
            font-size: 1.1rem !important;
            font-weight: 500 !important;
        }

        .period-val {
            font-weight: 700 !important;
            font-size: 1.35rem !important;
            color: #FFFFFF !important;
            margin-bottom: 0.4rem !important;
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

    def render_sidebar(self) -> str:
        """
        Renders sidebar navigation using streamlit_option_menu.
        
        Returns:
            str: Selected navigation menu item.
        """
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
                    "icon": {"color": "#FFFFFF", "font-size": "16px"},
                    "nav-link": {
                        "color": "#FFFFFF",
                        "font-size": "16px",
                        "text-align": "left",
                        "margin": "0px",
                        "padding": "10px",
                    },
                    "nav-link-selected": {
                        "background-color": "#31333F",
                        "color": "#FFFFFF",
                        "font-weight": "600",
                    },
                },
            )
        return selected

    def handle_file_upload(self, uploaded_file) -> None:
        """Processes the uploaded PDF statement through the PDF parser engine."""
        if uploaded_file is None:
            st.error("Please select a PDF statement file to process.")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            with st.spinner("Processing statement..."):
                if parse_statement is not None:
                    try:
                        parse_statement(tmp_path)
                    except TypeError:
                        parse_statement(tmp_path, self.repo.db_path)
                else:
                    st.error("Core Engine `src/pdf_parser.py` is not available.")
                    return
            st.success("Statement processed successfully!")
        except Exception as err:
            st.error(f"Failed to process statement: {str(err)}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def render_upload_view(self) -> None:
        """Renders the Upload view with 3-column metric cards and paginated transaction table."""
        st.title("Upload")
        st.markdown(
            "Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning."
        )

        df = self.repo.get_transactions_dataframe()
        has_logs = self.repo.has_statements()
        total_txns = len(df)

        col1, col2, col3 = st.columns(3)

        # Card 1: File Picker
        with col1:
            with st.container(border=True):
                st.markdown(
                    "<div style='font-size: 1rem; font-weight: 500; margin-bottom: 0.5rem;'>Upload a PDF statement</div>",
                    unsafe_allow_html=True,
                )
                uploaded_file = st.file_uploader(
                    "Upload a PDF statement",
                    type=["pdf"],
                    label_visibility="collapsed",
                    key="pdf_uploader",
                )
                process_btn = st.button(
                    "Process Statement", type="primary", use_container_width=True
                )
                if process_btn:
                    self.handle_file_upload(uploaded_file)
                    st.rerun()

        # Card 2: Total Transactions Uploaded
        with col2:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="metric-card-container">
                        <div style="font-size: 1.1rem; font-weight: 500; color: #A0A0A0;">Total transactions uploaded</div>
                        <div class="metric-large">{total_txns}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Card 3: Statement Period Uploaded
        with col3:
            with st.container(border=True):
                if not has_logs or df.empty or "trans_date" not in df.columns:
                    st.markdown(
                        """
                        <div class="metric-card-container">
                            <div style="font-size: 1.1rem; font-weight: 500; color: #A0A0A0; margin-bottom: 0.5rem;">Statement period uploaded</div>
                            <div style="font-size: 1.2rem; color: #FFFFFF; font-weight: 600;">No statements uploaded</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    min_date = df["trans_date"].min()
                    max_date = df["trans_date"].max()
                    st.markdown(
                        f"""
                        <div class="metric-card-container">
                            <div style="font-size: 1.1rem; font-weight: 500; color: #A0A0A0; margin-bottom: 0.5rem;">Statement period uploaded</div>
                            <div>
                                <span class="period-label">From: </span><span class="period-val">{min_date}</span>
                            </div>
                            <div>
                                <span class="period-label">To: </span><span class="period-val">{max_date}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Transactions uploaded")

        # Explicit 10-Row Table Pagination Logic
        items_per_page = 10
        total_rows = len(df)
        total_pages = math.ceil(total_rows / items_per_page) if total_rows > 0 else 1

        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 1

        if st.session_state["current_page"] > total_pages:
            st.session_state["current_page"] = total_pages
        if st.session_state["current_page"] < 1:
            st.session_state["current_page"] = 1

        current_page = st.session_state["current_page"]
        start_idx = (current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        sliced_df = df.iloc[start_idx:end_idx]

        st.dataframe(sliced_df, use_container_width=True)

        col_prev, col_info, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button(
                "Previous Page",
                disabled=(current_page <= 1),
                use_container_width=True,
                key="btn_prev",
            ):
                st.session_state["current_page"] -= 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div style='text-align: center; padding-top: 0.4rem; font-weight: 600; font-size: 1rem;'>Page {current_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button(
                "Next Page",
                disabled=(current_page >= total_pages),
                use_container_width=True,
                key="btn_next",
            ):
                st.session_state["current_page"] += 1
                st.rerun()

    def run(self) -> None:
        """Main execution entry point for the Streamlit application."""
        st.set_page_config(
            page_title="Personal Expense Tracker",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        self.inject_custom_css()
        selected_page = self.render_sidebar()

        if selected_page == "Upload":
            self.render_upload_view()
        elif selected_page == "Dashboard":
            st.title("Dashboard")
            st.info("Dashboard module under construction.")
        elif selected_page == "Charts":
            st.title("Charts")
            st.info("Charts module under construction.")


if __name__ == "__main__":
    app = UIApp()
    app.run()