import os
import re
import sqlite3
import tempfile
from datetime import datetime
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
        def parse_statement(file_path: str, db_path: str) -> None:
            """Fallback mock if pdf_parser is unavailable."""
            raise NotImplementedError("The pdf_parser module is not installed or accessible.")


DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "db", "personal-expense-tracker.db")
)


class DatabaseRepository:
    """Handles read operations for application analytics and transactions.
    
    Database table creation and schema management are strictly handled by pdf_parser.py.
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return sqlite3.connect(self.db_path)

    def get_total_transaction_count(self) -> int:
        """Fetches total count of stored transactions."""
        query = 'SELECT COUNT(*) FROM "transaction"'
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                row = cursor.fetchone()
                return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0

    def get_statement_period(self) -> Tuple[Optional[str], Optional[str]]:
        """Retrieves min and max transaction dates formatted as string."""
        log_query = 'SELECT filename FROM statement_log'
        txn_query = 'SELECT MIN(trans_date), MAX(trans_date) FROM "transaction"'
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(log_query)
                log_rows = cursor.fetchall()
                if not log_rows:
                    return None, None

                cursor.execute(txn_query)
                min_date_str, max_date_str = cursor.fetchone()
                if not min_date_str or not max_date_str:
                    return None, None

                min_dt = datetime.strptime(str(min_date_str)[:10], "%Y-%m-%d")
                max_dt = datetime.strptime(str(max_date_str)[:10], "%Y-%m-%d")
                return min_dt.strftime("%b %Y"), max_dt.strftime("%b %Y")
        except (sqlite3.OperationalError, ValueError):
            return None, None

    def get_transactions_dataframe() -> pd.DataFrame:
        """Queries normalized transaction records for display grid."""
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
        except sqlite3.OperationalError:
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
    """Main Streamlit Operational Dashboard Application."""

    def __init__(self) -> None:
        self.db_repo = DatabaseRepository()

    @staticmethod
    def configure_page() -> None:
        """Configures Streamlit page metadata and custom layout settings."""
        st.set_page_config(
            page_title="Statement Ingestion & Operational Dashboard",
            page_icon="💳",
            layout="wide",
            initial_sidebar_state="expanded",
        )

    def render_sidebar(self) -> str:
        """Renders styled sidebar navigation option menu without headers."""
        with st.sidebar:
            selected_menu = option_menu(
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
                        "font-size": "14px",
                        "text-align": "left",
                        "margin": "0px",
                        "--hover-color": "#31333F",
                    },
                    "nav-link-selected": {
                        "background-color": "#31333F",
                        "color": "#FFFFFF",
                    },
                },
            )
        return str(selected_menu)

    def _process_file_upload(self, uploaded_file: Any) -> None:
        """Saves file to temporary storage, parses contents, and clears memory."""
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                temp_file_path = tmp.name

            with st.spinner("Processing statement..."):
                parse_statement(temp_file_path, DB_PATH)
            st.success("Statement processed successfully!")
        except Exception as err:
            st.error(f"Failed to process statement: {str(err)}")
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def render_upload_view(self) -> None:
        """Renders the primary statement upload view and transaction summary UI."""
        st.title("Upload")
        st.markdown(
            "Upload a PDF statement to process into anonymised transactions to be "
            "stored and used for budget planning."
        )

        col1, col2, col3 = st.columns(3)

        # Card 1: File Picker & Processing
        with col1:
            with st.container(border=True):
                st.markdown("**Upload a PDF statement**")
                uploaded_file = st.file_uploader(
                    label="Upload a PDF statement",
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
                        self._process_file_upload(uploaded_file)
                    else:
                        st.warning("Please select a PDF file first.")

        # Card 2: Total Transactions Metric
        with col2:
            with st.container(border=True):
                st.markdown("**Total transactions uploaded**")
                total_txns = self.db_repo.get_total_transaction_count()
                st.markdown(
                    f"<h1 style='text-align: center; font-size: 3rem; margin: 10px 0;'>{total_txns}</h1>",
                    unsafe_allow_html=True,
                )

        # Card 3: Uploaded Statement Period
        with col3:
            with st.container(border=True):
                st.markdown("**Uploaded statement period**")
                min_month, max_month = self.db_repo.get_statement_period()
                if min_month and max_month:
                    period_str = f"**From:**<br>{min_month}<br>**To:**<br>{max_month}"
                    st.markdown(
                        f"<div style='margin-top: 5px; line-height: 1.4;'>{period_str}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='margin-top: 15px; color: #888888;'>No statements uploaded</div>",
                        unsafe_allow_html=True,
                    )

        st.write("")
        st.subheader("Transactions uploaded")

        df = self.db_repo.get_transactions_dataframe()
        st.dataframe(
            df,
            use_container_width=True,
            height=390,
            hide_index=True,
            column_config={
                "trans_date": st.column_config.TextColumn("Transaction Date"),
                "merchant": st.column_config.TextColumn("Merchant"),
                "category_name": st.column_config.TextColumn("Category"),
                "txn_amount": st.column_config.NumberColumn("Txn Amount", format="%.2f"),
                "purchase_currency": st.column_config.TextColumn("Currency"),
                "hkd_amount": st.column_config.NumberColumn("HKD Amount", format="%.2f"),
                "fx_rate": st.column_config.NumberColumn("FX Rate", format="%.4f"),
            },
        )

    @staticmethod
    def render_dashboard_view() -> None:
        """Placeholder for Dashboard menu page."""
        st.title("Dashboard")
        st.info("Dashboard visualizations and summary metrics coming soon.")

    @staticmethod
    def render_charts_view() -> None:
        """Placeholder for Charts menu page."""
        st.title("Charts")
        st.info("Analytics charts and expense breakdowns coming soon.")

    def run(self) -> None:
        """Executes main application routing logic."""
        self.configure_page()
        selected_menu = self.render_sidebar()

        if selected_menu == "Dashboard":
            self.render_dashboard_view()
        elif selected_menu == "Upload":
            self.render_upload_view()
        elif selected_menu == "Charts":
            self.render_charts_view()


if __name__ == "__main__":
    app = StatementApp()
    app.run()