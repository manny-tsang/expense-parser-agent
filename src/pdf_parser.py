import os
import re
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import pdfplumber


class HKStatementParser:
    """Parser for Hong Kong Credit Card PDF Statements."""

    MONTH_MAP = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
    }

    CURRENCY_CODES = {
        "AUD", "USD", "EUR", "GBP", "CAD", "SGD", "JPY", "NZD", "CNY", "HKD",
        "THB", "KRW", "TWD", "MYR", "IDR", "PHP", "VND", "INR", "CHF"
    }

    DB_PATH = os.path.join("db", "personal-expense-tracker.db")

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path:
            self.DB_PATH = db_path

    def process(self, pdf_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame:
        """Main pipeline for parsing PDF statement, persisting to DB, and outputting DataFrame/CSV."""
        filename = os.path.basename(pdf_path)
        self._init_db_and_check_log(filename)

        raw_txns: List[Dict[str, Any]] = []

        with pdfplumber.open(pdf_path) as pdf:
            stmt_month, stmt_year = self._extract_statement_date(pdf)

            pending_txn: Optional[Dict[str, Any]] = None
            global_stop = False

            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1

                # Skip Page 2 completely
                if page_num == 2:
                    continue

                if global_stop:
                    break

                page_text = page.extract_text() or ""
                lines = page_text.split("\n")

                page1_active = False if page_num == 1 else True

                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        continue

                    # Global Stop Anchor
                    if "*FOR CREDIT CARD TRANSACTIONS EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS" in line_str:
                        global_stop = True
                        break

                    # Page 1 Anchors
                    if page_num == 1:
                        if "MINIMUM PAYMENT SUMMARY" in line_str or "SUMMARY 戶口概要" in line_str:
                            break
                        if not page1_active:
                            if any(k in line_str for k in ["Post date", "Trans date", "Description of transaction"]):
                                page1_active = True
                            continue

                    # Exclusion Rule
                    if "PREVIOUS BALANCE" in line_str or "上月結欠/結餘" in line_str:
                        continue

                    # Line 2: Apple Pay Metadata (Discard)
                    if "APPLE PAY-MOBILE:" in line_str:
                        continue

                    # Line 3: Capture Exchange Rate
                    m_fx = re.search(r"\*?EXCHANGE\s+RATE:\s*([\d\.]+)", line_str, re.IGNORECASE)
                    if m_fx:
                        if pending_txn:
                            pending_txn["fx_rate"] = m_fx.group(1)
                        continue

                    # Line 1 Start: Matches two date tokens
                    date_pattern = r"^(\d{1,2}\s*[A-Za-z]{3})\s+(\d{1,2}\s*[A-Za-z]{3})\s+(.*)"
                    m_date = re.match(date_pattern, line_str, re.IGNORECASE)
                    if m_date:
                        if pending_txn:
                            parsed = self._parse_transaction_rest(pending_txn, stmt_month, stmt_year)
                            if parsed:
                                raw_txns.append(parsed)
                            pending_txn = None

                        pending_txn = {
                            "post_date_raw": m_date.group(1),
                            "trans_date_raw": m_date.group(2),
                            "rest": m_date.group(3),
                            "fx_rate": None
                        }

            if pending_txn and not global_stop:
                parsed = self._parse_transaction_rest(pending_txn, stmt_month, stmt_year)
                if parsed:
                    raw_txns.append(parsed)

        # Persistence to SQLite
        self._persist_to_sqlite(raw_txns, filename)

        # Build final DataFrame
        df_columns = [
            "post_date", "trans_date", "merchant", "country",
            "purchase_currency", "aud_amount", "hkd_amount", "fx_rate"
        ]

        formatted_rows = []
        for txn in raw_txns:
            formatted_rows.append({
                "post_date": txn["post_date"],
                "trans_date": txn["trans_date"],
                "merchant": txn["merchant"],
                "country": txn["country"] or "",
                "purchase_currency": txn["purchase_currency"] or "",
                "aud_amount": self._format_dollar(txn["aud_amount"]),
                "hkd_amount": self._format_dollar(txn["hkd_amount"]),
                "fx_rate": txn["fx_rate"] if txn["fx_rate"] is not None else ""
            })

        df = pd.DataFrame(formatted_rows, columns=df_columns)

        if output_csv_path and not output_csv_path.endswith(".db"):
            out_dir = os.path.dirname(output_csv_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            df.to_csv(output_csv_path, index=False)

        return df

    @staticmethod
    def _extract_statement_date(pdf: pdfplumber.PDF) -> Tuple[int, int]:
        """Extract statement_month and statement_year from Page 1 header."""
        page1 = pdf.pages[0]
        text = page1.extract_text() or ""
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if "Statement date" in line or "結單日" in line:
                search_block = " ".join(lines[i:i + 3])
                match = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b", search_block, re.IGNORECASE)
                if match:
                    _, m_str, y_str = match.groups()
                    return HKStatementParser.MONTH_MAP.get(m_str.upper(), 1), int(y_str)

        match = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b", text, re.IGNORECASE)
        if match:
            _, m_str, y_str = match.groups()
            return HKStatementParser.MONTH_MAP.get(m_str.upper(), 1), int(y_str)

        now = datetime.now()
        return now.month, now.year

    @staticmethod
    def _parse_raw_date(date_str: str, stmt_month: int, stmt_year: int) -> str:
        """Parse raw date string '09JUN' / '09 JUN' into DD-MM-YYYY format."""
        match = re.search(r"(\d{1,2})\s*([A-Za-z]{3})", date_str)
        if not match:
            return ""

        day = int(match.group(1))
        month_str = match.group(2).upper()
        month = HKStatementParser.MONTH_MAP.get(month_str, 1)

        year = stmt_year - 1 if month > stmt_month else stmt_year
        return f"{day:02d}-{month:02d}-{year:04d}"

    @staticmethod
    def _parse_float_amount(amt_str: Optional[str]) -> Optional[float]:
        """Convert monetary string into float."""
        if not amt_str:
            return None
        clean_str = amt_str.replace(",", "").replace("$", "")
        if clean_str.endswith("CR"):
            return -float(clean_str[:-2])
        return float(clean_str)

    @staticmethod
    def _format_dollar(val: Optional[float]) -> str:
        """Format numerical float as currency string."""
        if val is None:
            return ""
        if val < 0:
            return f"-${abs(val):,.2f}"
        return f"${val:,.2f}"

    @staticmethod
    def _categorise_merchant(cursor: sqlite3.Cursor, merchant_name: str) -> int:
        """Categorise merchant using SQLite merchant_mapping table lookups."""
        cursor.execute(
            """
            SELECT category_id
            FROM "merchant_mapping"
            WHERE ? LIKE '%' || pattern || '%'
               OR UPPER(?) LIKE '%' || UPPER(pattern) || '%'
            ORDER BY LENGTH(pattern) DESC, id ASC
            LIMIT 1
            """,
            (merchant_name, merchant_name)
        )
        row = cursor.fetchone()
        if row:
            return row[0]

        return HKStatementParser._get_or_create_category(cursor, "Uncategorised")

    @staticmethod
    def _parse_transaction_rest(
        pending_txn: Dict[str, Any], stmt_month: int, stmt_year: int
    ) -> Optional[Dict[str, Any]]:
        """Parse transaction details from raw Line 1 components."""
        rest = pending_txn["rest"].strip()

        # Check Exclusion Filters
        for excluded in ["IFS PAYMENT", "PAYMENT - THANK YOU", "PREVIOUS BALANCE", "上月結欠/結餘"]:
            if excluded in rest:
                return None

        post_date = HKStatementParser._parse_raw_date(pending_txn["post_date_raw"], stmt_month, stmt_year)
        trans_date = HKStatementParser._parse_raw_date(pending_txn["trans_date_raw"], stmt_month, stmt_year)

        tokens = rest.split()
        if not tokens:
            return None

        amount_pattern = re.compile(r"^-?[\d,]+\.\d{2}(?:CR)?$")

        # Rightmost token: HKD Amount
        if not amount_pattern.match(tokens[-1]):
            return None
        hkd_amount_str = tokens.pop()

        # Second rightmost token: Foreign/AUD Amount (optional)
        foreign_amount_str = None
        if tokens and amount_pattern.match(tokens[-1]):
            foreign_amount_str = tokens.pop()

        # Currency code (optional)
        purchase_currency = None
        if tokens and tokens[-1].upper() in HKStatementParser.CURRENCY_CODES:
            purchase_currency = tokens.pop().upper()

        # Country code (optional)
        country = None
        if tokens and len(tokens[-1]) == 2 and tokens[-1].isupper() and tokens[-1].isalpha():
            country = tokens.pop().upper()

        merchant = " ".join(tokens).strip()

        # Edge cases
        if country and not purchase_currency and not pending_txn["fx_rate"]:
            purchase_currency = "HKD"

        if not country and not purchase_currency:
            country = "HK"
            purchase_currency = "HKD"

        hkd_amount = HKStatementParser._parse_float_amount(hkd_amount_str)
        aud_amount = HKStatementParser._parse_float_amount(foreign_amount_str)

        return {
            "post_date": post_date,
            "trans_date": trans_date,
            "merchant": merchant,
            "country": country,
            "purchase_currency": purchase_currency,
            "aud_amount": aud_amount,
            "hkd_amount": hkd_amount,
            "fx_rate": pending_txn["fx_rate"]
        }

    @staticmethod
    def _seed_default_mappings(cursor: sqlite3.Cursor) -> None:
        """Populate initial merchant mapping rules if mapping table is empty."""
        default_mappings = {
            "Automotive": ["MEEK AUTOMOTIVE", "SHANNONS", "SUPERCHEAP AUTO", "AUTOMOTIVE", "MECHANIC"],
            "Bank Fees": ["DCC FEE", "FOREIGN TRANSACTION FEE", "LATE FEE", "INTEREST CHARGE"],
            "Dining & Cafes": [
                "24 YORK", "BARE WITNESS", "BAMBOO SUSHI", "BY V BAR", "CONCORDIA CLUB", "CHARGRILL OLYMPICPARK",
                "EL JANNAH", "GYUKATSU KYOTO", "HASHI SUSHI", "HIN TEE CHOO", "HOONSIKDANG", "KFC", "MESSIN",
                "SIMPLE SIMONS GELATO", "SQ *ANGUS MARRICKVILLE", "SQ *BELLA BACIATA", "SQ *GOOD FELLA",
                "SQ *GUMPTION", "SQ *HEADLANDS", "SQ *KABUL SOCIAL", "SQ *LAB RHODES", "SQ *MAMUKI",
                "SQ *THE BERLIN FOOD", "SQ *YUMYUM", "THE LUCKY PLACE", "THE MAJOR HABERFIELD", "THE LONDON HOTEL",
                "UNCLE TETSU", "GELATO", "GYG", "CAFE", "RESTAURANT", "COFFEE", "BAKERY", "PATISSERIE", "MCDONALD"
            ],
            "Fuel": ["BP ", "BP CONNECT", "SHELL", "AMPOL", "7-ELEVEN", "UNITED PETROLEUM", "CALTEX"],
            "Groceries": ["WOOLWORTHS", "COLES", "ALDI", "PETBARN", "ZETCITI", "SUPERMARKET", "IGAMARKET", "GROCER"],
            "Haircut": ["SQ *STUDIO NO. 4", "BARBER", "HAIR", "SALON"],
            "Health & Fitness": [
                "ADRENALINE HQ", "CHEMIST WAREHOUSE", "EZI*DYNASTY", "KAPNOR", "GYM", "PHARMACY",
                "CHEMIST", "HEALTH", "FITNESS"
            ],
            "Medical": ["SHIM SZE EIN", "DOCTOR", "CLINIC", "DENTAL", "MEDICAL"],
            "Shopping & Retail": ["AMAZON", "AQUILA", "KIEHLS", "REBEL", "UNIQLO", "BUNNINGS", "KMART", "TARGET", "APPLE"],
            "Subscriptions": ["CANVA", "NETFLIX", "PDF.NET", "SPOTIFY", "APPLE.COM/BILL", "YOUTUBE", "PRIME", "DISNEY"],
            "Transport": ["OPAL", "PARKING", "UBER", "TAXI", "TRANSPORT", "TRANSIT"],
            "Utilities": ["TELSTRA", "OPTUS", "ENERGY", "WATER", "AANET", "AGL", "ORIGIN"]
        }

        for cat_name, patterns in default_mappings.items():
            cat_id = HKStatementParser._get_or_create_category(cursor, cat_name)
            for pattern in patterns:
                cursor.execute(
                    'INSERT OR IGNORE INTO "merchant_mapping" (pattern, category_id) VALUES (?, ?)',
                    (pattern, cat_id)
                )

        HKStatementParser._get_or_create_category(cursor, "Uncategorised")

    def _init_db_and_check_log(self, filename: Optional[str] = None) -> None:
        """Initialize database schema and check statement duplicate log."""
        db_dir = os.path.dirname(self.DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with sqlite3.connect(self.DB_PATH) as conn:
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
                    currency_code TEXT,
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "statement_log" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "merchant_mapping" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "pattern" TEXT UNIQUE NOT NULL,
                    "category_id" INTEGER NOT NULL,
                    "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY("category_id") REFERENCES "category"("id")
                );
            """)

            cursor.execute('SELECT COUNT(*) FROM "merchant_mapping"')
            count_row = cursor.fetchone()
            if count_row and count_row[0] == 0:
                self._seed_default_mappings(cursor)

            if filename:
                cursor.execute('SELECT id FROM "statement_log" WHERE filename = ?', (filename,))
                if cursor.fetchone() is not None:
                    raise ValueError(f"Statement '{filename}' has already been processed.")

            conn.commit()

    def _persist_to_sqlite(self, raw_txns: List[Dict[str, Any]], filename: str) -> None:
        """Persist structured transactions and update log in SQLite."""
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()

            for txn in raw_txns:
                # Exclusion filter guard
                if any(ex in txn["merchant"].upper() for ex in ["IFS PAYMENT", "PAYMENT - THANK YOU"]):
                    continue

                cat_id = self._categorise_merchant(cursor, txn["merchant"])
                country_id = self._get_or_create_country(cursor, txn["country"])
                currency_id = self._get_or_create_currency(cursor, txn["purchase_currency"], country_id)

                p_parts = txn["post_date"].split("-")
                t_parts = txn["trans_date"].split("-")
                post_date_iso = f"{p_parts[2]}-{p_parts[1]}-{p_parts[0]}"
                trans_date_iso = f"{t_parts[2]}-{t_parts[1]}-{t_parts[0]}"

                txn_amount = txn["aud_amount"] if txn["aud_amount"] is not None else txn["hkd_amount"]
                fx_rate_val = float(txn["fx_rate"]) if txn["fx_rate"] is not None else None

                cursor.execute("""
                    INSERT INTO "transaction" (
                        post_date, trans_date, merchant, country_id, purchase_currency_id,
                        txn_amount, hkd_amount, fx_rate, category_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_date_iso, trans_date_iso, txn["merchant"], country_id, currency_id,
                    txn_amount, txn["hkd_amount"], fx_rate_val, cat_id
                ))

            cursor.execute('INSERT INTO "statement_log" (filename) VALUES (?)', (filename,))
            conn.commit()

    @staticmethod
    def _get_or_create_category(cursor: sqlite3.Cursor, category_name: str) -> int:
        cursor.execute('SELECT id FROM "category" WHERE category_name = ?', (category_name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute('INSERT INTO "category" (category_name) VALUES (?)', (category_name,))
        return cursor.lastrowid

    @staticmethod
    def _get_or_create_country(cursor: sqlite3.Cursor, country_code: Optional[str]) -> Optional[int]:
        if not country_code:
            return None
        cursor.execute('SELECT id FROM "country" WHERE country_code = ?', (country_code,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute('INSERT OR IGNORE INTO "country" (country_name, country_code) VALUES (?, ?)', (country_code, country_code))
        cursor.execute('SELECT id FROM "country" WHERE country_code = ?', (country_code,))
        row = cursor.fetchone()
        return row[0] if row else None

    @staticmethod
    def _get_or_create_currency(
        cursor: sqlite3.Cursor, currency_code: Optional[str], country_id: Optional[int]
    ) -> Optional[int]:
        if not currency_code:
            return None
        if country_id:
            cursor.execute(
                'SELECT id FROM "currency" WHERE currency_code = ? AND currency_country_id = ?',
                (currency_code, country_id)
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        cursor.execute('SELECT id FROM "currency" WHERE currency_code = ?', (currency_code,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            'INSERT INTO "currency" (currency_country_id, currency_code) VALUES (?, ?)',
            (country_id, currency_code)
        )
        return cursor.lastrowid


class DatabaseRepository:
    """Database repository layer for managing transactions, categories, and merchant rules."""

    def __init__(self, db_path: str = HKStatementParser.DB_PATH) -> None:
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a connection to the SQLite database."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        """Initialize schema and seed initial database tables."""
        parser = HKStatementParser(db_path=self.db_path)
        parser._init_db_and_check_log()

    def get_transactions_dataframe(self) -> pd.DataFrame:
        """Fetch all transactions with category and currency details."""
        if not os.path.exists(self.db_path):
            return pd.DataFrame(
                columns=[
                    "id", "trans_date", "merchant", "category_name",
                    "txn_amount", "purchase_currency", "hkd_amount", "fx_rate", "category_id"
                ]
            )
        try:
            with self.get_connection() as conn:
                query = """
                SELECT 
                    t.id,
                    t.trans_date, 
                    t.merchant, 
                    c.category_name, 
                    t.txn_amount, 
                    curr.currency_code AS purchase_currency, 
                    t.hkd_amount, 
                    t.fx_rate,
                    t.category_id
                FROM "transaction" t
                LEFT JOIN category c ON t.category_id = c.id
                LEFT JOIN currency curr ON t.purchase_currency_id = curr.id
                ORDER BY t.trans_date DESC, t.id DESC
                """
                return pd.read_sql_query(query, conn)
        except Exception:
            return pd.DataFrame(
                columns=[
                    "id", "trans_date", "merchant", "category_name",
                    "txn_amount", "purchase_currency", "hkd_amount", "fx_rate", "category_id"
                ]
            )

    def get_categories(self) -> pd.DataFrame:
        """Fetch all existing categories ordered by category_name."""
        if not os.path.exists(self.db_path):
            return pd.DataFrame(columns=["id", "category_name"])
        try:
            with self.get_connection() as conn:
                query = 'SELECT id, category_name FROM "category" ORDER BY category_name ASC'
                return pd.read_sql_query(query, conn)
        except Exception:
            return pd.DataFrame(columns=["id", "category_name"])

    def get_uncategorised_merchants(self) -> pd.DataFrame:
        """Fetch distinct merchants assigned to 'Uncategorised' with transaction counts."""
        if not os.path.exists(self.db_path):
            return pd.DataFrame(columns=["merchant", "transaction_count"])
        try:
            with self.get_connection() as conn:
                query = """
                SELECT t.merchant, COUNT(t.id) AS transaction_count
                FROM "transaction" t
                JOIN category c ON t.category_id = c.id
                WHERE c.category_name = 'Uncategorised'
                GROUP BY t.merchant
                ORDER BY transaction_count DESC, t.merchant ASC
                """
                return pd.read_sql_query(query, conn)
        except Exception:
            return pd.DataFrame(columns=["merchant", "transaction_count"])

    def add_merchant_mapping_rule(self, pattern: str, category_id: int) -> bool:
        """Add a global merchant rule pattern and propagate to all matching existing transactions."""
        if not pattern or not pattern.strip():
            return False
        clean_pattern = pattern.strip()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT OR REPLACE INTO "merchant_mapping" (pattern, category_id) VALUES (?, ?)',
                    (clean_pattern, category_id)
                )
                cursor.execute(
                    """
                    UPDATE "transaction"
                    SET category_id = ?
                    WHERE UPPER(merchant) LIKE '%' || UPPER(?) || '%'
                    """,
                    (category_id, clean_pattern)
                )
                conn.commit()
                return True
        except Exception:
            return False

    def update_transaction_category(self, transaction_id: int, category_id: int) -> bool:
        """Update category_id for an individual transaction without creating a global rule."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE "transaction" SET category_id = ? WHERE id = ?',
                    (category_id, transaction_id)
                )
                conn.commit()
                return True
        except Exception:
            return False


def parse_statement(
    pdf_path: str, 
    db_path: str = "db/personal-expense-tracker.db", 
    output_csv_path: Optional[str] = None
) -> pd.DataFrame:
    """Entry point function to parse HK Credit Card PDF statements."""
    parser = HKStatementParser(db_path=db_path)
    return parser.process(pdf_path, output_csv_path)