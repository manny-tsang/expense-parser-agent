# Specification: Centralized Database Repository Layer

## 1. Objective
AS A Personal Tracker System Component  
I WANT TO centralize all SQLite schema management, reference data seeding, and CRUD database operations into a dedicated module (`src/repository.py`)  
SO THAT both the PDF parser engine (`src/pdf_parser.py`) and Streamlit presentation layer (`src/app.py`) can execute database interactions through a single, clean, decoupled repository interface without duplicating schema definitions or import fallback logic.

## 2. Technical Stack & Dependencies
- **Language**: Python 3.x
- **Database Engine**: SQLite 3 (`sqlite3`)
- **Data Processing & Typing**: `pandas`, `typing` (`List`, `Dict`, `Tuple`, `Optional`, `Union`, `Any`)
- **Target File**: `src/repository.py`
- **Database Target File Path**: `db/personal-expense-tracker.db`

---

## 3. Jira Automation & Story Backlog Definitions

- **Project Key**: `PET`
- **Prefix Standard**: `[ TOUCHPOINT_1 | TOUCHPOINT_2 | ... ] Story Title` (Front-to-Back: `UI` -> `PY` -> `API` -> `DB`)
- **Epic Mapping**: Links directly as a child story to existing Epic **`PET-3`** (`Categorise Transactions`)

### Story Definition
**Target Epic**: `PET-3`  
**Title**: `[ PY | DB ] Centralized Database Repository Layer Refactoring`

**Description**:
AS A Personal Tracker System Component  
I WANT TO extract all SQLite schema definitions, reference data seeding, and database CRUD methods from `pdf_parser.py` and `app.py` into `src/repository.py`  
SO THAT all data access is managed through a Single Source of Truth without duplicate fallback classes or brittle multi-tier import logic.

Acceptance Criteria:

Scenario 1: Dedicated Repository Class  
GIVEN the application starts up or parses a statement  
WHEN database interactions are executed  
THEN `DatabaseRepository` inside `src/repository.py` owns all connection lifecycles, table creations, baseline data seeding, and queries.

Scenario 2: Decoupled Parser & Presentation Layers  
GIVEN `src/pdf_parser.py` and `src/app.py` require database operations  
WHEN they execute reads or writes  
THEN both modules import `DatabaseRepository` directly from `src.repository` without defining mock fallback classes or duplicate inline DDL statements.

---

## 4. Database Schema Reference (`db/personal-expense-tracker.db`)

The `DatabaseRepository` class inside `src/repository.py` exclusively owns database initialization, table creation DDLs, and reference data migrations.

### 4.1 Entity-Relationship Schema Definitions

```sql
CREATE TABLE IF NOT EXISTS "category" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS "country" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_name TEXT UNIQUE,
    country_code TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS "currency" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency_country_id INTEGER,
    currency_code TEXT UNIQUE,
    FOREIGN KEY(currency_country_id) REFERENCES "country"(id)
);

CREATE TABLE IF NOT EXISTS "merchant" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_name TEXT UNIQUE NOT NULL,
    category_id INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(category_id) REFERENCES "category"(id)
);

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

CREATE TABLE IF NOT EXISTS "statement_log" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 Idempotent Baseline Reference Data Seeding

Upon database initialization, execute `INSERT OR IGNORE` to guarantee baseline seed entries:

1. **Category Table**:
   - Seed `(1, 'Uncategorised')` first as the default category.
   - Seed remaining canonical categories: `Automotive`, `Bank Fees`, `Dining & Cafes`, `Fuel`, `Groceries`, `Haircut`, `Health & Fitness`, `Medical`, `Pet`, `Shopping & Retail`, `Subscriptions`, `Transport`, `Utilities`.

2. **Country Table**:
   Seed the exact list of 45 ISO countries:
   `(1, 'Austria', 'AT')`, `(2, 'Australia', 'AU')`, `(3, 'Belgium', 'BE')`, `(4, 'Bulgaria', 'BG')`, `(5, 'Canada', 'CA')`, `(6, 'China', 'CN')`, `(7, 'Croatia', 'HR')`, `(8, 'Cyprus', 'CY')`, `(9, 'Czech Republic', 'CZ')`, `(10, 'Denmark', 'DK')`, `(11, 'Estonia', 'EE')`, `(12, 'Finland', 'FI')`, `(13, 'France', 'FR')`, `(14, 'Germany', 'DE')`, `(15, 'Greece', 'GR')`, `(16, 'Hong Kong', 'HK')`, `(17, 'Hungary', 'HU')`, `(18, 'India', 'IN')`, `(19, 'Indonesia', 'ID')`, `(20, 'Ireland', 'IE')`, `(21, 'Italy', 'IT')`, `(22, 'Japan', 'JP')`, `(23, 'Latvia', 'LV')`, `(24, 'Lithuania', 'LT')`, `(25, 'Luxembourg', 'LU')`, `(26, 'Malaysia', 'MY')`, `(27, 'Malta', 'MT')`, `(28, 'Netherlands', 'NL')`, `(29, 'New Zealand', 'NZ')`, `(30, 'Philippines', 'PH')`, `(31, 'Poland', 'PL')`, `(32, 'Portugal', 'PT')`, `(33, 'Romania', 'RO')`, `(34, 'Singapore', 'SG')`, `(35, 'Slovakia', 'SK')`, `(36, 'Slovenia', 'SI')`, `(37, 'South Korea', 'KR')`, `(38, 'Spain', 'ES')`, `(39, 'Sweden', 'SE')`, `(40, 'Switzerland', 'CH')`, `(41, 'Taiwan', 'TW')`, `(42, 'Thailand', 'TH')`, `(43, 'United Kingdom', 'GB')`, `(44, 'United States', 'US')`, `(45, 'Vietnam', 'VN')`.

3. **Currency Table**:
   Seed the exact list of 45 currency mapping pairs `(currency_country_id, currency_code)`:
   `(1, 'EUR')`, `(2, 'AUD')`, `(3, 'EUR')`, `(4, 'BGN')`, `(5, 'CAD')`, `(6, 'CNY')`, `(7, 'EUR')`, `(8, 'EUR')`, `(9, 'CZK')`, `(10, 'DKK')`, `(11, 'EUR')`, `(12, 'EUR')`, `(13, 'EUR')`, `(14, 'EUR')`, `(15, 'EUR')`, `(16, 'HKD')`, `(17, 'HUF')`, `(18, 'INR')`, `(19, 'IDR')`, `(20, 'EUR')`, `(21, 'EUR')`, `(22, 'JPY')`, `(23, 'EUR')`, `(24, 'EUR')`, `(25, 'EUR')`, `(26, 'MYR')`, `(27, 'EUR')`, `(28, 'EUR')`, `(29, 'NZD')`, `(30, 'PHP')`, `(31, 'PLN')`, `(32, 'EUR')`, `(33, 'RON')`, `(34, 'SGD')`, `(35, 'EUR')`, `(36, 'EUR')`, `(37, 'KRW')`, `(38, 'EUR')`, `(39, 'SEK')`, `(40, 'CHF')`, `(41, 'TWD')`, `(42, 'THB')`, `(43, 'GBP')`, `(44, 'USD')`, `(45, 'VND')`.

---

## 5. Class Interface & Method Contracts (`DatabaseRepository`)

The `DatabaseRepository` class inside `src/repository.py` must expose the following complete interface:

### 5.1 Connection & Schema Operations
- `__init__(self, db_path: str = "db/personal-expense-tracker.db")`: Initializes target DB path and ensures parent directories exist.
- `get_connection(self) -> sqlite3.Connection`: Creates parent directory if missing and returns an active `sqlite3.Connection`.
- `init_db(self, filename: Optional[str] = None) -> None`: Executes table creation DDLs and baseline seeding logic. If `filename` is provided, verifies it does not already exist in `statement_log` (raising `ValueError(f"Statement '{filename}' has already been processed.")` if found).

### 5.2 Query & Read Contracts
- `get_transactions_dataframe(self) -> pd.DataFrame`: Returns a DataFrame containing all transactions joined with `merchant`, `category` (supporting transaction-level override via `COALESCE(override_cat.category_name, default_cat.category_name)`), and `currency`. Output columns: `id`, `trans_date`, `merchant`, `category_name`, `txn_amount`, `purchase_currency`, `hkd_amount`, `fx_rate`, `category_id`.
- `get_categories(self) -> pd.DataFrame`: Returns DataFrame of all categories (`id`, `category_name`) ordered by `category_name ASC`.
- `get_merchants(self) -> pd.DataFrame`: Returns DataFrame of ALL merchants joined with their mapped category name (`merchant_id`, `merchant_name`, `category_id`, `category_name`) ordered by `merchant_name ASC`.
- `get_uncategorised_merchants(self) -> pd.DataFrame`: Returns DataFrame of distinct merchants where `m.category_id = 1` AND `t.category_id IS NULL`, grouped with `transaction_count`. Output columns: `merchant_id`, `merchant_name`, `transaction_count`.
- `match_merchant_category_pattern(self, merchant_name: str) -> Optional[int]`: 
  Evaluates `merchant_name` against mapped merchants in SQLite using SQL substring matching (`WHERE category_id != 1 AND UPPER(?) LIKE '%' || UPPER(merchant_name) || '%'`). Returns the matching `category_id` if found, otherwise `None`.

### 5.3 Write & Update Contracts
- `add_category(self, category_name: str) -> bool`: Inserts a new category into `"category"`. Returns `True` on success, `False` on failure.
- `update_merchant_category(self, merchant_id_or_name: Union[int, str], category_id: int) -> bool`: Updates `category_id` on `merchant` record by `id` or `merchant_name`. Returns `True` on success.
- `update_transaction_category(self, transaction_id: int, category_id: int) -> bool`: Updates `category_id` directly on `"transaction"` row for explicit overrides. Returns `True` on success.
- `get_or_create_merchant(self, cursor: sqlite3.Cursor, merchant_name: str, cat_id: int) -> int`: Retrieves existing `merchant.id` or inserts a new merchant row with `cat_id`.
- `get_or_create_country(self, cursor: sqlite3.Cursor, country_code: Optional[str]) -> Optional[int]`: Resolves or creates `country.id`.
- `get_or_create_currency(self, cursor: sqlite3.Cursor, currency_code: Optional[str], country_id: Optional[int]) -> Optional[int]`: Resolves or creates `currency.id`.
- `persist_statement_transactions(self, raw_txns: List[Dict[str, Any]], filename: str) -> None`: Writes batch transactions and logs `filename` in `statement_log`. Explicitly sets `category_id = NULL` on the `"transaction"` record unless an explicit override is provided, ensuring `merchant.category_id` controls the default baseline categorisation.

### 5.4 SQL Identifier & Python String Escaping Rules
- **Reserved Keyword Escaping**: The table `"transaction"` is an SQLite reserved keyword. All DDL and DML queries MUST enclose the table name in double quotes (`"transaction"`).
- **Python String Safety**: When embedding SQL queries in Python triple-quoted strings inside `src/repository.py`, use clean double quotes (`"transaction"`) without nesting single quotes (e.g., write `FROM "transaction" t`, NEVER `FROM "'transaction'" t`).