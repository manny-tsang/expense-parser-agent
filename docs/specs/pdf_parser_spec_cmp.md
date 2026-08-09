# Specification: HK Credit Card PDF Statement Parser MVP

## 1. Objective
Extract, clean, and anonymize credit card transaction data from a multi-page bank PDF statement and output a structured CSV file locally.

## 2. Environment & Dependencies
- **Language:** Python 3.x
- **Primary Libraries:** `pdfplumber`, `pandas`, `re`

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

### Monetary Value & Exchange Rate Formatting
* **Dollar Formatting:** Prepend a `$` sign to monetary values in `aud_amount` and `hkd_amount` formatted to 2 decimal places with commas (e.g., `$180.00`, `$1,015.72`). If `aud_amount` is missing for a native HKD transaction, leave the cell empty.
* **Exchange Rate (`fx_rate`):** Preserve raw numeric decimal values (e.g., `5.64289`) without a `$` sign.

### Function Interface Contract
* Module Entry Point: `parse_statement(pdf_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame`

---

## 7. Privacy & Anonymization Requirements
- NO personal account details, full names, card numbers, or address details may be captured or exported.
- Payment token numbers (`APPLE PAY-MOBILE:XXXX`) must be discarded during parsing.