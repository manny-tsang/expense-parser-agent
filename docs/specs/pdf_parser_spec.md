# Specification: HK Credit Card PDF Statement Parser MVP

## 1. Objective
Extract, clean, and anonymize credit card transaction data from a multi-page bank PDF statement, populate a normalized SQLite database (`db/personal-expense-tracker.db`), and optionally output a structured CSV file locally.

## 2. Environment & Dependencies
- **Language:** Python 3.x
- **Primary Libraries:** `pdfplumber`, `pandas`, `sqlite3`, `re`, `os`

## 3. Page Routing & Anchors

### Page 1 (Hybrid Summary & Partial Transactions)
- **Start Anchor:** Table Header (`Post date` / `Trans date` / `Description of transaction`).
- **Stop Anchor:** Stop parsing immediately when hitting `MINIMUM PAYMENT SUMMARY` or `SUMMARY 戶口概要`.
- **Exclusion Rule:** Ignore rows containing `PREVIOUS BALANCE` or `上月結欠/結餘`.

### Page 2 (Terms & Marketing Insert)
- **Skip Rule:** Skip Page 2 completely.

### Page 3+ (Continuation Pages)
- **Process Rule:** Read standard full-page transaction tables top-to-bottom.
- **Global Stop Anchor:** Terminate parsing entirely upon reading:
  `*FOR CREDIT CARD TRANSACTIONS EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS`

## 4. Multi-Line Transaction Logic
A single transaction spans 3 distinct visual lines in the PDF table:
- **Line 1:** `Post Date`, `Trans Date`, `Merchant Description`, `Suburb`, `Country`, `AUD Amount` (if FX), `HKD Amount`.
- **Line 2:** `APPLE PAY-MOBILE:xxxx` (Payment method metadata — **TO BE STRIPPED/DISCARDED**).
- **Line 3:** `*EXCHANGE RATE: X.XXXXX` (Capture rate if present).

## 5. Output Schema & CSV Headers
The resulting dataframe/CSV must contain the following exact header columns in this order:
`post_date,trans_date,merchant,country,purchase_currency,aud_amount,hkd_amount,fx_rate`

---

## 6. Detailed Field Formatting & Extraction Rules

### Statement Period & Date Formatting
* **Statement Date Header Extraction:**
  1. Search Page 1 for the dual-language anchor `Statement date` / `結單日`.
  2. Inspect that line and the following line for `\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b` (e.g., `07 JUL 2026`) to extract `statement_year` (e.g., `2026`) and `statement_month` (e.g., `7`).
* **Raw Date Extraction Rule:**
  * In the raw PDF text stream, day digits and month characters appear directly adjacent with no spaces (e.g., `09JUN` instead of `09 JUN`).
  * Regex patterns matching raw date tokens MUST handle optional whitespace between digits and month characters using `\s*` (e.g., `\d{1,2}\s*[A-Za-z]{3}`).
* **Transaction Date Output Format:**
  * Convert all extracted transaction dates to `DD-MM-YYYY` (e.g., `16-06-2026`).
* **Cross-Year Boundary Rule:**
  * Assign `statement_year` to transaction dates. If a transaction month (e.g., `DEC` / `12`) is numerically greater than `statement_month` (e.g., `JAN` / `1`), infer the transaction year as `statement_year - 1` (e.g., `2025`).

### Merchant String & Location Cleaning
* **Clean Merchant Name (`merchant`):** Strip trailing country codes (e.g., `AU`, `US`, `SG`), currency codes (`AUD`, `USD`), and city/suburb names from the raw merchant text to isolate the business name (e.g., `"WOOLWORTHS/6-14 WALKER ST RHODES AU AUD"` becomes `"WOOLWORTHS/6-14 WALKER ST RHODES"`).
* **Country (`country`):** Extract two-letter ISO country codes printed near the end of transaction lines (e.g., `AU`, `US`, `SG`).
* **Purchase Currency (`purchase_currency`):** Extract the explicit currency code if present (`AUD`, `USD`, etc.).

### Edge Case Handling
* **Native HKD Foreign Transactions (e.g., Netflix SG):** If a country code is present (e.g., `SG`) but no foreign currency or exchange rate is listed because billing occurred directly in HKD, populate `purchase_currency` as `HKD`.
* **Bank Fees & Adjustments (e.g., DCC FEE-NON-HK MERCHANT):** If no physical location or country code is printed on the statement for bank fees, default `country` to `HK` and `purchase_currency` to `HKD`.
* **Waived Card Annual Fee Reversals:** If a `CARD ANNUAL FEE` transaction is immediately followed by an `ANNUAL FEE REFUND` transaction (or vice-versa on the same date with matching amounts), both transactions MUST be suppressed/discarded during parsing and excluded from database insertion.

### Monetary Value & Exchange Rate Formatting
* **Dollar Formatting:** Prepend a `$` sign to monetary values in `aud_amount` and `hkd_amount` formatted to 2 decimal places with commas (e.g., `$180.00`, `$1,015.72`). If `aud_amount` is missing for a native HKD transaction, leave the cell empty.
* **Exchange Rate (`fx_rate`):** Preserve raw numeric decimal values (e.g., `5.64289`) without a `$` sign.

### Function Interface Contract
* Module Entry Point: `parse_statement(pdf_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame`

---

## 7. Privacy & Anonymization Requirements
- NO personal account details, full names, card numbers, or address details may be captured or exported.
- Payment token numbers (`APPLE PAY-MOBILE:XXXX`) must be discarded during parsing.

---

## 8. Database Schema & Persistence Target

- **Engine**: SQLite 3
- **File Location**: `db/personal-expense-tracker.db`

### 8.1 Entity-Relationship Structure

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

### 8.2 Baseline Reference Data Seeding Logic
Upon initializing the database connection, execute idempotent seeding (`INSERT OR IGNORE`) for baseline lookup values:

```sql
-- Always seed default 'Uncategorised' first to guarantee category_id = 1
INSERT OR IGNORE INTO "category" ("id", "category_name") VALUES (1, 'Uncategorised');

-- Populate Remaining Categories
INSERT OR IGNORE INTO "category" ("category_name") VALUES 
('Automotive'),
('Bank Fees'),
('Dining & Cafes'),
('Fuel'),
('Groceries'),
('Haircut'),
('Health & Fitness'),
('Medical'),
('Shopping & Retail'),
('Subscriptions'),
('Transport'),
('Utilities');

-- Populate Countries
INSERT OR IGNORE INTO "country" ("id", "country_name", "country_code") VALUES 
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
(45, 'Vietnam', 'VN');

-- Populate Currencies
INSERT OR IGNORE INTO "currency" ("currency_country_id", "currency_code") VALUES 
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
(45, 'VND');
```

### 8.3 Duplicate Statement Prevention Logic
- Before parsing or inserting transactions from a statement file, check if the baseline filename (e.g., `2026-01-08_Statement.pdf`) exists in `statement_log`.
- If the filename exists in `statement_log`, raise a `ValueError` with `"Statement '<filename>' has already been processed."`.
- If it does not exist, insert the filename into `statement_log` upon successful ingestion.

### 8.4 Exclusion Filter Rules
Before inserting into the database, the parser MUST filter out and discard any transaction where the raw merchant string contains:
- `IFS PAYMENT`
- `PAYMENT - THANK YOU`

### 8.5 Auto-Categorisation Engine & Merchant Creation Rules
When a clean `merchant_name` string is extracted during PDF parsing:
1. **Merchant Entity Resolution**: Check if the `merchant_name` exists in the `merchant` table.
2. **Auto-Categorisation Evaluation**: If the merchant does not exist in the `merchant` table, evaluate the `merchant_name` string against default keyword rules:
   - **Automotive**: `MEEK AUTOMOTIVE`, `SHANNONS`, `SUPERCHEAP AUTO`, `AUTOMOTIVE`, `MECHANIC`
   - **Bank Fees**: `DCC FEE`, `FOREIGN TRANSACTION FEE`, `LATE FEE`, `INTEREST CHARGE`
   - **Dining & Cafes**: `24 YORK`, `BARE WITNESS`, `BAMBOO SUSHI`, `BY V BAR`, `CONCORDIA CLUB`, `CHARGRILL OLYMPICPARK`, `EL JANNAH`, `GYUKATSU KYOTO`, `HASHI SUSHI`, `HIN TEE CHOO`, `HOONSIKDANG`, `KFC`, `MESSIN`, `SIMPLE SIMONS GELATO`, `SQ *ANGUS MARRICKVILLE`, `SQ *BELLA BACIATA`, `SQ *GOOD FELLA`, `SQ *GUMPTION`, `SQ *HEADLANDS`, `SQ *KABUL SOCIAL`, `SQ *LAB RHODES`, `SQ *MAMUKI`, `SQ *THE BERLIN FOOD`, `SQ *YUMYUM`, `THE LUCKY PLACE`, `THE MAJOR HABERFIELD`, `THE LONDON HOTEL`, `UNCLE TETSU`, `GELATO`, `GYG`, `CAFE`, `RESTAURANT`, `COFFEE`, `BAKERY`, `PATISSERIE`, `MCDONALD`
   - **Fuel**: `BP `, `BP CONNECT`, `SHELL`, `AMPOL`, `7-ELEVEN`, `UNITED PETROLEUM`, `CALTEX`
   - **Groceries**: `WOOLWORTHS`, `COLES`, `ALDI`, `PETBARN`, `ZETCITI`, `SUPERMARKET`, `IGAMARKET`, `GROCER`
   - **Haircut**: `SQ *STUDIO NO. 4`, `BARBER`, `HAIR`, `SALON`
   - **Health & Fitness**: `ADRENALINE HQ`, `CHEMIST WAREHOUSE`, `EZI*DYNASTY`, `KAPNOR`, `GYM`, `PHARMACY`, `CHEMIST`, `HEALTH`, `FITNESS`
   - **Medical**: `SHIM SZE EIN`, `DOCTOR`, `CLINIC`, `DENTAL`, `MEDICAL`
   - **Shopping & Retail**: `AMAZON`, `AQUILA`, `KIEHLS`, `REBEL`, `UNIQLO`, `BUNNINGS`, `KMART`, `TARGET`, `APPLE`
   - **Subscriptions**: `CANVA`, `NETFLIX`, `PDF.NET`, `SPOTIFY`, `APPLE.COM/BILL`, `YOUTUBE`, `PRIME`, `DISNEY`
   - **Transport**: `OPAL`, `PARKING`, `UBER`, `TAXI`, `TRANSPORT`, `TRANSIT`
   - **Utilities**: `TELSTRA`, `OPTUS`, `ENERGY`, `WATER`, `AANET`, `AGL`, `ORIGIN`
   - **Fallback**: Unmatched new merchants default to `category_id = 1` (`Uncategorised`).
3. **Insertion**: Insert the new record into `merchant` with its resolved `category_id` and obtain its `merchant_id`.

### 8.6 Foreign Key Resolution Logic
1. For `merchant_id`: Retrieve or create the corresponding `id` from the `merchant` table.
2. For `purchase_currency_id`: Query `currency` table for `currency_code` (e.g., `AUD`). If not found, insert and retrieve new `id`.
3. For `country_id`: Query `country` table for `country_code` (e.g., `AUS` / `AU`). If not found, insert and retrieve new `id`. If null/empty, store `NULL`.
4. For `category_id`: On `transaction`, leave as `NULL` unless explicitly overridden.