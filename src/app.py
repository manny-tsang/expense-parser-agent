import os
import re
import sqlite3
import tempfile
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

# Attempt import of parse_statement from src.pdf_parser or fallback
try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:
        parse_statement = None


class DatabaseService:
    """Handles read-only queries against the personal expense database."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes SQLite database connection."""
        return sqlite3.connect(self.db_path)

    def is_statement_ingested(self, filename: str) -> bool:
        """Checks if a statement filename exists in statement_log table."""
        if not os.path.exists(self.db_path):
            return False

        query = 'SELECT 1 FROM statement_log WHERE filename = ? LIMIT 1'
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (filename,))
                return cursor.fetchone() is not None
        except sqlite3.OperationalError:
            # Table statement_log may not exist yet
            return False

    def get_total_transactions_count(self) -> int:
        """Queries total count of transactions ingested."""
        if not os.path.exists(self.db_path):
            return 0

        query = 'SELECT COUNT(*) FROM "transaction"'
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                row = cursor.fetchone()
                return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0

    def get_statement_date_range(self) -> str:
        """
        Queries statement_log, parses filenames (e.g. YYYY-MM-DD_Statement.pdf)
        and computes formatted date range string.
        """
        if not os.path.exists(self.db_path):
            return "No statements uploaded"

        query = "SELECT filename FROM statement_log"
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn)
        except sqlite3.OperationalError:
            return "No statements uploaded"

        if df.empty or "filename" not in df.columns:
            return "No statements uploaded"

        dates: List[datetime] = []
        date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")

        for fname in df["filename"].dropna():
            match = date_pattern.search(str(fname))
            if match:
                try:
                    dt = datetime.strptime(match.group(1), "%Y-%m-%d")
                    dates.append(dt)
                except ValueError:
                    continue

        if not dates:
            return "No statements uploaded"

        min_date = min(dates)
        max_date = max(dates)

        start_str = min_date.strftime("%B %Y")
        end_str = max_date.strftime("%B %Y")

        return f"From {start_str} to {end_str}"

    def get_raw_transactions(self) -> pd.DataFrame:
        """Queries normalized raw transactions with category and currency joins."""
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
                return pd.read_sql_query(query, conn)
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


class AppUI:
    """Streamlit Application UI controller."""

    DB_PATH = os.path.join("db", "personal-expense-tracker.db")

    def __init__(self) -> None:
        self.db_service = DatabaseService(self.DB_PATH)

    @staticmethod
    def init_session_state() -> None:
        """Initializes Streamlit session state navigation defaults."""
        if "active_page" not in st.session_state:
            st.session_state["active_page"] = "Upload"

    def render_sidebar(self) -> None:
        """Renders single-word physical action button navigation."""
        st.sidebar.title("Navigation")

        if st.sidebar.button("Dashboard", use_container_width=True):
            st.session_state["active_page"] = "Dashboard"

        if st.sidebar.button("Upload", use_container_width=True):
            st.session_state["active_page"] = "Upload"

        if st.sidebar.button("Charts", use_container_width=True):
            st.session_state["active_page"] = "Charts"

    def render_dashboard(self) -> None:
        """Placeholder view for Dashboard."""
        st.title("Dashboard")
        st.info(
            "Dashboard overview, category averages, and statement analysis coming soon."
        )

    def render_charts(self) -> None:
        """Placeholder view for Interactive Charts."""
        st.title("Charts")
        st.info("Interactive charts and budget filtering coming soon.")

    def render_upload(self) -> None:
        """Renders main Upload screen, metrics, and raw transactions grid."""
        st.title("Upload")
        st.markdown(
            "Select PDF credit card statement to process into anonymised "
            "transactions to be stored and used for budget planning."
        )

        uploaded_file = st.file_uploader("Select PDF Statement", type=["pdf"])
        process_clicked = st.button("Process Statement", type="primary")

        if process_clicked:
            if uploaded_file is None:
                st.error("Please select a PDF file before processing.")
            else:
                self._handle_file_processing(uploaded_file)

        # Metrics cards section
        total_txns = self.db_service.get_total_transactions_count()
        date_range_str = self.db_service.get_statement_date_range()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Transactions Uploaded", total_txns)
        with col2:
            st.metric("Statements Uploaded Date Range", date_range_str)

        st.subheader("Raw Transactions Preview")
        df_transactions = self.db_service.get_raw_transactions()
        st.dataframe(df_transactions, height=500, use_container_width=True)

    def _handle_file_processing(self, uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> None:
        """Validates duplicate state, invokes parser, and provides execution feedback."""
        filename = uploaded_file.name

        # Scenario 2: Duplicate Statement Prevention
        if self.db_service.is_statement_ingested(filename):
            st.error(
                f"Duplicate File Error: Statement '{filename}' has already been processed previously."
            )
            return

        if parse_statement is None:
            st.error("Parser module `src.pdf_parser.parse_statement` is missing or unavailable.")
            return

        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, filename)

        try:
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with st.spinner("Processing statement..."):
                try:
                    parse_statement(temp_file_path)
                    st.success("Statement processed successfully!")
                except Exception as e:
                    st.error(f"Failed to process statement: {str(e)}")

        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    def run(self) -> None:
        """Main application execution pipeline."""
        st.set_page_config(
            page_title="Personal Expense Tracker",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        self.init_session_state()
        self.render_sidebar()

        active_page = st.session_state.get("active_page", "Upload")

        if active_page == "Dashboard":
            self.render_dashboard()
        elif active_page == "Charts":
            self.render_charts()
        else:
            self.render_upload()


if __name__ == "__main__":
    app = AppUI()
    app.run()