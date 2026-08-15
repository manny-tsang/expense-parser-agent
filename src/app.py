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

        def parse_statement(file_path: str) -> bool:
            return False


class DatabaseRepository:
    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        self.db_path = db_path

    def get_connection(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.db_path):
            return None
        try:
            return sqlite3.connect(self.db_path)
        except sqlite3.Error:
            return None

    def get_transactions_dataframe(self) -> pd.DataFrame:
        conn = self.get_connection()
        if conn is None:
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
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception:
            conn.close()
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

    def get_upload_metrics(self) -> Tuple[int, Optional[str], Optional[str], bool]:
        conn = self.get_connection()
        if conn is None:
            return 0, None, None, False

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM statement_log")
            log_count = cursor.fetchone()[0]
            if log_count == 0:
                conn.close()
                return 0, None, None, False

            cursor.execute('SELECT COUNT(*) FROM "transaction"')
            total_txns = cursor.fetchone()[0]

            cursor.execute(
                'SELECT MIN(trans_date), MAX(trans_date) FROM "transaction"'
            )
            min_date_raw, max_date_raw = cursor.fetchone()

            conn.close()
            return total_txns, min_date_raw, max_date_raw, True
        except Exception:
            if conn:
                conn.close()
            return 0, None, None, False


class StatementIngestionApp:
    def __init__(self) -> None:
        self.db_repo = DatabaseRepository()

    @staticmethod
    def inject_custom_css() -> None:
        st.markdown(
            """
            <style>
            [data-testid="stSidebarHeader"] {
                display: none;
            }
            [data-testid="stSidebarContent"] {
                padding-top: 0rem !important;
                margin-top: 0.5rem !important;
            }
            .block-container {
                padding-top: 1.5rem !important;
                padding-bottom: 1rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
            }
            div[data-testid="stColumn"] > div {
                height: 100%;
            }
            .metric-card-container {
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                height: 100%;
            }
            .metric-large {
                font-size: 3.5rem !important;
                font-weight: 800 !important;
                line-height: 1 !important;
                color: #FFFFFF !important;
                margin-top: 0.25rem !important;
                margin-bottom: 0.25rem !important;
            }
            .period-label {
                color: #A0A0A0 !important;
                font-size: 1rem !important;
                font-weight: 500 !important;
            }
            .period-val {
                font-weight: 700 !important;
                font-size: 1.25rem !important;
                color: #FFFFFF !important;
                margin-bottom: 0.4rem !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def format_date_str(date_str: Optional[str]) -> str:
        if not date_str:
            return "N/A"
        try:
            dt = pd.to_datetime(date_str)
            return dt.strftime("%B %Y")
        except Exception:
            return str(date_str)

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
                    "icon": {"color": "#FFFFFF", "font-size": "16px"},
                    "nav-link": {
                        "font-size": "14px",
                        "text-align": "left",
                        "margin": "0px",
                        "color": "#FFFFFF",
                        "--hover-color": "#31333F",
                    },
                    "nav-link-selected": {"background-color": "#31333F"},
                },
            )
        return selected

    def render_upload_view(self) -> None:
        st.title("Upload")
        st.markdown(
            "Upload a PDF statement to process into anonymised transactions to be stored and used for budget planning."
        )

        total_txns, min_date_raw, max_date_raw, has_statements = (
            self.db_repo.get_upload_metrics()
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            with st.container(border=True):
                st.markdown(
                    "<span class='period-label'>Upload a PDF statement</span>",
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

        with col2:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="metric-card-container">
                        <div class="period-label">Total transactions uploaded</div>
                        <div class="metric-large">{total_txns}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with col3:
            with st.container(border=True):
                if not has_statements:
                    st.markdown(
                        """
                        <div class="metric-card-container">
                            <div class="period-label">Statement period uploaded</div>
                            <div class="period-val" style="margin-top: 0.5rem;">No statements uploaded</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    from_str = self.format_date_str(min_date_raw)
                    to_str = self.format_date_str(max_date_raw)
                    st.markdown(
                        f"""
                        <div class="metric-card-container">
                            <div class="period-label">Statement period uploaded</div>
                            <div class="period-label">From:</div>
                            <div class="period-val">{from_str}</div>
                            <div class="period-label">To:</div>
                            <div class="period-val">{to_str}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        if process_btn:
            if uploaded_file is None:
                st.error("Please select a PDF file before processing.")
            else:
                with st.spinner("Processing statement..."):
                    temp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".pdf"
                        ) as tmp:
                            tmp.write(uploaded_file.getvalue())
                            temp_path = tmp.name

                        success = parse_statement(temp_path)
                        if success:
                            st.success("Statement processed successfully!")
                            st.rerun()
                        else:
                            st.error(
                                "Failed to process statement. Duplicate or invalid PDF file."
                            )
                    except Exception as err:
                        st.error(f"Error processing file: {str(err)}")
                    finally:
                        if temp_path and os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                            except OSError:
                                pass

        st.subheader("Transactions uploaded")
        df = self.db_repo.get_transactions_dataframe()

        if "current_page" not in st.session_state:
            st.session_state.current_page = 1

        total_rows = len(df)
        total_pages = math.ceil(total_rows / 10) if total_rows > 0 else 1

        if st.session_state.current_page > total_pages:
            st.session_state.current_page = total_pages
        if st.session_state.current_page < 1:
            st.session_state.current_page = 1

        start_idx = (st.session_state.current_page - 1) * 10
        end_idx = st.session_state.current_page * 10
        page_df = df.iloc[start_idx:end_idx]

        st.dataframe(page_df, use_container_width=True)

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
                f"<div style='text-align: center; padding-top: 0.4rem;'>"
                f"Page <b>{st.session_state.current_page}</b> of <b>{total_pages}</b>"
                f"</div>",
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
        st.set_page_config(
            page_title="Personal Expense Tracker",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        self.inject_custom_css()
        selected_menu = self.render_sidebar()

        if selected_menu == "Upload":
            self.render_upload_view()
        elif selected_menu == "Dashboard":
            st.title("Dashboard")
            st.info("Dashboard module under development.")
        elif selected_menu == "Charts":
            st.title("Charts")
            st.info("Charts module under development.")


if __name__ == "__main__":
    app = StatementIngestionApp()
    app.run()