import inspect
import os
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

# Import PDF parser core engine
try:
    from src.pdf_parser import parse_statement
except ImportError:
    try:
        from pdf_parser import parse_statement
    except ImportError:
        parse_statement = None


class DatabaseManager:
    """Handles SQLite database read operations adhering to the ownership contract."""

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes SQLite connection ensuring parent directory structure exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path))

    def get_total_transactions(self) -> int:
        """Queries the total count of parsed transactions."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM "transaction"')
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0
        except Exception:
            return 0

    def get_statements_date_range(self) -> str:
        """
        Queries statement logs and transactions to determine the minimum and
        maximum dates, formatted as 'From Month YYYY to Month YYYY'.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT filename FROM statement_log")
                statement_rows = cursor.fetchall()

                if not statement_rows:
                    return "No statements uploaded"

                cursor.execute(
                    'SELECT MIN(trans_date), MAX(trans_date) FROM "transaction"'
                )
                date_row = cursor.fetchone()

                if date_row and date_row[0] and date_row[1]:
                    min_dt = self._parse_date_string(str(date_row[0]))
                    max_dt = self._parse_date_string(str(date_row[1]))

                    if min_dt and max_dt:
                        min_str = min_dt.strftime("%B %Y")
                        max_str = max_dt.strftime("%B %Y")
                        if min_str == max_str:
                            return f"From {min_str}"
                        return f"From {min_str} to {max_str}"

                return f"{len(statement_rows)} statement(s) uploaded"
        except sqlite3.OperationalError:
            return "No statements uploaded"
        except Exception:
            return "No statements uploaded"

    @staticmethod
    def _parse_date_string(date_str: str) -> Optional[datetime]:
        """Helper to parse raw date string variants into a datetime object."""
        if not date_str:
            return None
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
        ]
        cleaned_str = str(date_str).strip()
        for fmt in formats:
            try:
                return datetime.strptime(cleaned_str, fmt)
            except ValueError:
                continue

        # Regex fallback for embedded dates
        match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", cleaned_str)
        if match:
            try:
                return datetime(
                    int(match.group(1)), int(match.group(2)), int(match.group(3))
                )
            except ValueError:
                pass
        return None

    def get_transactions_dataframe(self) -> pd.DataFrame:
        """Queries normalized raw transactions joined with category and currency schemas."""
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
        expected_columns = [
            "trans_date",
            "merchant",
            "category_name",
            "txn_amount",
            "purchase_currency",
            "hkd_amount",
            "fx_rate",
        ]
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn)
                return df
        except sqlite3.OperationalError:
            return pd.DataFrame(columns=expected_columns)
        except Exception:
            return pd.DataFrame(columns=expected_columns)


class StatementProcessor:
    """Handles temp file management and statement ingestion execution."""

    @staticmethod
    def process_upload(file_buffer: bytes, db_path: str) -> Tuple[bool, str]:
        """
        Saves buffer to a temp file, invokes parse_statement, and cleans up temp resources.
        """
        if parse_statement is None:
            return False, "PDF parser engine module (`src.pdf_parser`) is unavailable."

        tmp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_buffer)
                tmp_file_path = tmp_file.name

            sig = inspect.signature(parse_statement)
            params = sig.parameters

            if len(params) >= 2:
                res = parse_statement(tmp_file_path, db_path)
            else:
                res = parse_statement(tmp_file_path)

            if isinstance(res, tuple) and len(res) >= 2:
                status, msg = res[0], res[1]
                return bool(status), str(msg)
            elif isinstance(res, bool):
                if res:
                    return True, "Statement processed successfully!"
                return False, "Failed to parse statement or duplicate record."
            
            return True, "Statement processed successfully!"

        except Exception as exc:
            return False, str(exc)
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except OSError:
                    pass


def render_sidebar_navigation() -> str:
    """Renders options menu in sidebar strictly without headings or titles."""
    with st.sidebar:
        selected = option_menu(
            menu_title=None,
            options=["Dashboard", "Upload", "Charts"],
            icons=["house", "cloud-upload", "bar-chart"],
            default_index=1,
            styles={
                "container": {"padding": "0!important", "background-color": "#fafafa"},
                "icon": {"color": "#02ab21", "font-size": "18px"},
                "nav-link": {
                    "font-size": "15px",
                    "text-align": "left",
                    "margin": "0px",
                    "--hover-color": "#eee",
                },
                "nav-link-selected": {"background-color": "#02ab21"},
            },
        )
    return str(selected)


def render_upload_view(db_mgr: DatabaseManager) -> None:
    """Renders 3-column rounded card layout and transaction grid on Upload screen."""
    st.title("Upload")
    st.markdown(
        "Select PDF credit card statement to process into anonymised transactions "
        "to be stored and used for budget planning."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### Statement Selection")
            uploaded_file = st.file_uploader(
                "Select PDF Statement", type=["pdf"], label_visibility="visible"
            )
            process_btn = st.button(
                "Process Statement", type="primary", use_container_width=True
            )

    with col2:
        with st.container(border=True):
            total_txns = db_mgr.get_total_transactions()
            st.metric(
                label="Total transactions uploaded",
                value=f"{total_txns:,}",
            )

    with col3:
        with st.container(border=True):
            date_range_str = db_mgr.get_statements_date_range()
            st.metric(
                label="Statements uploaded",
                value=date_range_str,
            )

    if process_btn:
        if uploaded_file is None:
            st.warning("Please select a PDF statement file before processing.")
        else:
            with st.spinner("Processing statement..."):
                file_bytes = uploaded_file.getvalue()
                success, message = StatementProcessor.process_upload(
                    file_bytes, str(db_mgr.db_path)
                )

            if success:
                st.success("Statement processed successfully!")
                st.rerun()
            else:
                st.error(f"Processing Error: {message}")

    st.markdown("---")
    render_transaction_grid(db_mgr)


def render_transaction_grid(db_mgr: DatabaseManager) -> None:
    """Renders a paginated, 10-row maximum raw transaction preview grid."""
    st.subheader("Raw Transaction Grid")
    df = db_mgr.get_transactions_dataframe()

    if df.empty:
        st.info("No transaction records found in database. Ingest a PDF statement to display rows.")
        return

    items_per_page = 10
    total_rows = len(df)
    total_pages = max(1, (total_rows + items_per_page - 1) // items_per_page)

    if "current_page" not in st.session_state:
        st.session_state.current_page = 1

    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages
    if st.session_state.current_page < 1:
        st.session_state.current_page = 1

    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = df.iloc[start_idx:end_idx]

    st.dataframe(
        page_df,
        use_container_width=True,
        height=390,
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

    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.button(
            "Previous",
            disabled=(st.session_state.current_page <= 1),
            use_container_width=True,
            key="btn_prev_page",
        ):
            st.session_state.current_page -= 1
            st.rerun()

    with col_info:
        st.markdown(
            f"<div style='text-align: center; font-weight: 500; padding-top: 6px;'>"
            f"Page {st.session_state.current_page} of {total_pages} ({total_rows} total rows)"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.button(
            "Next",
            disabled=(st.session_state.current_page >= total_pages),
            use_container_width=True,
            key="btn_next_page",
        ):
            st.session_state.current_page += 1
            st.rerun()


def main() -> None:
    """Application entry point handling page routing and layout setup."""
    st.set_page_config(
        page_title="Personal Expense Tracker - Statement Ingestion",
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    db_mgr = DatabaseManager("db/personal-expense-tracker.db")
    selected_page = render_sidebar_navigation()

    if selected_page == "Upload":
        render_upload_view(db_mgr)
    elif selected_page == "Dashboard":
        st.title("Dashboard")
        st.info("Dashboard operational view is under development.")
    elif selected_page == "Charts":
        st.title("Charts")
        st.info("Analytics and charts view is under development.")


if __name__ == "__main__":
    main()