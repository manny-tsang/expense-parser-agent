Refinement Pass: 1

## 0. Questions & Clarification Needed for Human Sign-Off

- **Question**: Should single-currency categories adopt the explicit `<category> (Currency)` naming convention in the primary summary table, or retain the raw `<category>` string?
  - **Justification & Impact**: Section 3.2.1 specifies that multi-currency categories split into `<category> (Currency)` rows, but section 3.3.1 mandates strict column alignment for CSV export. Inconsistent row labeling will break spreadsheet parsing and regex filters in external export automation scripts.
  - **Proposed Default / Response**: Standardize all row labels to always follow `<category> (Currency)` (e.g., `Groceries (AUD)`, `Dining (HKD)`) regardless of whether the category spans single or multiple currencies, ensuring deterministic CSV structure.

- **Question**: How should refund / credit line items with positive net balances in a lookback window interact with global average totals?
  - **Justification & Impact**: If a category receives a massive refund in AUD (e.g., -$2,000.00 AUD) and no other spending, its monthly average could result in a negative float value. This impacts target budget defaulting and total spend summations.
  - **Proposed Default / Response**: If `Historical Monthly Avg (Currency)` evaluates to a negative value due to net refunds, set the initial default `Target Monthly Budget (Currency)` to `0.00` while preserving the actual calculated negative float in `Historical Monthly Avg (Currency)`.

- **Question**: Does the transient outlier threshold slider filter transactions prior to computing the global distinct month denominator ($N_{months}$), or is $N_{months}$ determined independently before outlier suppression?
  - **Justification & Impact**: If a calendar month contains *only* a single transaction that exceeds the outlier threshold, suppressing that transaction could reduce $N_{months}$ from 3 to 2, altering baseline calculations across *all* unaffected categories.
  - **Proposed Default / Response**: Compute $N_{months}$ strictly based on the presence of valid ledger transactions in the calendar month prior to applying the transient UI outlier filter, ensuring the denominator remains immutable across slider adjustments.

---

## 1. Module Overview & Primary Intent
- **Epic Title**: HK Card Budget Projection Engine
- **Epic Description**: As a Personal Expense Tracker user, I want a forward-looking budget planning engine to compute rolling spend baselines across multi-currency accounts (AUD, HKD, USD), suppress transaction outliers, set target category allocations, and export summaries to external spreadsheets.

---

## 2. Module Boundaries & Ownership Contracts
- **Primary Source Files**: 
  - `src/app.py`: Presentation layer, Streamlit UI controls, interactive target input fields, and `st.column_config` data table renderings.
  - `src/repository.py`: Business logic, historical aggregations, global distinct month calculation, transient outlier filtering, and data aggregation contracts.
- **Allowed Dependencies**: `pandas`, `sqlite3`, `streamlit`, `DatabaseRepository`.
- **Forbidden Operations**: 
  - Presentation layer (`src/app.py`) MUST NOT write raw SQL queries directly or execute database modifications.
  - Projections and baseline calculations MUST NOT modify persistent transaction records in SQLite.
  - Cross-currency dynamic FX conversion at runtime is strictly prohibited; baseline averages and targets must be kept isolated per currency code (`AUD`, `HKD`, `USD`).

---

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Historical Baseline & Rolling Averages
1. **Window Selection**:
   - The user selects a historical lookback window from pre-defined options: `Trailing 3 Months`, `Trailing 6 Months`, or `Trailing 12 Months`.
2. **Partial Lookback Window & Global Distinct Month Handling**:
   - A **Distinct Month** is defined as a unique `YYYY-MM` calendar period containing at least one valid non-outlier transaction in the database ledger.
   - The distinct month count denominator ($N_{months}$) is calculated globally across the database for the selected window.
   - If $N_{months}$ is less than the selected lookback window size (e.g., 2 distinct months exist for a 3-month window), calculate monthly averages using $N_{months}$ as the denominator and display an inline UI warning badge:  
     `⚠️ Partial history: Calculation based on N distinct month(s)`
   - If $N_{months} = 0$, set $N_{months} = 1$ for baseline calculations, default all category averages to `0.00`, and render an inline UI informational badge:  
     `ℹ️ No historical transactions found in selected window`
   - Categories with zero transactions within the selected window must default `Historical Monthly Avg` to `0.00` across all currencies.
3. **Base Currency & Multi-Currency Isolation**:
   - The primary reporting currency across ledger views is `AUD`.
   - Baseline aggregations evaluate stored native currency amounts directly (`AUD`, `HKD`, `USD`) without applying runtime FX conversions.
4. **Outlier Suppression & Native Currency Limits**:
   - Outlier exclusion threshold is transient, configurable via a UI slider ($0.00 to $100,000.00 AUD, defaulting to $1,000.00 AUD). Setting the slider to $0.00 disables outlier suppression completely.
   - Suppression applies ONLY to transactions that possess a native AUD amount.
   - Non-AUD transactions (e.g., native HKD or USD line items) MUST NOT be converted to AUD to test threshold exclusion; non-AUD items are never suppressed by the AUD threshold slider.
   - An AUD transaction line item is excluded from baseline calculations if:  
     $\text{Amount}_{\text{AUD}} \ge \text{Threshold}_{\text{Slider}}$
   - The UI MUST display the explicit notice:  
     `"Transactions performed in AUD above the set threshold are excluded from projection calculations."`
   - If all transactions for a category within a month are suppressed as outliers, treat that category's monthly spend as `0.00` while preserving the global $N_{months}$ denominator.
5. **Refunds and Credit Line Items**:
   - Negative transactions (credits/refunds) are included in net category monthly sums unless their absolute magnitude triggers the outlier suppression rule (i.e., $|\text{Amount}_{\text{AUD}}| \ge \text{Threshold}_{\text{Slider}}$).

### 3.2 Target Budget Allocation & Interactive Overrides
1. **Default State**:
   - Upon initial load or lookback window change, `Target Monthly Budget (Currency)` for AUD, HKD, and USD defaults to the calculated `Historical Monthly Avg (Currency)`.
   - **Multi-Currency Category Decomposition**: Categories spanning transactions in multiple currencies render as distinct rows suffixed with the currency code: `<Category> (Currency)` (e.g., `Groceries (AUD)`, `Groceries (HKD)`).
   - In currency-specific category rows, column values for unassociated currencies MUST be set to `0.00`.
2. **Multi-Currency UI Adjustments**:
   - Render independent numeric input fields for target monthly allocations per row in `src/app.py`.
   - Target inputs must be non-negative real numbers ($\ge 0.00$).
   - If a user inputs a negative value or invalid text string, display an inline validation message (`"Target budget must be >= 0.00"`) and revert target to `0.00`.
   - Explicit input of `0.00` is valid and represents intentional budget phase-out.
3. **Summary Aggregation**:
   - System updates live dynamic sums for `Total Projected Monthly Spend (AUD)`, `Total Projected Monthly Spend (HKD)`, and `Total Projected Monthly Spend (USD)`.

### 3.3 Google Sheets Transfer Summary & Export Formats

#### 3.3.1 Summary Data Structure & Schema
The exported and displayed summary table strictly adheres to the following 7-column schema:
1. `Category` (Text)
2. `Historical Monthly Avg (AUD)` (Float64)
3. `Historical Monthly Avg (HKD)` (Float64)
4. `Historical Monthly Avg (USD)` (Float64)
5. `Target Monthly Budget (AUD)` (Float64)
6. `Target Monthly Budget (HKD)` (Float64)
7. `Target Monthly Budget (USD)` (Float64)

- A appended read-only summary row labeled `Total` must calculate column sums across all active category rows.
- CSV export outputs must preserve exact category row labels and include the appended `Total` row.

#### 3.3.2 Streamlit Rendering & Export Options
1. Rendered via `st.dataframe`.
2. Native pandas DataFrame underlying types must remain `float64` rounded to 2 decimal places.
3. Visual formatting uses `st.column_config.NumberColumn(format="$%.2f")`.
4. Enables Streamlit native CSV download, column sorting, and text filtering.

---

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Calculate Category Baseline Averages with Partial Window Handling
**AS A** personal expense tracker user,  
**I WANT TO** select a historical lookback window and outlier threshold,  
**SO THAT** I can view normalized baseline monthly averages per category isolated by currency.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Historical Category Baseline Calculation

  Background:
    Given the database ledger contains historical transaction records:
      | Transaction ID | Date       | Category  | Currency | Amount   |
      | TXN-101        | 2023-10-15 | Groceries | AUD      | 150.00   |
      | TXN-102        | 2023-10-20 | Groceries | AUD      | 1200.00  |
      | TXN-103        | 2023-11-10 | Groceries | AUD      | 200.00   |
      | TXN-104        | 2023-11-12 | Dining    | HKD      | 500.00   |
      | TXN-105        | 2023-11-15 | Groceries | USD      | 80.00    |

  Scenario Outline: Calculating baseline averages across different lookback windows with outlier filtering
    Given the user sets the historical lookback window to "<lookback_window>"
    And the user sets the transient outlier slider threshold to <outlier_threshold>
    When the baseline computation engine aggregates transaction records
    Then the calculated distinct month denominator N_months should be <expected_n_months>
    And the baseline projection summary table should contain the calculated averages:
      | Category        | Historical Monthly Avg (AUD) | Historical Monthly Avg (HKD) | Historical Monthly Avg (USD) |
      | Groceries (AUD) | <expected_groceries_aud>    | 0.00                         | 0.00                         |
      | Groceries (USD) | 0.00                         | 0.00                         | <expected_groceries_usd>     |
      | Dining (HKD)    | 0.00                         | <expected_dining_hkd>        | 0.00                         |
    And the UI warning badge display status should be "<expected_badge>"

    Examples:
      | lookback_window    | outlier_threshold | expected_n_months | expected_groceries_aud | expected_groceries_usd | expected_dining_hkd | expected_badge                                           |
      | Trailing 3 Months  | 1000.00           | 2                 | 175.00                 | 40.00                  | 250.00              | ⚠️ Partial history: Calculation based on 2 distinct month(s) |
      | Trailing 3 Months  | 0.00              | 2                 | 775.00                 | 40.00                  | 250.00              | ⚠️ Partial history: Calculation based on 2 distinct month(s) |
      | Trailing 6 Months  | 1000.00           | 2                 | 175.00                 | 40.00                  | 250.00              | ⚠️ Partial history: Calculation based on 2 distinct month(s) |

  Scenario: Zero transaction history handling in selected lookback window
    Given an empty transaction ledger for the timeframe "Trailing 12 Months"
    When the baseline computation engine aggregates transaction records
    Then the global distinct month denominator N_months should default to 1
    And all category historical monthly averages should evaluate to 0.00
    And the UI should display the badge "ℹ️ No historical transactions found in selected window"
```

---

### Story 2: Outlier Suppression and Native Currency Isolation
**AS A** personal expense tracker user,  
**I WANT** transient outlier threshold controls to filter AUD transactions exclusively,  
**SO THAT** foreign currency records are not suppressed by AUD magnitude checks.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: AUD Outlier Suppression and Foreign Currency Isolation

  Background:
    Given the database ledger contains the following multi-currency entries for "Trailing 3 Months":
      | Transaction ID | Date       | Category     | Currency | Amount   |
      | TXN-201        | 2023-11-01 | Travel (AUD) | AUD      | 1500.00  |
      | TXN-202        | 2023-11-05 | Travel (AUD) | AUD      | 300.00   |
      | TXN-203        | 2023-11-10 | Travel (HKD) | HKD      | 8000.00  |
      | TXN-204        | 2023-11-15 | Flights (AUD)| AUD      | -1200.00 |

  Scenario Outline: AUD transaction filtering does not impact non-AUD records or refunds below absolute threshold
    Given the transient AUD outlier threshold slider is set to <slider_threshold>
    When baseline monthly averages are calculated for a total of 1 distinct month
    Then line items should be included or suppressed resulting in baseline values:
      | Category      | Historical Monthly Avg (AUD) | Historical Monthly Avg (HKD) |
      | Travel (AUD)  | <expected_travel_aud>        | 0.00                         |
      | Travel (HKD)  | 0.00                         | <expected_travel_hkd>        |
      | Flights (AUD) | <expected_flights_aud>       | 0.00                         |
    And the presentation layer displays the notice "Transactions performed in AUD above the set threshold are excluded from projection calculations."

    Examples:
      | slider_threshold | expected_travel_aud | expected_travel_hkd | expected_flights_aud |
      | 1000.00          | 300.00              | 8000.00             | 0.00                 |
      | 2000.00          | 1800.00             | 8000.00             | -1200.00             |
      | 0.00             | 1800.00             | 8000.00             | -1200.00             |
```

---

### Story 3: Interactive Target Overrides and Dynamic Summary Export
**AS A** personal expense tracker user,  
**I WANT TO** interactively adjust category targets and export the summary table to CSV,  
**SO THAT** I can transfer accurate budget projections to external spreadsheet tools.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Interactive Target Allocation and CSV Export

  Background:
    Given calculated historical baseline averages for lookback window "Trailing 3 Months":
      | Category         | Historical Monthly Avg (AUD) | Historical Monthly Avg (HKD) | Historical Monthly Avg (USD) |
      | Utilities (AUD)  | 200.00                       | 0.00                         | 0.00                         |
      | Software (USD)   | 0.00                         | 0.00                         | 50.00                        |
    And initial target monthly budgets default to their historical averages

  Scenario Outline: Target validation and negative value rejection
    When the user inputs "<user_input>" into the Target Monthly Budget for "<target_category>"
    Then the system validation output state should be "<validation_state>"
    And the effective Target Monthly Budget for "<target_category>" should evaluate to <effective_target>
    And the total projected monthly spend summary should update dynamically

    Examples:
      | user_input | target_category  | validation_state | effective_target |
      | 250.00     | Utilities (AUD)  | Valid            | 250.00           |
      | 0.00       | Software (USD)   | Valid            | 0.00             |
      | -45.00     | Utilities (AUD)  | Invalid          | 0.00             |
      | abc        | Software (USD)   | Invalid          | 0.00             |

  Scenario: Verify 7-column schema alignment and Total row append during CSV export
    Given the finalized target budget allocations:
      | Category        | Hist Avg (AUD) | Hist Avg (HKD) | Hist Avg (USD) | Target (AUD) | Target (HKD) | Target (USD) |
      | Groceries (AUD) | 300.00         | 0.00           | 0.00           | 350.00       | 0.00         | 0.00         |
      | Dining (HKD)    | 0.00           | 1500.00        | 0.00           | 0.00         | 1200.00      | 0.00         |
    When the user triggers the Streamlit CSV export action
    Then the generated CSV content must contain the exact headers:
      """
      Category,Historical Monthly Avg (AUD),Historical Monthly Avg (HKD),Historical Monthly Avg (USD),Target Monthly Budget (AUD),Target Monthly Budget (HKD),Target Monthly Budget (USD)
      """
    And the final row of the CSV file must match the computed total summary:
      """
      Total,300.00,1500.00,0.00,350.00,1200.00,0.00
      """
```