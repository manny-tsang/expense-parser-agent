import os
import sqlite3
import tempfile
from typing import List, Optional, Tuple
import pandas as pd
import streamlit as st

# Attempt to import parse_statement from core engine; fall back to safe error handling if unimported
try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:

        def parse_statement(file_path: str) -> pd.DataFrame:
            """Fallback parser stub if src.pdf_parser is unavailable in path."""
            raise NotImplementedError(
                "Core parser module 'src.pdf_parser' (parse_statement) was not found."
            )


class DatabaseManager:
    """Manages SQLite database connections and CRUD operations for transactions and categories."""

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        self.db_path = db_path
        self._ensure_db_dir()
        self.init_db()

    def _ensure_db_dir(self) -> None:
        """Ensure the target database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a database connection."""
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        """Initialize required database tables if they do not exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS category (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE NOT NULL
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trans_date TEXT,
                    merchant TEXT,
                    category_name TEXT,
                    txn_amount REAL,
                    purchase_currency TEXT,
                    hkd_amount REAL,
                    fx_rate REAL
                );
                """
            )
            conn.commit()

    def get_categories(self) -> List[str]:
        """Fetch distinct categories from category table and existing transactions."""
        with self.get_connection() as conn:
            query = """
                SELECT DISTINCT category_name FROM (
                    SELECT category_name FROM category
                    UNION
                    SELECT category_name FROM transactions 
                    WHERE category_name IS NOT NULL AND category_name != ''
                ) ORDER BY category_name;
            """
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [row[0] for row in rows if row[0]]

    def save_transactions(self, df: pd.DataFrame) -> int:
        """
        Ingest transactions DataFrame into SQLite database.
        Returns the number of records inserted.
        """
        if df.empty:
            return 0

        required_cols = [
            "trans_date",
            "merchant",
            "category_name",
            "txn_amount",
            "purchase_currency",
            "hkd_amount",
            "fx_rate",
        ]

        # Ensure schema compliance
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        df_to_save = df[required_cols].copy()

        with self.get_connection() as conn:
            # Sync unique categories
            unique_cats = df_to_save["category_name"].dropna().unique()
            for cat in unique_cats:
                cat_str = str(cat).strip()
                if cat_str:
                    conn.execute(
                        "INSERT OR IGNORE INTO category (category_name) VALUES (?)",
                        (cat_str,),
                    )

            df_to_save.to_sql("transactions", conn, if_exists="append", index=False)
            conn.commit()

        return len(df_to_save)

    def get_transactions(
        self, category_filter: Optional[str] = None, search_term: Optional[str] = None
    ) -> pd.DataFrame:
        """Fetch transactions with optional filtering criteria."""
        query = """
            SELECT trans_date, merchant, category_name, txn_amount, purchase_currency, hkd_amount, fx_rate
            FROM transactions
            WHERE 1=1
        """
        params: List[str] = []

        if category_filter and category_filter != "All":
            query += " AND category_name = ?"
            params.append(category_filter)

        if search_term and search_term.strip():
            query += " AND merchant LIKE ?"
            params.append(f"%{search_term.strip()}%")

        query += " ORDER BY trans_date DESC, id DESC"

        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        return df


class StatementIngestionApp:
    """Main Streamlit Application Controller."""

    def __init__(self) -> None:
        self.db_manager = DatabaseManager()

    @staticmethod
    def _process_file(uploaded_file, db_manager: DatabaseManager) -> Tuple[bool, str]:
        """Safely saves uploaded file temporarily and processes it using parse_statement."""
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getbuffer())
                temp_file_path = tmp.name

            parsed_df = parse_statement(temp_file_path)

            if isinstance(parsed_df, list):
                parsed_df = pd.DataFrame(parsed_df)
            elif not isinstance(parsed_df, pd.DataFrame):
                return False, "Parser returned an incompatible data format."

            if parsed_df.empty:
                return False, "Statement parsed successfully, but no transactions were extracted."

            inserted_count = db_manager.save_transactions(parsed_df)
            return True, f"Successfully processed statement and ingested {inserted_count} transactions."

        except Exception as e:
            return False, f"Error processing statement: {str(e)}"
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

    def render_sidebar((self)) -> None:
        """Render side control panel for statement uploading and ingestion."""
        st.sidebar.title("Statement Ingestion")
        st.sidebar.markdown("Upload downloadable PDF credit card statements to ingest into DB.")

        uploaded_file = st.sidebar.file_uploader("Select PDF Statement", type=["pdf"])

        if st.sidebar.button("Process Statement", type="primary"):
            if uploaded_file is None:
                st.sidebar.warning("Please select a PDF statement file first.")
            else:
                with st.spinner("Processing PDF statement..."):
                    success, message = self._process_file(uploaded_file, self.db_manager)

                if success:
                    st.toast(message, icon="✅")
                    st.sidebar.success(message)
                else:
                    st.sidebar.error(message)

    @staticmethod
    def render_metrics(df: pd.DataFrame) -> None:
        """Render high-level spend metrics cards."""
        col1, col2, col3 = st.columns(3)

        if not df.empty and "txn_amount" in df.columns:
            total_spend = df["txn_amount"].fillna(0).sum()
            total_count = len(df)
            
            # Group spend by category to find top spending category
            if "category_name" in df.columns:
                cat_totals = df.groupby("category_name")["txn_amount"].sum()
                top_category = cat_totals.idxmax() if not cat_totals.empty else "N/A"
            else:
                top_category = "N/A"
        else:
            total_spend = 0.0
            total_count = 0
            top_category = "N/A"

        formatted_total_spend = f"${total_spend:,.2f}"

        with col1:
            st.metric("Total Spend (AUD)", formatted_total_spend)
        with col2:
            st.metric("Total Transaction Count", f"{total_count:,}")
        with col3:
            st.metric("Top Spending Category", str(top_category))

    def render_main_area(self) -> None:
        """Render filtering toolbar and transaction data grid."""
        st.title("Operational Expense Dashboard")
        st.caption("Real-Time Ingestion Preview & Transaction Grid")

        categories = self.db_manager.get_categories()
        category_options = ["All"] + categories

        # Filters Row
        filter_col1, filter_col2 = st.columns([1, 2])
        with filter_col1:
            selected_category = st.selectbox("Category Filter", options=category_options)
        with filter_col2:
            search_merchant = st.text_input("Search Merchant", placeholder="Type merchant name...")

        # Query updated dataset
        df = self.db_manager.get_transactions(
            category_filter=selected_category, search_term=search_merchant
        )

        # Metrics Display
        st.subheader("Summary Metrics")
        self.render_metrics(df)

        st.divider()

        # Data Grid Display
        st.subheader("Transactions")
        if df.empty:
            st.info("No transaction records found matching the current filters.")
        else:
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "trans_date": st.column_config.TextColumn("Date"),
                    "merchant": st.column_config.TextColumn("Merchant"),
                    "category_name": st.column_config.TextColumn("Category"),
                    "txn_amount": st.column_config.NumberColumn(
                        "Txn Amount", format="$%.2f"
                    ),
                    "purchase_currency": st.column_config.TextColumn("Currency"),
                    "hkd_amount": st.column_config.NumberColumn(
                        "HKD Amount", format="$%.2f"
                    ),
                    "fx_rate": st.column_config.NumberColumn(
                        "FX Rate", format="%.4f"
                    ),
                },
                hide_index=True,
            )

    def run(self) -> None:
        """Run the application layout."""
        st.set_page_config(
            page_title="Statement Ingestion & Operational Dashboard",
            page_icon="💳",
            layout="wide",
        )
        self.render_sidebar()
        self.render_main_area()


if __name__ == "__main__":
    app = StatementIngestionApp()
    app.run()