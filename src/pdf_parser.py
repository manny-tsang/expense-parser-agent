import os
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import pdfplumber


class HKStatementParser:
    """Parser for HK Credit Card PDF Statements."""

    CATEGORIES: Dict[str, List[str]] = {
        "Automotive": ["MEEK AUTOMOTIVE", "SHANNONS", "SUPERCHEAP AUTO", "AUTOMOTIVE", "MECHANIC"],
        "Bank Fees": ["DCC FEE", "FOREIGN TRANSACTION FEE", "LATE FEE", "INTEREST CHARGE"],
        "Dining & Cafes": [
            "24 YORK", "BARE WITNESS", "BAMBOO SUSHI", "BY V BAR", "CONCORDIA CLUB",
            "CHARGRILL OLYMPICPARK", "EL JANNAH", "GYUKATSU KYOTO", "HASHI SUSHI",
            "HIN TEE CHOO", "HOONSIKDANG", "KFC", "MESSIN", "SIMPLE SIMONS GELATO",
            "SQ *ANGUS MARRICKVILLE", "SQ *BELLA BACIATA", "SQ *GOOD FELLA", "SQ *GUMPTION",
            "SQ *HEADLANDS", "SQ *KABUL SOCIAL", "SQ *LAB RHODES", "SQ *MAMUKI",
            "SQ *THE BERLIN FOOD", "SQ *YUMYUM", "THE LUCKY PLACE", "THE MAJOR HABERFIELD",
            "THE LONDON HOTEL", "UNCLE TETSU", "GELATO", "GYG", "CAFE", "RESTAURANT",
            "COFFEE", "BAKERY", "PATISSERIE", "MCDONALD"
        ],
        "Fuel": ["BP ", "BP CONNECT", "SHELL", "AMPOL", "7-ELEVEN", "UNITED PETROLEUM", "CALTEX"],
        "Groceries": ["WOOLWORTHS", "COLES", "ALDI", "PETBARN", "ZETCITI", "SUPERMARKET", "IGAMARKET", "GROCER"],
        "Haircut": ["SQ *STUDIO NO. 4", "BARBER", "HAIR", "SALON"],
        "Health & Fitness": [
            "ADRENALINE HQ", "CHEMIST WAREHOUSE", "EZI*DYNASTY", "KAPNOR", "GYM",
            "PHARMACY", "CHEMIST", "HEALTH", "FITNESS"
        ],
        "Medical": ["SHIM SZE EIN", "DOCTOR", "CLINIC", "DENTAL", "MEDICAL"],
        "Shopping & Retail": ["AMAZON", "AQUILA", "KIEHLS", "REBEL", "UNIQLO", "BUNNINGS", "KMART", "TARGET", "APPLE"],
        "Subscriptions": ["CANVA", "NETFLIX", "PDF.NET", "SPOTIFY", "APPLE.COM/BILL", "YOUTUBE", "PRIME", "DISNEY"],
        "Transport": ["OPAL", "PARKING", "UBER", "TAXI", "TRANSPORT", "TRANSIT"],
        "Utilities": ["TELSTRA", "OPTUS", "ENERGY", "WATER", "AANET", "AGL", "ORIGIN"]
    }

    ISO_CURRENCIES = {
        'AUD', 'USD', 'EUR', 'GBP', 'SGD', 'CAD', 'JPY', 'CNY', 'NZD',
        'HKD', 'TWD', 'KRW', 'THB', 'MYR', 'PHP', 'VND', 'IDR', 'INR', 'AED', 'SAR', 'CHF'
    }

    ISO_COUNTRIES = {
        'AU', 'US', 'SG', 'HK', 'JP', 'CN', 'GB', 'CA', 'NZ', 'DE',
        'FR', 'IT', 'ES', 'TW', 'KR', 'TH', 'MY', 'PH', 'VN', 'ID', 'IN', 'MO', 'AE', 'SA', 'CH'
    }

    MONTH_MAP = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        self.db_path = db_path

    @staticmethod
    def parse_statement_date(text: str) -> Tuple[int, int]:
        """Extract statement year and month from text."""
        stmt_pattern = re.compile(
            r'(?:Statement\s*date|結單日)[^\n]*?\b(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4})\b',
            re.IGNORECASE
        )
        match = stmt_pattern.search(text)
        if not match:
            fallback_match = re.search(r'\b(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4})\b', text)
            if fallback_match:
                match = fallback_match

        if match:
            month_str = match.group(2).upper()
            year = int(match.group(3))
            month = HKStatementParser.MONTH_MAP.get(month_str, datetime.now().month)
            return year, month

        now = datetime.now()
        return now.year, now.month

    @staticmethod
    def format_txn_date(raw_date_str: str, stmt_year: int, stmt_month: int) -> str:
        """Convert raw date string (e.g. 09JUN) into DD-MM-YYYY format handling cross-year boundaries."""
        match = re.match(r'(\d{1,2})\s*([A-Za-z]{3})', raw_date_str.strip(), re.IGNORECASE)
        if not match:
            return raw_date_str

        day = int(match.group(1))
        mon_str = match.group(2).upper()
        month = HKStatementParser.MONTH_MAP.get(mon_str, stmt_month)

        if month > stmt_month:
            txn_year = stmt_year - 1
        else:
            txn_year = stmt_year

        return f"{day:02d}-{month:02d}-{txn_year:04d}"

    @staticmethod
    def categorize_merchant(merchant: str) -> str:
        """Categorize a merchant based on keyword dictionary rules."""
        merchant_upper = merchant.upper()
        for cat_name, keywords in HKStatementParser.CATEGORIES.items():
            for kw in keywords:
                if kw in merchant_upper:
                    return cat_name
        return "Uncategorised"

    @staticmethod
    def parse_amount_str(amt_str: str) -> float:
        """Parse numeric amount string to float handling commas and trailing minus."""
        clean_str = amt_str.replace(',', '').strip()
        if clean_str.endswith('-'):
            return -float(clean_str[:-1])
        return float(clean_str)

    @staticmethod
    def format_currency_cell(val: Optional[float]) -> str:
        """Format monetary value for CSV dataframe."""
        if val is None:
            return ""
        if val < 0:
            return f"-${abs(val):,.2f}"
        return f"${val:,.2f}"

    def parse_line_1(
        self, rest_line: str
    ) -> Tuple[str, str, str, Optional[float], float]:
        """Extract clean merchant, country, currency, foreign amount, and HKD amount from transaction line."""
        amt_pattern = re.compile(
            r'^(.*?)\s+([\d,]+\.\d{2}-?)(?:\s+([\d,]+\.\d{2}-?))?\s*$'
        )
        match = amt_pattern.search(rest_line.strip())

        if match:
            text_before = match.group(1).strip()
            amt1_str = match.group(2)
            amt2_str = match.group(3)

            if amt2_str:
                foreign_amt = self.parse_amount_str(amt1_str)
                hkd_amt = self.parse_amount_str(amt2_str)
            else:
                foreign_amt = None
                hkd_amt = self.parse_amount_str(amt1_str)
        else:
            text_before = rest_line.strip()
            foreign_amt = None
            hkd_amt = 0.0

        tokens = text_before.split()
        country = ""
        purchase_currency = ""

        if tokens:
            last_token = tokens[-1].upper()
            if last_token in self.ISO_CURRENCIES:
                purchase_currency = last_token
                tokens.pop()

        if tokens:
            last_token = tokens[-1].upper()
            if last_token in self.ISO_COUNTRIES or (len(last_token) == 2 and last_token.isalpha() and last_token.isupper()):
                country = last_token
                tokens.pop()

        clean_merchant = " ".join(tokens).strip()

        if country and not purchase_currency:
            purchase_currency = "HKD"
        elif not country and not purchase_currency:
            country = "HK"
            purchase_currency = "HKD"

        return clean_merchant, country, purchase_currency, foreign_amt, hkd_amt

    def parse_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract transactions from PDF file according to spec rules."""
        raw_transactions: List[Dict[str, Any]] = []

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return raw_transactions

            page1_text = pdf.pages[0].extract_text() or ""
            stmt_year, stmt_month = self.parse_statement_date(page1_text)

            current_txn: Optional[Dict[str, Any]] = None
            global_stop = False

            line_start_pattern = re.compile(
                r'^\s*(\d{1,2}\s*[A-Za-z]{3})\s+(\d{1,2}\s*[A-Za-z]{3})\s+(.*)$'
            )

            def commit_current_txn():
                nonlocal current_txn
                if current_txn is not None:
                    raw_transactions.append(current_txn)
                    current_txn = None

            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1

                if page_num == 2:
                    continue

                if global_stop:
                    break

                page_text = page.extract_text()
                if not page_text:
                    continue

                lines = page_text.split('\n')
                in_trans_section_p1 = False

                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        continue

                    if page_num == 1:
                        if ("MINIMUM PAYMENT SUMMARY" in line_str.upper() or
                            "SUMMARY 戶口概要" in line_str or
                            ("SUMMARY" in line_str.upper() and "戶口概要" in line_str)):
                            commit_current_txn()
                            break

                        if (("POST DATE" in line_str.upper() and "TRANS DATE" in line_str.upper()) or
                            "DESCRIPTION OF TRANSACTION" in line_str.upper()):
                            in_trans_section_p1 = True
                            continue

                        if not in_trans_section_p1:
                            continue

                        if "PREVIOUS BALANCE" in line_str.upper() or "上月結欠/結餘" in line_str or "上月結欠" in line_str:
                            continue

                    else:
                        if ("FOR CREDIT CARD TRANSACTIONS EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS" in line_str.upper() or
                            "EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS" in line_str.upper()):
                            commit_current_txn()
                            global_stop = True
                            break

                        if (("POST DATE" in line_str.upper() and "TRANS DATE" in line_str.upper()) or
                            "DESCRIPTION OF TRANSACTION" in line_str.upper() or
                            "PREVIOUS BALANCE" in line_str.upper() or
                            "上月結欠/結餘" in line_str):
                            continue

                    if "APPLE PAY-MOBILE:" in line_str.upper():
                        continue

                    fx_match = re.search(r'EXCHANGE RATE\s*:?\s*([\d\.]+)', line_str, re.IGNORECASE)
                    if fx_match and current_txn is not None:
                        try:
                            current_txn['fx_rate'] = float(fx_match.group(1))
                        except ValueError:
                            pass
                        continue

                    match_l1 = line_start_pattern.match(line_str)
                    if match_l1:
                        commit_current_txn()

                        post_date_raw = match_l1.group(1)
                        trans_date_raw = match_l1.group(2)
                        rest_line = match_l1.group(3)

                        merchant, country, purchase_curr, foreign_amt, hkd_amt = self.parse_line_1(rest_line)

                        post_date_formatted = self.format_txn_date(post_date_raw, stmt_year, stmt_month)
                        trans_date_formatted = self.format_txn_date(trans_date_raw, stmt_year, stmt_month)

                        current_txn = {
                            'post_date': post_date_formatted,
                            'trans_date': trans_date_formatted,
                            'merchant': merchant,
                            'country': country,
                            'purchase_currency': purchase_curr,
                            'aud_amount_raw': foreign_amt,
                            'hkd_amount_raw': hkd_amt,
                            'fx_rate': None
                        }

            commit_current_txn()

        return raw_transactions

    def init_db(self, conn: sqlite3.Connection) -> None:
        """Initialize database schema."""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS country (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_name TEXT UNIQUE,
                country_code TEXT UNIQUE
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS currency (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_country_id INTEGER,
                currency_code TEXT UNIQUE,
                FOREIGN KEY(currency_country_id) REFERENCES country(id)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_date DATE,
                trans_date DATE,
                merchant TEXT,
                country_id INTEGER,
                purchase_currency_id INTEGER,
                txn_amount REAL,
                hkd_amount REAL,
                fx_rate NUMERIC,
                category_id INTEGER,
                FOREIGN KEY(country_id) REFERENCES country(id),
                FOREIGN KEY(purchase_currency_id) REFERENCES currency(id),
                FOREIGN KEY(category_id) REFERENCES category(id)
            );
        """)
        conn.commit()

    def save_to_db(self, transactions: List[Dict[str, Any]]) -> None:
        """Persist cleaned transactions to SQLite database."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            self.init_db(conn)
            cursor = conn.cursor()

            for txn in transactions:
                merchant = txn['merchant']

                if "IFS PAYMENT" in merchant.upper() or "PAYMENT - THANK YOU" in merchant.upper():
                    continue

                category_name = self.categorize_merchant(merchant)
                cursor.execute("SELECT id FROM category WHERE category_name = ?", (category_name,))
                cat_row = cursor.fetchone()
                if cat_row:
                    category_id = cat_row[0]
                else:
                    cursor.execute("INSERT INTO category (category_name) VALUES (?)", (category_name,))
                    category_id = cursor.lastrowid

                country_code = txn['country']
                country_id = None
                if country_code:
                    cursor.execute("SELECT id FROM country WHERE country_code = ?", (country_code,))
                    c_row = cursor.fetchone()
                    if c_row:
                        country_id = c_row[0]
                    else:
                        cursor.execute("INSERT INTO country (country_name, country_code) VALUES (?, ?)", (country_code, country_code))
                        country_id = cursor.lastrowid

                currency_code = txn['purchase_currency']
                currency_id = None
                if currency_code:
                    cursor.execute("SELECT id FROM currency WHERE currency_code = ?", (currency_code,))
                    curr_row = cursor.fetchone()
                    if curr_row:
                        currency_id = curr_row[0]
                    else:
                        cursor.execute("INSERT INTO currency (currency_country_id, currency_code) VALUES (?, ?)", (country_id, currency_code))
                        currency_id = cursor.lastrowid

                def to_iso_date(dt_str: str) -> str:
                    try:
                        return datetime.strptime(dt_str, "%d-%m-%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        return dt_str

                post_date_iso = to_iso_date(txn['post_date'])
                trans_date_iso = to_iso_date(txn['trans_date'])

                txn_amount = txn['aud_amount_raw'] if txn['aud_amount_raw'] is not None else txn['hkd_amount_raw']

                cursor.execute("""
                    INSERT INTO transaction (
                        post_date, trans_date, merchant, country_id,
                        purchase_currency_id, txn_amount, hkd_amount, fx_rate, category_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_date_iso,
                    trans_date_iso,
                    merchant,
                    country_id,
                    currency_id,
                    txn_amount,
                    txn['hkd_amount_raw'],
                    txn['fx_rate'],
                    category_id
                ))

            conn.commit()
        finally:
            conn.close()

    def build_dataframe(self, transactions: List[Dict[str, Any]]) -> pd.DataFrame:
        """Format raw transaction dictionary list into specified DataFrame structure."""
        rows = []
        for txn in transactions:
            aud_amt_str = self.format_currency_cell(txn['aud_amount_raw'])
            hkd_amt_str = self.format_currency_cell(txn['hkd_amount_raw'])
            fx_rate_str = str(txn['fx_rate']) if txn['fx_rate'] is not None else ""

            rows.append({
                'post_date': txn['post_date'],
                'trans_date': txn['trans_date'],
                'merchant': txn['merchant'],
                'country': txn['country'],
                'purchase_currency': txn['purchase_currency'],
                'aud_amount': aud_amt_str,
                'hkd_amount': hkd_amt_str,
                'fx_rate': fx_rate_str
            })

        cols = [
            'post_date', 'trans_date', 'merchant', 'country',
            'purchase_currency', 'aud_amount', 'hkd_amount', 'fx_rate'
        ]
        return pd.DataFrame(rows, columns=cols)


def parse_statement(pdf_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame:
    """Parse statement entry point function."""
    parser = HKStatementParser()
    raw_txns = parser.parse_pdf(pdf_path)

    parser.save_to_db(raw_txns)

    df = parser.build_dataframe(raw_txns)

    if output_csv_path:
        out_dir = os.path.dirname(output_csv_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        df.to_csv(output_csv_path, index=False)

    return df