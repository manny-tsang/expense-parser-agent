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
- **Line 2:** `APPLE PAY-MOBILE:xxxx` (Payment method metadata — **TO BE STRIPPED**).
- **Line 3:** `*EXCHANGE RATE: X.XXXXX` (Capture rate if present).

## 5. Output Schema (CSV)
The resulting dataframe/CSV must contain the following columns:
1. `post_date` (STRING) - e.g., "10JUN"
2. `trans_date` (STRING) - e.g., "06JUN"
3. `merchant` (STRING) - Cleaned merchant name (stripped of location/amount tokens)
4. `aud_amount` (FLOAT, Nullable) - Original transaction value in AUD
5. `hkd_amount` (FLOAT) - Billed transaction value in HKD
6. `fx_rate` (FLOAT, Nullable) - Bank applied exchange rate

## 6. Privacy & Anonymization Requirements
- NO personal account details, full names, card numbers, or address details may be captured or exported.
- Payment token numbers (`APPLE PAY-MOBILE:XXXX`) must be discarded during parsing.