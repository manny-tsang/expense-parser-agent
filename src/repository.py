import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd


class DatabaseRepository:
    """Centralized database repository for SQLite schema management, reference data seeding, and CRUD database operations."""

    def __init__(self, db_path: str = "db/personal-expense-tracker.db") -> None:
        """Initializes target DB path and ensures parent directories exist."""
        self.db_path = db_path
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Creates parent directory if missing and returns an active sqlite3.Connection."""
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def init_db(self, filename: Optional[str] = None) -> None:
        """Executes table creation DDLs and baseline seeding logic.

        If filename is provided, verifies it does not already exist in statement_log.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # Create Tables
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "category" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "country" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    country_name TEXT UNIQUE,
                    country_code TEXT UNIQUE
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "currency" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    currency_country_id INTEGER,
                    currency_code TEXT UNIQUE,
                    FOREIGN KEY(currency_country_id) REFERENCES "country"(id)
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "merchant" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant_name TEXT UNIQUE NOT NULL,
                    category_id INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(category_id) REFERENCES "category"(id)
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "transaction" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_date DATE,
                    trans_date DATE,
                    merchant_id INTEGER NOT NULL,
                    country_id INTEGER,
                    purchase_currency_id INTEGER,
                    txn_amount REAL,
                    hkd_amount REAL,
                    fx_rate NUMERIC,
                    category_id INTEGER,
                    FOREIGN KEY(merchant_id) REFERENCES "merchant"(id),
                    FOREIGN KEY(country_id) REFERENCES "country"(id),
                    FOREIGN KEY(purchase_currency_id) REFERENCES "currency"(id),
                    FOREIGN KEY(category_id) REFERENCES "category"(id)
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "statement_log" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            if filename:
                cursor.execute(
                    'SELECT id FROM "statement_log" WHERE filename = ?', (filename,)
                )
                if cursor.fetchone():
                    raise ValueError(f"Statement '{filename}' has already been processed.")

            # Baseline Seed Data: Category
            cursor.execute(
                'INSERT OR IGNORE INTO "category" (id, category_name) VALUES (1, \'Uncategorised\');'
            )
            canonical_categories = [
                'Automotive',
                'Bank Fees',
                'Dining & Cafes',
                'Fuel',
                'Groceries',
                'Haircut',
                'Health & Fitness',
                'Medical',
                'Pet',
                'Shopping & Retail',
                'Subscriptions',
                'Transport',
                'Utilities',
            ]
            cursor.executemany(
                'INSERT OR IGNORE INTO "category" (category_name) VALUES (?)',
                [(c,) for c in canonical_categories],
            )

            # Baseline Seed Data: Country
            countries = [
                (1, 'Austria', 'AT'),
                (2, 'Australia', 'AU'),
                (3, 'Belgium', 'BE'),
                (4, 'Bulgaria', 'BG'),
                (5, 'Canada', 'CA'),
                (6, 'China', 'CN'),
                (7, 'Croatia', 'HR'),
                (8, 'Cyprus', 'CY'),
                (9, 'Czech Republic', 'CZ'),
                (10, 'Denmark', 'DK'),
                (11, 'Estonia', 'EE'),
                (12, 'Finland', 'FI'),
                (13, 'France', 'FR'),
                (14, 'Germany', 'DE'),
                (15, 'Greece', 'GR'),
                (16, 'Hong Kong', 'HK'),
                (17, 'Hungary', 'HU'),
                (18, 'India', 'IN'),
                (19, 'Indonesia', 'ID'),
                (20, 'Ireland', 'IE'),
                (21, 'Italy', 'IT'),
                (22, 'Japan', 'JP'),
                (23, 'Latvia', 'LV'),
                (24, 'Lithuania', 'LT'),
                (25, 'Luxembourg', 'LU'),
                (26, 'Malaysia', 'MY'),
                (27, 'Malta', 'MT'),
                (28, 'Netherlands', 'NL'),
                (29, 'New Zealand', 'NZ'),
                (30, 'Philippines', 'PH'),
                (31, 'Poland', 'PL'),
                (32, 'Portugal', 'PT'),
                (33, 'Romania', 'RO'),
                (34, 'Singapore', 'SG'),
                (35, 'Slovakia', 'SK'),
                (36, 'Slovenia', 'SI'),
                (37, 'South Korea', 'KR'),
                (38, 'Spain', 'ES'),
                (39, 'Sweden', 'SE'),
                (40, 'Switzerland', 'CH'),
                (41, 'Taiwan', 'TW'),
                (42, 'Thailand', 'TH'),
                (43, 'United Kingdom', 'GB'),
                (44, 'United States', 'US'),
                (45, 'Vietnam', 'VN'),
            ]
            cursor.executemany(
                'INSERT OR IGNORE INTO "country" (id, country_name, country_code) VALUES (?, ?, ?)',
                countries,
            )

            # Baseline Seed Data: Currency
            currencies = [
                (1, 'EUR'),
                (2, 'AUD'),
                (3, 'EUR'),
                (4, 'BGN'),
                (5, 'CAD'),
                (6, 'CNY'),
                (7, 'EUR'),
                (8, 'EUR'),
                (9, 'CZK'),
                (10, 'DKK'),
                (11, 'EUR'),
                (12, 'EUR'),
                (13, 'EUR'),
                (14, 'EUR'),
                (15, 'EUR'),
                (16, 'HKD'),
                (17, 'HUF'),
                (18, 'INR'),
                (19, 'IDR'),
                (20, 'EUR'),
                (21, 'EUR'),
                (22, 'JPY'),
                (23, 'EUR'),
                (24, 'EUR'),
                (25, 'EUR'),
                (26, 'MYR'),
                (27, 'EUR'),
                (28, 'EUR'),
                (29, 'NZD'),
                (30, 'PHP'),
                (31, 'PLN'),
                (32, 'EUR'),
                (33, 'RON'),
                (34, 'SGD'),
                (35, 'EUR'),
                (36, 'EUR'),
                (37, 'KRW'),
                (38, 'EUR'),
                (39, 'SEK'),
                (40, 'CHF'),
                (41, 'TWD'),
                (42, 'THB'),
                (43, 'GBP'),
                (44, 'USD'),
                (45, 'VND'),
            ]
            cursor.executemany(
                'INSERT OR IGNORE INTO "currency" (currency_country_id, currency_code) VALUES (?, ?)',
                currencies,
            )

            conn.commit()
        finally:
            conn.close()

    def get_transactions_dataframe(self) -> pd.DataFrame:
        """Returns a DataFrame containing all transactions joined with merchant, category, and currency."""
        self.init_db()
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    t.id AS id,
                    t.trans_date AS trans_date,
                    m.merchant_name AS merchant,
                    COALESCE(override_cat.category_name, default_cat.category_name) AS category_name,
                    t.txn_amount AS txn_amount,
                    c.currency_code AS purchase_currency,
                    t.hkd_amount AS hkd_amount,
                    t.fx_rate AS fx_rate,
                    COALESCE(t.category_id, m.category_id) AS category_id
                FROM "transaction" t
                LEFT JOIN "merchant" m ON t.merchant_id = m.id
                LEFT JOIN "category" default_cat ON m.category_id = default_cat.id
                LEFT JOIN "category" override_cat ON t.category_id = override_cat.id
                LEFT JOIN "currency" c ON t.purchase_currency_id = c.id
                ORDER BY t.trans_date DESC, t.id DESC
            """
            df = pd.read_sql_query(query, conn)
            expected_cols = [
                'id',
                'trans_date',
                'merchant',
                'category_name',
                'txn_amount',
                'purchase_currency',
                'hkd_amount',
                'fx_rate',
                'category_id',
            ]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
            return df[expected_cols]
        finally:
            conn.close()

    def get_categories(self) -> pd.DataFrame:
        """Returns DataFrame of all categories (id, category_name) ordered by category_name ASC."""
        self.init_db()
        conn = self.get_connection()
        try:
            query = 'SELECT id, category_name FROM "category" ORDER BY category_name ASC'
            df = pd.read_sql_query(query, conn)
            expected_cols = ['id', 'category_name']
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
            return df[expected_cols]
        finally:
            conn.close()

    def get_merchants(self) -> pd.DataFrame:
        """Returns DataFrame of ALL merchants joined with their mapped category name ordered by merchant_name ASC."""
        self.init_db()
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    m.id AS merchant_id,
                    m.merchant_name AS merchant_name,
                    m.category_id AS category_id,
                    c.category_name AS category_name
                FROM "merchant" m
                LEFT JOIN "category" c ON m.category_id = c.id
                ORDER BY m.merchant_name ASC
            """
            df = pd.read_sql_query(query, conn)
            expected_cols = ['merchant_id', 'merchant_name', 'category_id', 'category_name']
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
            return df[expected_cols]
        finally:
            conn.close()

    def get_uncategorised_merchants(self) -> pd.DataFrame:
        """Returns DataFrame of distinct merchants where m.category_id = 1 AND t.category_id IS NULL."""
        self.init_db()
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    m.id AS merchant_id,
                    m.merchant_name AS merchant_name,
                    COUNT(t.id) AS transaction_count
                FROM "merchant" m
                JOIN "transaction" t ON t.merchant_id = m.id
                WHERE m.category_id = 1 AND (t.category_id IS NULL OR t.category_id = 1)
                GROUP BY m.id, m.merchant_name
                ORDER BY transaction_count DESC, m.merchant_name ASC
            """
            df = pd.read_sql_query(query, conn)
            expected_cols = ['merchant_id', 'merchant_name', 'transaction_count']
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
            return df[expected_cols]
        finally:
            conn.close()

    def match_merchant_category_pattern(self, merchant_name: str) -> Optional[int]:
        """Evaluates an unmapped merchant string against existing mapped merchants in SQLite using SQL substring matching."""
        if not merchant_name:
            return None
        self.init_db()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT category_id
                FROM "merchant"
                WHERE category_id != 1
                  AND UPPER(?) LIKE '%' || UPPER(merchant_name) || '%'
                ORDER BY LENGTH(merchant_name) DESC
                LIMIT 1
                """,
                (merchant_name,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def add_category(self, category_name: str) -> bool:
        """Inserts a new category into 'category'. Returns True on success, False on failure."""
        self.init_db()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO "category" (category_name) VALUES (?)', (category_name,)
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def update_merchant_category(
        self, merchant_id_or_name: Union[int, str], category_id: int
    ) -> bool:
        """Updates category_id on merchant record by id or merchant_name. Returns True on success."""
        self.init_db()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if isinstance(merchant_id_or_name, int):
                cursor.execute(
                    'UPDATE "merchant" SET category_id = ? WHERE id = ?',
                    (category_id, merchant_id_or_name),
                )
            else:
                cursor.execute(
                    'UPDATE "merchant" SET category_id = ? WHERE merchant_name = ?',
                    (category_id, str(merchant_id_or_name)),
                )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def update_transaction_category(
        self, transaction_id: int, category_id: int
    ) -> bool:
        """Updates category_id directly on 'transaction' row for explicit overrides. Returns True on success."""
        self.init_db()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE "transaction" SET category_id = ? WHERE id = ?',
                (category_id, transaction_id),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def get_or_create_merchant(
        cursor: sqlite3.Cursor, merchant_name: str, cat_id: int = 1
    ) -> int:
        """Retrieves existing merchant.id or inserts a new merchant row with cat_id."""
        cursor.execute(
            'SELECT id FROM "merchant" WHERE merchant_name = ?', (merchant_name,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            'INSERT INTO "merchant" (merchant_name, category_id) VALUES (?, ?)',
            (merchant_name, cat_id),
        )
        return cursor.lastrowid

    @staticmethod
    def get_or_create_country(
        cursor: sqlite3.Cursor, country_code: Optional[str]
    ) -> Optional[int]:
        """Resolves or creates country.id."""
        if not country_code:
            return None
        cursor.execute(
            'SELECT id FROM "country" WHERE country_code = ?', (country_code,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            'INSERT INTO "country" (country_name, country_code) VALUES (?, ?)',
            (country_code, country_code),
        )
        return cursor.lastrowid

    @staticmethod
    def get_or_create_currency(
        cursor: sqlite3.Cursor,
        currency_code: Optional[str],
        country_id: Optional[int] = None,
    ) -> Optional[int]:
        """Resolves or creates currency.id."""
        if not currency_code:
            return None
        cursor.execute(
            'SELECT id FROM "currency" WHERE currency_code = ?', (currency_code,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            'INSERT INTO "currency" (currency_country_id, currency_code) VALUES (?, ?)',
            (country_id, currency_code),
        )
        return cursor.lastrowid

    def persist_statement_transactions(
        self, raw_txns: List[Dict[str, Any]], filename: str
    ) -> None:
        """Writes batch transactions and logs filename in statement_log."""
        self.init_db(filename=filename)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # Verify statement log again before writing
            cursor.execute(
                'SELECT id FROM "statement_log" WHERE filename = ?', (filename,)
            )
            if cursor.fetchone():
                raise ValueError(f"Statement '{filename}' has already been processed.")

            for txn in raw_txns:
                m_name = (
                    txn.get("merchant_name")
                    or txn.get("merchant")
                    or "UNKNOWN"
                )
                cat_id = txn.get("merchant_category_id") or txn.get("category_id") or 1
                m_id = self.get_or_create_merchant(cursor, m_name, cat_id)

                c_code = txn.get("country_code") or txn.get("country")
                c_id = self.get_or_create_country(cursor, c_code)

                curr_code = (
                    txn.get("currency_code")
                    or txn.get("currency")
                    or txn.get("purchase_currency")
                )
                curr_id = self.get_or_create_currency(cursor, curr_code, c_id)

                p_date = txn.get("post_date")
                t_date = txn.get("trans_date") or txn.get("date")
                txn_amt = (
                    txn.get("txn_amount")
                    if "txn_amount" in txn
                    else txn.get("amount")
                )
                hkd_amt = txn.get("hkd_amount")
                fx_rate = txn.get("fx_rate")

                # Explicitly set category_id = NULL on "transaction" record unless explicit override provided
                t_cat_id = txn.get("override_category_id") or txn.get("transaction_category_id")
                if t_cat_id is None and txn.get("is_override"):
                    t_cat_id = txn.get("category_id")

                cursor.execute(
                    """
                    INSERT INTO "transaction" (
                        post_date, trans_date, merchant_id, country_id,
                        purchase_currency_id, txn_amount, hkd_amount, fx_rate, category_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p_date,
                        t_date,
                        m_id,
                        c_id,
                        curr_id,
                        txn_amt,
                        hkd_amt,
                        fx_rate,
                        t_cat_id,
                    ),
                )

            cursor.execute(
                'INSERT INTO "statement_log" (filename) VALUES (?)', (filename,)
            )
            conn.commit()
        finally:
            conn.close()