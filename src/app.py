import os
import sqlite3
import tempfile
import uuid
from typing import Any, List, Optional, Tuple

import pandas as pd
import streamlit as st

try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:
        parse_statement = None


class DatabaseManager:
    """Manages read-only queries against the normalized SQLite database."""

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Establishes and returns a database connection with Row factory."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_categories(self) -> List[str]:
        """Fetches distinct category names ordered alphabetically."""
        if not os.path.exists(self.db_path):
            return []
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT category_name FROM category ORDER BY category_name")
                rows = cursor.fetchall()
                return [row["category_name"] for row in rows if row["category_name"]]
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return []

    def fetch_transactions(
        self, category_filter: Optional[str] = None, search_term: Optional[str] = None
    ) -> pd.DataFrame:
        """Queries normalized transaction records with optional filters."""
        default_cols = [
            "trans_date",
            "merchant",
            "category_name",
            "txn_amount",
            "purchase_currency",
            "hkd_amount",
            "fx_rate",
        ]
        if not os.path.exists(self.db_path):
            return pd.DataFrame(columns=default_cols)

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
            WHERE 1=1
        """
        params: List[Any] = []

        if category_filter and category_filter != "All":
            query += " AND c.category_name = ?"
            params.append(category_filter)

        if search_term and search_term.strip():
            query += " AND t.merchant LIKE ?"
            params.append(f"%{search_term.strip()}%")

        query += " ORDER BY t.trans_date DESC"

        try:
            with self.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params)
                return df
        except (sqlite3.OperationalError, pd.errors.DatabaseError):
            return pd.DataFrame(columns=default_cols)


class DashboardMetrics:
    """Computes summary metrics from transaction datasets."""

    @staticmethod
    def calculate_metrics(df: pd.DataFrame) -> Tuple[str, int, str]:
        """Calculates total spend, transaction count, and top spending category."""
        if df.empty:
            return "$0.00", 0, "N/A"

        amount_col = "txn_amount" if "txn_amount" in df.columns else None
        if amount_col and not df[amount_col].dropna().empty:
            total_spend = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0).sum()
        else:
            total_spend = 0.0

        total_count = len(df)

        top_category = "N/A"
        if "category_name" in df.columns and not df["category_name"].dropna().empty:
            valid_cats = df.dropna(subset=["category_name"])
            if not valid_cats.empty:
                if amount_col:
                    grouped = valid_cats.groupby("category_name")[amount_col].sum()
                else:
                    grouped = valid_cats["category_name"].value_counts()
                if not grouped.empty:
                    top_category = str(grouped.idxmax())

        formatted_spend = f"${total_spend:,.2f}"
        return formatted_spend, total_count, top_category


class StatementProcessor:
    """Handles PDF file uploading, temporary file handling, and parser execution."""

    @staticmethod
    def process_pdf(uploaded_file: Any) -> Tuple[bool, str]:
        """Saves uploaded PDF to a temporary file and triggers parse_statement."""
        if parse_statement is None:
            return False, "PDF Parser engine (`src/pdf_parser.py`) is missing or unavailable."

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"temp_{uuid.uuid4().hex}_{uploaded_file.name}")

        try:
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            parse_statement(temp_path)
            return True, "Statement processed and ingested successfully!"
        except Exception as e:
            return False, f"Failed to process statement: {str(e)}"
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


def main() -> None:
    st.set_page_config(
        page_title="Statement Ingestion & Operational Dashboard",
        page_icon="💳",
        layout="wide",
    )

    st.title("💳 Statement Ingestion & Operational Dashboard")
    st.markdown("Upload credit card statements, ingest transactions into SQLite, and monitor spending.")

    db_manager = DatabaseManager()

    # Sidebar: Statement Ingestion
    st.sidebar.header("Statement Ingestion")
    uploaded_file = st.sidebar.file_uploader(
        "Select PDF Statement",
        type=["pdf"],
        help="Upload downloadable credit card statements in PDF format.",
    )

    process_btn = st.sidebar.button("Process Statement", use_container_width=True, type="primary")

    if process_btn:
        if uploaded_file is None:
            st.sidebar.warning("Please select a PDF file before clicking process.")
        else:
            with st.spinner("Processing PDF statement..."):
                success, message = StatementProcessor.process_pdf(uploaded_file)
            if success:
                st.sidebar.success(message)
                st.toast("Ingestion completed successfully!", icon="✅")
                st.rerun()
            else:
                st.sidebar.error(message)
                st.toast(f"Processing Error: {message}", icon="🚨")

    # Main Area: Filters
    st.subheader("Filters & Search")
    category_list = ["All"] + db_manager.fetch_categories()

    col_filter1, col_filter2 = st.columns([1, 2])
    with col_filter1:
        selected_category = st.selectbox("Category Filter", options=category_list, index=0)
    with col_filter2:
        search_merchant = st.text_input(
            "Search Merchant",
            placeholder="Type merchant name...",
        )

    # Main Area: Query Data & Summary Metrics Cards
    df_transactions = db_manager.fetch_transactions(
        category_filter=selected_category, search_term=search_merchant
    )

    formatted_spend, total_count, top_category = DashboardMetrics.calculate_metrics(df_transactions)

    st.subheader("Summary Metrics")
    m1, m2, m3 = st.columns(3)
    m1.metric(label="Total Spend", value=formatted_spend)
    m2.metric(label="Total Transaction Count", value=str(total_count))
    m3.metric(label="Top Spending Category", value=top_category)

    st.divider()

    # Main Area: Real-Time Transaction Grid
    st.subheader("Transaction Records")
    if not df_transactions.empty:
        st.dataframe(
            df_transactions,
            use_container_width=True,
            column_config={
                "trans_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "merchant": st.column_config.TextColumn("Merchant"),
                "category_name": st.column_config.TextColumn("Category"),
                "txn_amount": st.column_config.NumberColumn("Txn Amount", format="$%.2f"),
                "purchase_currency": st.column_config.TextColumn("Currency"),
                "hkd_amount": st.column_config.NumberColumn("HKD Amount", format="$%.2f"),
                "fx_rate": st.column_config.NumberColumn("FX Rate", format="%.4f"),
            },
            hide_index=True,
        )
    else:
        st.info("No transaction records found. Upload a statement to populate data.")


if __name__ == "__main__":
    main()