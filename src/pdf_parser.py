import os
import re
import sqlite3
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import pdfplumber


class HKStatementParser:
    MONTH_MAP: Dict[str, int] = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
        'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
        'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    KNOWN_CURRENCIES = {
        'AUD', 'USD', 'HKD', 'SGD', 'EUR', 'GBP', 'JPY', 'CAD', 'NZD',
        'CNY', 'TWD', 'THB', 'KRW', 'MYR', 'PHP', 'INR', 'VND', 'IDR',
        'CHF', 'SEK', 'NOK', 'DKK', 'SAR', 'AED', 'MOP'
    }

    CATEGORIES: Dict[str, List[str]] = {
        "Automotive": ["MEEK AUTOMOTIVE", "SHANNONS", "SUPERCHEAP AUTO", "AUTOMOTIVE", "MECHANIC"],
        "Bank Fees": ["DCC FEE", "FOREIGN TRANSACTION FEE", "LATE FEE", "INTEREST CHARGE"],
        "Dining & Cafes": [
            "24 YORK", "BARE WITNESS", "BAMBOO SUSHI", "BY V BAR", "CONCORDIA CLUB",
            "CHARGRILL OLYMPICPARK", "EL JANNAH", "GYUKATSU KYOTO", "HASHI SUSHI",
            "HIN TEE CHOO", "HOONSIKDANG", "KFC", "MESSIN", "SIMPLE SIMONS GELATO",
            "SQ *ANGUS MARRICKVILLE", "SQ *BELLA BACIATA", "SQ *GOOD FELLA",
            "SQ *GUMPTION", "SQ *HEADLANDS", "SQ *KABUL SOCIAL", "SQ *LAB RHODES",
            "SQ *MAMUKI", "SQ *THE BERLIN FOOD", "SQ *YUMYUM", "THE LUCKY PLACE",
            "THE MAJOR HABERFIELD", "THE LONDON HOTEL", "UNCLE TETSU", "GELATO",
            "GYG", "CAFE", "RESTAURANT", "COFFEE", "BAKERY", "PATISSERIE", "MCDONALD"
        ],
        "Fuel": ["BP ", "BP CONNECT", "SHELL", "AMPOL", "7-ELEVEN", "UNITED PETROLEUM", "CALTEX"],
        "Groceries": ["WOOLWORTHS", "COLES", "ALDI", "PETBARN", "ZETCITI", "SUPERMARKET", "IGAMARKET", "GROCER"],
        "Haircut": ["SQ *STUDIO NO. 4", "BARBER", "HAIR", "SALON"],
        "Health & Fitness": [
            "ADRENALINE HQ", "CHEMIST WAREHOUSE", "EZI*DYNASTY", "KAPNOR",
            "GYM", "PHARMACY", "CHEMIST", "HEALTH", "FITNESS"
        ],
        "Medical": ["SHIM SZE EIN", "DOCTOR", "CLINIC", "DENTAL", "MEDICAL"],
        "Shopping & Retail": ["AMAZON", "AQUILA", "KIEHLS", "REBEL", "UNIQLO", "BUNNINGS", "KMART", "TARGET", "APPLE"],
        "Subscriptions": ["CANVA", "NETFLIX", "PDF.NET", "SPOTIFY", "APPLE.COM/BILL", "YOUTUBE", "PRIME", "DISNEY"],
        "Transport": ["OPAL", "PARKING", "UBER", "TAXI", "TRANSPORT", "TRANSIT"],
        "Utilities": ["TELSTRA", "OPTUS", "ENERGY", "WATER", "AANET", "AGL", "ORIGIN"]
    }

    def __init__(self, pdf_path: str):
        self.pdf_path: str = pdf_path
        self.statement_year: int = 2026
        self.statement_month: int = 1

    @staticmethod
    def _parse_date_token(token: str) -> Tuple[int, int]:
        token_clean = re.sub(r'\s+', '', token).upper()
        match = re.match(r'(\d{1,2})([A-Z]{3})', token_clean)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            month = HKStatementParser.MONTH_MAP.get(month_str, 1)
            return day, month
        return 1, 1

    def _format_transaction_date(self, token: str) -> str:
        day, month = self._parse_date_token(token)
        if month > self.statement_month:
            year = self.statement_year - 1
        else:
            year = self.statement_year
        return f"{day:02d}-{month:02d}-{year}"

    def _extract_statement_date(self, pdf: pdfplumber.PDF) -> None:
        if not pdf.pages:
            return
        page1_text = pdf.pages[0].extract_text() or ""
        lines = page1_text.split('\n')
        for i, line in enumerate(lines):
            if "Statement date" in line or "結單日" in line:
                text_to_search = line + " " + (lines[i + 1] if i + 1 < len(lines) else "")
                match = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b', text_to_search, re.IGNORECASE)
                if match:
                    _, month_str, year_str = match.groups()
                    self.statement_year = int(year_str)
                    self.statement_month = HKStatementParser.MONTH_MAP.get(month_str.upper(), 1)
                    break

    @staticmethod
    def _clean_merchant_info(raw_merchant: str) -> Tuple[str, str, str]:
        tokens = raw_merchant.strip().split()
        currency = None
        country = None

        if tokens and tokens[-1].upper() in HKStatementParser.KNOWN_CURRENCIES:
            currency = tokens.pop().upper()

        if tokens and len(tokens[-1]) == 2 and tokens[-1].isalpha() and tokens[-1].isupper():
            country = tokens.pop().upper()

        merchant_name = " ".join(tokens)

        if country and not currency:
            currency = "HKD"

        if not country and not currency:
            country = "HK"
            currency = "HKD"

        if currency and not country:
            country = "HK"

        return merchant_name, country or "HK", currency or "HKD"

    @staticmethod
    def _format_monetary_value(raw_val: Optional[str]) -> str:
        if not raw_val:
            return ""
        cleaned = raw_val.replace('CR', '').replace('$', '').replace(',', '').strip()
        try:
            val = float(cleaned)
            return f"${val:,.2f}"
        except ValueError:
            return ""

    @staticmethod
    def _parse_fx_rate(line: str) -> Optional[str]:
        match = re.search(r'\*?\s*EXCHANGE RATE\s*:\s*([\d\.]+)', line, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_apple_pay_line(line: str) -> bool:
        return "APPLE PAY" in line.upper()

    @staticmethod
    def _is_global_stop_anchor(line: str) -> bool:
        return "FOR CREDIT CARD TRANSACTIONS EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS" in line.upper()

    @staticmethod
    def _categorize_merchant(merchant: str) -> str:
        m_upper = merchant.upper()
        for cat, kws in HKStatementParser.CATEGORIES.items():
            for kw in kws:
                if kw in m_upper:
                    return cat
        return "Uncategorised"

    @staticmethod
    def _is_excluded_from_db(merchant: str) -> bool:
        m_upper = merchant.upper()
        return "IFS PAYMENT" in m_upper or "PAYMENT - THANK YOU" in m_upper

    def parse(self) -> List[Dict[str, Any]]:
        transactions: List[Dict[str, Any]] = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                self._extract_statement_date(pdf)

                current_txn: Optional[Dict[str, Any]] = None
                date_start_re = re.compile(
                    r'^\s*(\d{1,2}\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))\s+'
                    r'(\d{1,2}\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))\s+(.*)$',
                    re.IGNORECASE
                )

                stop_all = False

                for page_num, page in enumerate(pdf.pages, start=1):
                    if stop_all:
                        break

                    if page_num == 2:
                        continue

                    page_text = page.extract_text() or ""
                    lines = page_text.split('\n')

                    in_page_txns = (page_num != 1)

                    for line in lines:
                        line_str = line.strip()
                        if not line_str:
                            continue

                        if self._is_global_stop_anchor(line_str):
                            stop_all = True
                            break

                        if page_num == 1:
                            if "MINIMUM PAYMENT SUMMARY" in line_str.upper() or "SUMMARY 戶口概要" in line_str.upper():
                                break
                            if "PREVIOUS BALANCE" in line_str.upper() or "上月結欠/結餘" in line_str.upper():
                                continue
                            if not in_page_txns:
                                if ("POST DATE" in line_str.upper() and "TRANS DATE" in line_str.upper()) or \
                                   ("DESCRIPTION OF TRANSACTION" in line_str.upper()):
                                    in_page_txns = True
                                continue

                        match = date_start_re.match(line_str)
                        if match:
                            if current_txn:
                                transactions.append(current_txn)
                                current_txn = None

                            raw_post = match.group(1)
                            raw_trans = match.group(2)
                            rest = match.group(3)

                            two_amt_match = re.match(
                                r'^(.*?)\s+([\d,]+\.\d{2}(?:\s*CR)?)\s+([\d,]+\.\d{2}(?:\s*CR)?)\s*$',
                                rest, re.IGNORECASE
                            )
                            one_amt_match = re.match(
                                r'^(.*?)\s+([\d,]+\.\d{2}(?:\s*CR)?)\s*$',
                                rest, re.IGNORECASE
                            )

                            if two_amt_match:
                                merchant_part = two_amt_match.group(1)
                                aud_amt_raw = two_amt_match.group(2)
                                hkd_amt_raw = two_amt_match.group(3)
                            elif one_amt_match:
                                merchant_part = one_amt_match.group(1)
                                aud_amt_raw = None
                                hkd_amt_raw = one_amt_match.group(2)
                            else:
                                merchant_part = rest
                                aud_amt_raw = None
                                hkd_amt_raw = None

                            m_name, country, currency = self._clean_merchant_info(merchant_part)

                            current_txn = {
                                "post_date": self._format_transaction_date(raw_post),
                                "trans_date": self._format_transaction_date(raw_trans),
                                "merchant": m_name,
                                "country": country,
                                "purchase_currency": currency,
                                "aud_amount": self._format_monetary_value(aud_amt_raw),
                                "hkd_amount": self._format_monetary_value(hkd_amt_raw),
                                "fx_rate": ""
                            }
                        else:
                            if current_txn:
                                if self._is_apple_pay_line(line_str):
                                    continue
                                rate = self._parse_fx_rate(line_str)
                                if rate:
                                    current_txn["fx_rate"] = rate

                if current_txn:
                    transactions.append(current_txn)
        except Exception as e:
            pass

        return transactions

    def save_to_db(self, transactions: List[Dict[str, Any]], db_path: str = "db/personal-expense-tracker.db") -> None:
        try:
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "category" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "country" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_name TEXT UNIQUE,
                country_code TEXT UNIQUE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "currency" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_country_id INTEGER,
                currency_code TEXT UNIQUE,
                FOREIGN KEY(currency_country_id) REFERENCES "country"(id)
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS "transaction" (
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
                FOREIGN KEY(country_id) REFERENCES "country"(id),
                FOREIGN KEY(purchase_currency_id) REFERENCES "currency"(id),
                FOREIGN KEY(category_id) REFERENCES "category"(id)
            );
            """)

            for txn in transactions:
                merchant = txn["merchant"]
                if self._is_excluded_from_db(merchant):
                    continue

                cat_name = self._categorize_merchant(merchant)
                cursor.execute("SELECT id FROM category WHERE category_name = ?", (cat_name,))
                cat_row = cursor.fetchone()
                if cat_row:
                    cat_id = cat_row[0]
                else:
                    cursor.execute("INSERT INTO category (category_name) VALUES (?)", (cat_name,))
                    cat_id = cursor.lastrowid

                country_code = txn["country"]
                country_id = None
                if country_code:
                    cursor.execute("SELECT id FROM country WHERE country_code = ?", (country_code,))
                    c_row = cursor.fetchone()
                    if c_row:
                        country_id = c_row[0]
                    else:
                        cursor.execute("INSERT INTO country (country_name, country_code) VALUES (?, ?)", (country_code, country_code))
                        country_id = cursor.lastrowid

                curr_code = txn["purchase_currency"]
                curr_id = None
                if curr_code:
                    cursor.execute("SELECT id FROM currency WHERE currency_code = ?", (curr_code,))
                    curr_row = cursor.fetchone()
                    if curr_row:
                        curr_id = curr_row[0]
                    else:
                        cursor.execute("INSERT INTO currency (currency_country_id, currency_code) VALUES (?, ?)", (country_id, curr_code))
                        curr_id = cursor.lastrowid

                def to_iso(d_str: str) -> Optional[str]:
                    if not d_str:
                        return None
                    parts = d_str.split('-')
                    return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else d_str

                def parse_num(val_str: str) -> Optional[float]:
                    if not val_str:
                        return None
                    cleaned = val_str.replace('$', '').replace(',', '').strip()
                    try:
                        return float(cleaned)
                    except ValueError:
                        return None

                p_date = to_iso(txn["post_date"])
                t_date = to_iso(txn["trans_date"])
                txn_amt = parse_num(txn["aud_amount"])
                hkd_amt = parse_num(txn["hkd_amount"])
                fx = parse_num(txn["fx_rate"])

                cursor.execute("""
                INSERT INTO "transaction" (
                    post_date, trans_date, merchant, country_id, purchase_currency_id,
                    txn_amount, hkd_amount, fx_rate, category_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (p_date, t_date, merchant, country_id, curr_id, txn_amt, hkd_amt, fx, cat_id))

            conn.commit()
            conn.close()
        except Exception as e:
            pass


def parse_statement(pdf_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame:
    parser = HKStatementParser(pdf_path)
    txns = parser.parse()
    parser.save_to_db(txns)

    columns = [
        "post_date", "trans_date", "merchant", "country",
        "purchase_currency", "aud_amount", "hkd_amount", "fx_rate"
    ]

    df = pd.DataFrame(txns, columns=columns) if txns else pd.DataFrame(columns=columns)

    if output_csv_path:
        out_dir = os.path.dirname(output_csv_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        df.to_csv(output_csv_path, index=False)

    return df