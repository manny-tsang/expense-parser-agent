# Specification: HK Credit Card PDF Statement Parser MVP

## 1. Objective
Extract, clean, and anonymize credit card transaction data from a multi-page bank PDF statement, populate a normalized SQLite database (`db/personal-expense-tracker.db`), and optionally output a structured CSV file locally.

## 2. Environment & Dependencies
- **Language:** Python 3.x
- **Primary Libraries:** `pdfplumber`, `pandas`, `re`, `os`, `typing`
- **Internal Dependencies:** `repository` (`DatabaseRepository`)

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

## 8. Database Architecture & Persistence Contract

- **Database Engine**: SQLite 3 (`db/personal-expense-tracker.db`)
- **Ownership Contract**:
  - `src/pdf_parser.py` MUST NOT contain `CREATE TABLE` statements or define database schemas.
  - All schema definitions, migrations, baseline data seeding, and database connections are exclusively owned by `DatabaseRepository` inside `repository.py`.
  - `HKStatementParser` imports `DatabaseRepository` using standard import/fallback (`try: from src.repository import DatabaseRepository except ImportError: from repository import DatabaseRepository`) to handle reference lookups, entity creation, duplicate checks, and transaction persistence.

### 8.1 Ingestion & Persistence Pipeline
During PDF statement processing (`HKStatementParser.process`):
1. **Repository Instantiation**: Initialize `DatabaseRepository(db_path)`.
2. **Duplicate Statement Check**: Call `repo.init_db(filename)` prior to parsing. If `filename` exists in `statement_log`, it raises `ValueError("Statement '<filename>' has already been processed.")`.
3. **Transaction Ingestion**: Parse PDF text into raw transaction dictionaries (`post_date`, `trans_date`, `merchant`, `country`, `purchase_currency`, `aud_amount`, `hkd_amount`, `fx_rate`).
4. **Exclusion Filtering**: Filter out waived card annual fee reversals and transactions containing `IFS PAYMENT` or `PAYMENT - THANK YOU`.
5. **Batch Persistence**: Pass the cleaned transaction list to `repo.persist_statement_transactions(raw_txns, filename)` to insert records into `merchant`, `country`, `currency`, and `"transaction"` tables in SQLite. `category_id` on the `"transaction"` record MUST be explicitly saved as `NULL` during ingestion so that `merchant.category_id` acts as the single source of truth for baseline categorisation.

### 8.2 Dynamic Database-First Merchant Categorisation Hierarchy

During raw merchant processing and ingestion, resolving `category_id` for a merchant entity MUST evaluate a strict 4-level database-first priority hierarchy prior to inserting new records[cite: 10, 14]:

1. **Level 1 — Exact Database Merchant Lookup**:
   - Query the SQLite `"merchant"` table for an exact match on `merchant_name`[cite: 10, 14].
   - If found, reuse the existing `merchant.id` and retain its currently mapped `category_id`[cite: 10, 14]. This guarantees that all custom merchant category mappings previously saved via the Categorise UI are strictly preserved during subsequent PDF uploads[cite: 11, 14].

2. **Level 2 — Dynamic Database Pattern Search**:
   - If `merchant_name` does not exist in `"merchant"`, evaluate the string against existing mapped merchants in SQLite using SQL wildcard substring matching (`LIKE '%' || pattern || '%'`)[cite: 10, 14].
   - If a matching pattern is found in SQLite, assign the mapped `category_id` to the new merchant record[cite: 10, 14].

3. **Level 3 — Static Keyword Dictionary Fallback**:
   - If neither exact nor pattern matches exist in SQLite, evaluate `merchant_name` against the static default keyword rules[cite: 10, 14]:
     - **Automotive**: `MEEK AUTOMOTIVE`, `SHANNONS`, `SUPERCHEAP AUTO`, `AUTOMOTIVE`, `MECHANIC`[cite: 10, 14]
     - **Bank Fees**: `DCC FEE`, `FOREIGN TRANSACTION FEE`, `LATE FEE`, `INTEREST CHARGE`[cite: 10, 14]
     - **Dining & Cafes**: `24 YORK`, `BARE WITNESS`, `BAMBOO SUSHI`, `BY V BAR`, `CONCORDIA CLUB`, `CHARGRILL OLYMPICPARK`, `EL JANNAH`, `GYUKATSU KYOTO`, `HASHI SUSHI`, `HIN TEE CHOO`, `HOONSIKDANG`, `KFC`, `MESSIN`, `SIMPLE SIMONS GELATO`, `SQ *ANGUS MARRICKVILLE`, `SQ *BELLA BACIATA`, `SQ *GOOD FELLA`, `SQ *GUMPTION`, `SQ *HEADLANDS`, `SQ *KABUL SOCIAL`, `SQ *LAB RHODES`, `SQ *MAMUKI`, `SQ *THE BERLIN FOOD`, `SQ *YUMYUM`, `THE LUCKY PLACE`, `THE MAJOR HABERFIELD`, `THE LONDON HOTEL`, `UNCLE TETSU`, `GELATO`, `GYG`, `CAFE`, `RESTAURANT`, `COFFEE`, `BAKERY`, `PATISSERIE`, `MCDONALD`[cite: 10, 14]
     - **Fuel**: `BP `, `BP CONNECT`, `SHELL`, `AMPOL`, `7-ELEVEN`, `UNITED PETROLEUM`, `CALTEX`[cite: 10, 14]
     - **Groceries**: `WOOLWORTHS`, `COLES`, `ALDI`, `PETBARN`, `ZETCITI`, `SUPERMARKET`, `IGAMARKET`, `GROCER`[cite: 10, 14]
     - **Haircut**: `SQ *STUDIO NO. 4`, `BARBER`, `HAIR`, `SALON`[cite: 10, 14]
     - **Health & Fitness**: `ADRENALINE HQ`, `CHEMIST WAREHOUSE`, `EZI*DYNASTY`, `KAPNOR`, `GYM`, `PHARMACY`, `CHEMIST`, `HEALTH`, `FITNESS`[cite: 10, 14]
     - **Medical**: `SHIM SZE EIN`, `DOCTOR`, `CLINIC`, `DENTAL`, `MEDICAL`[cite: 10, 14]
     - **Pet**: `PETBARN`, `VET`[cite: 10, 14]
     - **Shopping & Retail**: `AMAZON`, `AQUILA`, `KIEHLS`, `REBEL`, `UNIQLO`, `BUNNINGS`, `KMART`, `TARGET`, `APPLE`[cite: 10, 14]
     - **Subscriptions**: `CANVA`, `NETFLIX`, `PDF.NET`, `SPOTIFY`, `APPLE.COM/BILL`, `YOUTUBE`, `PRIME`, `DISNEY`[cite: 10, 14]
     - **Transport**: `OPAL`, `PARKING`, `UBER`, `TAXI`, `TRANSPORT`, `TRANSIT`[cite: 10, 14]
     - **Utilities**: `TELSTRA`, `OPTUS`, `ENERGY`, `WATER`, `AANET`, `AGL`, `ORIGIN`[cite: 10, 14]

4. **Level 4 — Default Fallback**:
   - If no database entity, database pattern, or static dictionary rule matches, set `category_id = 1` (`Uncategorised`) on the new `merchant` entity record[cite: 10, 14].

*Note: The categorisation logic assigns `category_id` strictly at the `merchant` entity level upon creation. Individual `"transaction"` records inherit this mapping via database joins and remain `category_id = NULL` at ingestion time.*[cite: 10, 14]