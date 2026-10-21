## 0. Questions & Clarification Needed for Human Sign-Off

| Item # | Area | Issue / Ambiguity | Proposed Default / Risk | Sign-Off Required From |
| :--- | :--- | :--- | :--- | :--- |
| **0.1** | **Currency Base vs. HK Card Context** | The specification references "HK Card" and "HKD statement averages", but Section 3.1 references a default outlier threshold of `$1,000 AUD` and foreign conversions to AUD. Is the base ledger currency AUD with HKD as the source card, or vice versa? | **Default**: Base ledger reporting currency is AUD; HKD card transactions are converted to AUD at statement ingestion rate. | Lead Architect / Product Owner |
| **0.2** | **Partial Lookback Windows** | If a user selects "Trailing 12 Months" but the database only contains 3 months of transaction data, how is the monthly average calculated? | **Default**: Divide total category spend by actual distinct months available (3) rather than selected window length (12), and display a warning badge. | Product Owner |
| **0.3** | **FX Rate Source for Future Projections** | Section 3.2 requests live HKD equivalent totals for future budgets. Which FX rate should be used for future projections (e.g., latest spot rate vs. trailing average rate)? | **Default**: Use the most recent exchange rate stored in `DatabaseRepository` for HKD/AUD conversion. | Financial Analyst / PM |
| **0.4** | **Outlier Exclusion Scope** | Is the $1,000 threshold applied per individual transaction line item or per monthly aggregated category sum? | **Default**: Applied to individual transaction amounts before monthly aggregation. | Business Analyst |
| **0.5** | **Clipboard Format Standard** | Section 3.3 mentions "formatted markdown table or plain-text clipboard buffer". Google Sheets multi-cell pasting works best with Tab-Separated Values (TSV). | **Default**: Output TSV text to system clipboard and render Markdown preview table in Streamlit UI. | UI/UX Lead |

---

## 1. Module Overview & Primary Intent
The **HK Card Budget Projection Engine** is a forward-looking financial planning module embedded within the Personal Expense Tracker application. Its primary intent is to:
1. Aggregate historical credit card expenses across selected rolling timeframes (3, 6, or 12 months).
2. Filter out statistical anomalies (outlier spend) to construct a normalized spend baseline per expense category.
3. Provide an interactive user interface allowing fine-grained target budget overrides.
4. Calculate converted currency targets (AUD $\leftrightarrow$ HKD) using stored rates.
5. Generate clipboard-ready representations formatted for external spreadsheet software (Google Sheets, Microsoft Excel).

---

## 2. Module Boundaries & Ownership Contracts

```
+-----------------------------------------------------------------------+
|                         Presentation Layer                            |
|                          (src/app.py)                                 |
|  - Renders UI Controls (Lookback Dropdown, Outlier Sliders, Inputs)   |
|  - Manages Streamlit Session State for Budget Overrides               |
|  - Handles Direct Clipboard Export & Markdown Tables                  |
+-----------------------------------++----------------------------------+
                                    || (Calls Repository Methods)
                                    \/
+-----------------------------------------------------------------------+
|                          Data Logic Layer                             |
|                        (src/repository.py)                            |
|  - Implements DatabaseRepository Class                                |
|  - Executes SQL Aggregations & Outlier Filtering Logic                |
|  - Computes Currency Conversions & Rolling Category Averages          |
+-----------------------------------++----------------------------------+
                                    || (Reads Only)
                                    \/
+-----------------------------------------------------------------------+
|                          Database Layer                               |
|                         (sqlite3 / Pandas)                            |
|  - Tables: transactions, exchange_rates, categories                   |
+-----------------------------------------------------------------------+
```

### Architectural Constraints & Enforcement Rules
1. **Separation of Concerns**: `src/app.py` MUST NOT execute raw SQL queries, directly invoke `sqlite3`, or manipulate internal dataframes without going through `DatabaseRepository`.
2. **Immutability of Historical Data**: Projection adjustments and override inputs MUST reside strictly in application state (`st.session_state`) or temporary memory. No write-backs to historical transaction tables are permitted during budget planning routines.
3. **Allowed Tech Stack**: `pandas`, `sqlite3`, `streamlit`, internal `DatabaseRepository`. No external API calls allowed during local projection calculations.

---

## 3. Detailed Technical Requirements & Business Rules

### 3.1 Historical Baseline & Rolling Averages Calculation
1. **Window Boundaries**:
   - Trailing 3 Months: `[Today - 90 Days]` to `[Today]`
   - Trailing 6 Months: `[Today - 180 Days]` to `[Today]`
   - Trailing 12 Months: `[Today - 365 Days]` to `[Today]`
2. **Outlier Filtering Formula**:
   - Any transaction where $\text{Amount}_{\text{AUD}} \ge \text{Threshold}_{\text{Outlier}}$ (Default: $1,000.00 AUD) is excluded from the baseline sum calculation.
   - Monthly Average per Category = $\frac{\sum \text{Non-Outlier Transactions in Window}}{\text{Number of Active Months in Window}}$
3. **Zero-Spend Handling**:
   - Categories with no transactions in the lookback window MUST return `$0.00` as baseline rather than `NaN` or `NULL`.

### 3.2 Target Budget Allocation & Interactive Overrides
1. **State Initialization**: On initial render or window change, `Target Budget (AUD)` is auto-populated with `Historical Monthly Avg (AUD)`.
2. **Dynamic Recalculation**:
   - Editing a category target updates local state immediately.
   - Live summary totals re-sum all categories:
     $$\text{Total Projected AUD} = \sum \text{Target AUD}_i$$
     $$\text{Total Projected HKD} = \text{Total Projected AUD} \times \text{Latest FX Rate}_{\text{AUD}\rightarrow\text{HKD}}$$
3. **Validation Rules**:
   - Target inputs must be non-negative real numbers. Negative entries MUST trigger an inline validation error and fall back to $0.00.

### 3.3 Google Sheets Transfer Summary
1. **Clipboard Buffer Format**: Tab-Separated Values (TSV) formatted as:
   `Category\tHistorical Monthly Avg (AUD)\tTarget Monthly Budget (AUD)\tTarget Monthly Budget (HKD)`
2. **Display Format**: Markdown Table displayed under Streamlit expander container.
3. **Formatting Standard**: All monetary values formatted to 2 decimal places with standard comma separators (e.g., `1,250.50`).

---

## 4. User Stories & BDD Acceptance Criteria

### Story 1: Calculate Category Baseline Averages
**As a** Personal Expense Tracker user,  
**I want to** select a historical lookback window and outlier threshold,  
**So that** I can establish a realistic, normalized monthly spend baseline per category.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Calculate Category Baseline Averages

  Background:
    Given the DatabaseRepository is populated with the following exchange rates:
      | Source Currency | Target Currency | Rate   |
      | HKD             | AUD             | 0.19   |
      | AUD             | HKD             | 5.26   |
    And the following historical transactions exist in the database:
      | Transaction ID | Date       | Category       | Amount HKD | Amount AUD |
      | TXN-001         | 2023-10-15 | Dining & Cafes | 400.00     | 76.00      |
      | TXN-002         | 2023-11-10 | Dining & Cafes | 600.00     | 114.00     |
      | TXN-003         | 2023-12-05 | Dining & Cafes | 8000.00    | 1520.00    |
      | TXN-004         | 2023-12-20 | Groceries      | 1000.00    | 190.00     |

  Scenario Outline: Successfully calculating category averages with outlier suppression
    Given the user selects a lookback window of "<LookbackWindow>"
    And the outlier exclusion threshold is set to <OutlierThreshold> AUD
    When the baseline calculation engine executes
    Then the calculated baseline monthly average for "<Category>" should be <ExpectedAvgAUD> AUD

    Examples:
      | LookbackWindow    | OutlierThreshold | Category       | ExpectedAvgAUD |
      | Trailing 3 Months | 1000.00          | Dining & Cafes | 63.33          |
      | Trailing 3 Months | 2000.00          | Dining & Cafes | 570.00         |
      | Trailing 3 Months | 1000.00          | Groceries      | 63.33          |
      | Trailing 6 Months | 1000.00          | Utilities      | 0.00           |

  Scenario: Selected lookback window contains zero transactions
    Given the user selects a lookback window of "Trailing 12 Months"
    And there are no transactions in the database for category "Travel"
    When the baseline calculation engine executes
    Then the category "Travel" should display a baseline average of 0.00 AUD
    And no execution exceptions or NaN values should be propagated to the UI

  Scenario: Database connection failure during baseline calculation
    Given the DatabaseRepository encounters an operational database error
    When the baseline calculation engine attempts to fetch category averages
    Then the system should display an error message "Unable to calculate spend baseline: Database connection failed"
    And the baseline table should render empty states safely
```

---

### Story 2: Interactive Target Adjustments & Live Summary
**As a** Personal Expense Tracker user,  
**I want to** override calculated historical averages with targeted budget values,  
**So that** I can customize my projected monthly spend in both AUD and HKD.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Interactive Target Adjustments

  Background:
    Given the baseline calculations are loaded with the following values:
      | Category       | Historical Monthly Avg AUD |
      | Dining & Cafes | 190.00                     |
      | Groceries      | 300.00                     |
      | Rent           | 1500.00                    |
    And the current active exchange rate for "AUD" to "HKD" is 5.25

  Scenario: Default target budget initialization
    When the Budget Projection view is initially loaded
    Then each category target input should match its baseline average:
      | Category       | Target AUD | Target HKD |
      | Dining & Cafes | 190.00     | 997.50     |
      | Groceries      | 300.00     | 1575.00    |
      | Rent           | 1500.00    | 7875.00    |
    And the total projected AUD spend should be 1990.00
    And the total projected HKD spend should be 10447.50

  Scenario Outline: Dynamic override of category budget targets
    When the user updates the target budget for "<Category>" to <NewTargetAUD> AUD
    Then the recalculated target for "<Category>" in HKD should be <ExpectedHKD>
    And the overall projected AUD monthly budget sum should be <TotalAUD>
    And the overall projected HKD monthly budget sum should be <TotalHKD>

    Examples:
      | Category       | NewTargetAUD | ExpectedHKD | TotalAUD | TotalHKD |
      | Dining & Cafes | 250.00       | 1312.50     | 2050.00  | 10762.50 |
      | Groceries      | 0.00         | 0.00        | 1690.00  | 8872.50  |
      | Rent           | 1600.50      | 8402.63     | 2090.50  | 10975.13 |

  Scenario: Rejecting negative target inputs
    When the user enters a target budget of -150.00 AUD for "Dining & Cafes"
    Then the UI should reject the input with validation error "Budget target cannot be negative"
    And the target value for "Dining & Cafes" should reset to 0.00 AUD
    And total projections should treat "Dining & Cafes" as 0.00 AUD
```

---

### Story 3: Export Formatted Summary for Google Sheets
**As a** Personal Expense Tracker user,  
**I want to** export the final calculated budget as TSV and formatted Markdown,  
**So that** I can easily copy-paste my financial plans into external spreadsheets.

#### Acceptance Criteria (Gherkin):

```gherkin
Feature: Export Formatted Summary for External Spreadsheets

  Background:
    Given the active budget projection contains the following finalized values:
      | Category       | Historical Avg AUD | Target AUD | Target HKD |
      | Dining & Cafes | 190.00             | 250.00     | 1312.50    |
      | Groceries      | 300.00             | 300.00     | 1575.00    |

  Scenario: Generate clipboard TSV buffer and UI Markdown table
    When the user triggers the "Copy to Clipboard" export action
    Then the system generates a TSV string with the exact contents:
      """
      Category\tHistorical Monthly Avg (AUD)\tTarget Monthly Budget (AUD)\tTarget Monthly Budget (HKD)
      Dining & Cafes\t190.00\t250.00\t1312.50
      Groceries\t300.00\t300.00\t1575.00
      """
    And a Markdown preview table is displayed in the Streamlit interface
    And a notification badge confirms "Budget summary copied to clipboard!"

  Scenario: Exporting empty category configuration
    Given all category targets are set to 0.00
    When the user triggers the "Copy to Clipboard" export action
    Then the TSV string should include headers and 0.00 monetary values
    And no null or undefined text blocks should be present in the export output
```