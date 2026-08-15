import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:

        def parse_statement(pdf_path: str) -> None:
            raise NotImplementedError(
                "The core parser module 'pdf_parser' is not available."
            )


class ExpenseTrackerApp:
    """Streamlit application manager for statement ingestion and viewing."""

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        """Initialize the application manager with database location.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path: Path = Path(db_path)

    def fetch_transactions(self) -> pd.DataFrame:
        """Fetch raw transaction records directly from SQLite database.

        Returns:
            pd.DataFrame: Queried transactions or empty DataFrame on failure.
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

        if not self.db_path.exists():
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
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn)
                return df
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return pd.DataFrame(columns=columns)
        except Exception as e:
            st.error(f"Error querying database: {e}")
            return pd.DataFrame(columns=columns)

    def process_pdf(self, uploaded_file: Any) -> bool:
        """Save uploaded PDF to temporary storage, trigger parser, and cleanup.

        Args:
            uploaded_file: Streamlit UploadedFile instance.

        Returns:
            bool: True if ingestion succeeded, False otherwise.
        """
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getbuffer())
                temp_path = Path(tmp.name)

            parse_statement(str(temp_path))
            return True
        except Exception as e:
            st.error(f"Failed to process statement: {e}")
            return False
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    @staticmethod
    def render_dashboard() -> None:
        """Render placeholder Dashboard screen."""
        st.title("Dashboard")
        st.info("Dashboard view is currently under construction.")

    @staticmethod
    def render_charts() -> None:
        """Render placeholder Charts screen."""
        st.title("Charts")
        st.info("Charts view is currently under construction.")

    def render_upload(self) -> None:
        """Render the Statement Upload screen and Raw Transaction Grid."""
        st.title("Upload")
        st.markdown(
            "Select PDF credit card statement to process into anonymised "
            "transactions to be stored and used for budget planning."
        )

        uploaded_file = st.file_uploader("Select PDF Statement", type=["pdf"])
        process_clicked = st.button("Process Statement", type="primary")

        if process_clicked:
            if uploaded_file is None:
                st.error("Please select a PDF statement file before processing.")
            else:
                with st.spinner("Processing statement..."):
                    success = self.process_pdf(uploaded_file)

                if success:
                    st.toast("Statement processed successfully!")
                    st.success("Statement processed successfully!")

        st.divider()
        df_transactions = self.fetch_transactions()
        st.dataframe(df_transactions, use_container_width=True)

    def run(self) -> None:
        """Execute top-level Streamlit UI application and page routing."""
        st.set_page_config(
            page_title="Personal Expense Tracker",
            layout="wide",
            initial_sidebar_state="expanded",
        )

        page_selection = st.sidebar.radio(
            "Navigation",
            options=["Dashboard", "Upload", "Charts"],
            index=1,
        )

        if page_selection == "Dashboard":
            self.render_dashboard()
        elif page_selection == "Upload":
            self.render_upload()
        elif page_selection == "Charts":
            self.render_charts()


if __name__ == "__main__":
    app = ExpenseTrackerApp()
    app.run()