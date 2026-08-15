import os
import sqlite3
import tempfile
from typing import Optional, Tuple

import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

# Import parse_statement from core parser module if available
try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:

        def parse_statement(file_path: str) -> None:
            """Fallback placeholder function when pdf_parser module is unavailable."""
            raise NotImplementedError(
                "PDF parsing module 'src.pdf_parser' is not installed or available."
            )


DB_PATH = os.path.join("db", "personal-expense-tracker.db")


class DatabaseRepository:
    """Repository handling all database queries.

    Strictly adheres to Database Ownership Contract:
    DOES NOT perform DDL operations (CREATE TABLE, ALTER TABLE, etc.).
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Establish and return a database connection."""
        return sqlite3.connect(self.db_path)

    def get_total_transactions(self) -> int:
        """Query total count of transactions stored in the database."""
        if not os.path.exists(self.db_path):
            return 0
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM "transaction"')
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return 0

    def get_statement_period(self) -> Tuple[Optional[str], Optional[str]]:
        """Query the earliest and latest transaction dates."""
        if not os.path.exists(self.db_path):
            return None, None
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT MIN(trans_date), MAX(trans_date) FROM "transaction"'
                )
                row = cursor.fetchone()
                if row and row[0] is not None and row[1] is not None:
                    return str(row[0]), str(row[1])
                return None, None
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return None, None

    def get_transactions_dataframe(self) -> pd.DataFrame:
        """Retrieve historical transactions formatted for grid view."""
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
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn)
                return df
        except (sqlite3.OperationalError, pd.errors.DatabaseError):
            return pd.DataFrame(columns=columns)


def inject_custom_css() -> None:
    """Inject custom CSS overrides for padding, margins, and card layouts."""
    css = """
    <style>
    /* Compact Viewport Padding */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    
    /* Sidebar Margin Adjustment */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem;
    }

    /* Card Content Styling */
    .card-title {
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #FAFAFA;
    }

    .metric-large {
        font-size: 3rem;
        font-weight: bold;
        line-height: 1.2;
        margin-top: 0.25rem;
        margin-bottom: 0.25rem;
    }

    .period-text {
        font-size: 1rem;
        line-height: 1.4;
        margin-top: 0.25rem;
    }

    .period-label {
        color: #A0A0A0;
    }

    .period-val {
        font-weight: 600;
        color: #FFFFFF;
        margin-bottom: 0.2rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_sidebar() -> str:
    """Render styled sidebar navigation without top titles."""
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
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "color": "#FFFFFF",
                    "--hover-color": "#262730",
                },
                "nav-link-selected": {
                    "background-color": "#31333F",
                    "color": "#FFFFFF",
                },
            },
        )
    return str(selected)


def format_date_str(date_str: Optional[str]) -> str:
    """Format raw date string into Month YYYY display format."""
    if not date_str:
        return ""
    try:
        return pd.to_datetime(date_str).strftime("%b %Y")
    except Exception:
        return str(date_str)


def render_upload_view(db_repo: DatabaseRepository) -> None:
    """Render the primary Upload screen layout with 3 uniform cards and transaction grid."""
    st.title("Upload")
    st.markdown(
        "Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning."
    )

    # 3-Column Equal Card Row
    col1, col2, col3 = st.columns(3)

    # Card 1: File Picker
    with col1:
        with st.container(border=True):
            st.markdown(
                '<div class="card-title">Upload a PDF statement</div>',
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader(
                "Upload a PDF statement",
                type=["pdf"],
                label_visibility="collapsed",
            )
            process_clicked = st.button(
                "Process Statement", type="primary", use_container_width=True
            )

    # Card 2: Total Transactions Uploaded Metric
    with col2:
        with st.container(border=True):
            st.markdown(
                '<div class="card-title">Total transactions uploaded</div>',
                unsafe_allow_html=True,
            )
            total_txns = db_repo.get_total_transactions()
            st.markdown(
                f'<div class="metric-large">{total_txns}</div>',
                unsafe_allow_html=True,
            )

    # Card 3: Statement Period Uploaded
    with col3:
        with st.container(border=True):
            st.markdown(
                '<div class="card-title">Statement period uploaded</div>',
                unsafe_allow_html=True,
            )
            min_date, max_date = db_repo.get_statement_period()
            if min_date and max_date:
                min_fmt = format_date_str(min_date)
                max_fmt = format_date_str(max_date)
                period_html = f"""
                <div class="period-text">
                    <div class="period-label">From:</div>
                    <div class="period-val">{min_fmt}</div>
                    <div class="period-label">To:</div>
                    <div class="period-val">{max_fmt}</div>
                </div>
                """
                st.markdown(period_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="period-text" style="color: #888888;">No statements uploaded</div>',
                    unsafe_allow_html=True,
                )

    # Processing Action
    if process_clicked:
        if uploaded_file is None:
            st.error("Please select a PDF file before processing.")
        else:
            temp_file_path = None
            try:
                with st.spinner("Processing statement..."):
                    # Save uploaded file to temp path
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf"
                    ) as temp_file:
                        temp_file.write(uploaded_file.getvalue())
                        temp_file_path = temp_file.name

                    # Execute PDF parser
                    parse_statement(temp_file_path)

                st.success("Statement processed successfully!")
                st.rerun()
            except Exception as err:
                st.error(f"Error processing statement: {str(err)}")
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

    st.markdown("---")

    # Grid Section Header & Paginated Dataframe
    st.subheader("Transactions uploaded")
    df_txns = db_repo.get_transactions_dataframe()

    # Fitted precisely for 10 rows view (~390px height)
    st.dataframe(
        df_txns,
        height=390,
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    """Application entry point."""
    st.set_page_config(
        page_title="Statement Ingestion & Operational Dashboard",
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_custom_css()
    active_page = render_sidebar()

    db_repo = DatabaseRepository()

    if active_page == "Upload":
        render_upload_view(db_repo)
    elif active_page == "Dashboard":
        st.title("Dashboard")
        st.info("Dashboard overview is under construction.")
    elif active_page == "Charts":
        st.title("Charts")
        st.info("Analytics and charts are under construction.")


if __name__ == "__main__":
    main()