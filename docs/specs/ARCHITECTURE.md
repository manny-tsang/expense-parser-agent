# Personal Expense Tracker (PET) — Master Architecture Document

## 1. System Overview, Core Objective & AI Orchestration Workflow

### 1.1 Core Objective & Learning Philosophy
The primary objective of this project is to master and execute **Spec-Driven Development (SDD)** and **AI-Orchestrated Software Engineering**. 

The Personal Expense Tracker (PET) application serves as the production domain—extracting, cleaning, anonymizing, categorizing, and visualizing dual-currency credit card PDF statements (HKD/AUD) into SQLite. However, the governing engineering principle is that **AI agents generate code and Jira backlog artifacts strictly from human-governed Markdown specifications**.

---

### 1.2 End-to-End SDD & AI Delivery Workflow

All software engineering lifecycle activities MUST follow this 4-step orchestration pipeline:

[ Step 1: Human Specification ]
│
▼
docs/specs/_spec.md (Markdown Source of Truth)
│
┌──────┴────────────────────────────────────────┐
▼                                               ▼
[ Step 2: Jira Automation ]              [ Step 3: Code Generation Engine ]
python3 jira_agent_runner.py              python3 agent_runner.py
├── Reads spec markdown                   ├── Reads spec markdown + target file
├── Calls Gemini API (Spec Parser)        ├── Calls Gemini API (Role-Scoped System Prompt)
└── Creates Epics & Stories in Jira       └── Generates executable Python source code
via REST API v3                             (src/repository.py, src/pdf_parser.py, src/app.py)
│
▼
[ Step 4: Git & Local Sync ]
├── Automated Commit to GitHub Main Branch
└── Local VS Code Pull & Streamlit Validation

1. **Step 1 — Requirements & Specification Drafting**:
   - Human developer and AI draft, iterate, and finalize formal Markdown specification files in `docs/specs/` (e.g., `database_repository_spec.md`, `ui_categorisation_spec.md`).
   - Specifications explicitly establish acceptance criteria (BDD GIVEN/WHEN/THEN), module boundaries, database schemas, and interface contracts.

2. **Step 2 — Backlog Generation & Jira Orchestration (`jira_agent_runner.py`)**:
   - The markdown spec is passed into `jira_agent_runner.py`.
   - The runner uses the Gemini API (`gemini-3.6-flash`) to parse structured Epics and BDD User Stories out of the markdown text.
   - The runner invokes Atlassian Jira REST API v3 to automatically create the Epic and child Story issues in Jira under project key `PET` and set initial workflow states.

3. **Step 3 — Spec-Driven Code Generation (`agent_runner.py`)**:
   - The same markdown spec (along with optional context files) is passed to `agent_runner.py`.
   - The runner initializes Gemini API with strict role guidance (e.g., Streamlit UI vs. Backend Python Engineer) to protect module ownership boundaries.
   - Gemini generates clean, executable Python code strictly fulfilling the spec without manual code writing.

4. **Step 4 — Automated Remote Commit & Local Validation**:
   - Generated code is saved locally and committed directly to GitHub main branch via `PyGithub` integration[cite: 4].
   - Local VS Code workspace receives synced updates to validate functionality via `streamlit run src/app.py`.
   - Smart commits (`PET-X #devcomplete`) trigger GitHub Actions (`.github/workflows/jira-transitions.yml`) using `atlassian/gajira-transition@v3` to advance story statuses automatically across the Jira workflow.

### 1.3 Environment & Core Tech Stack
- **Language**: Python 3.x
- **UI & Presentation**: Streamlit (`src/app.py`), `streamlit-option-menu`
- **Data Visualization**: `plotly` (`plotly.express`, `plotly.graph_objects`), `st.plotly_chart`
- **PDF Extraction & Processing**: `pdfplumber`, `pandas`, `re`
- **Database Engine**: SQLite 3 (`db/personal-expense-tracker.db`)
- **API & System Integrations**: Google GenAI SDK (`google-genai`), `requests`, `python-dotenv`

---

### 1.4 Future Evolution of the AI Delivery Engine
*Note: The current SDD delivery engine (jira_agent_runner.py and agent_runner.py) represents Phase 1 of the delivery model. As the project matures, this architecture document will be updated to reflect Phase 2 capabilities, including automated spec refinement, automated test-driven output validation, and programmatic acceptance testing execution prior to git commits.*

---

## 2. Directory Structure & File Taxonomy

expense-parser-agent/
├── README.md                   # Repository landing page and high-level overview
├── agent_runner.py             # Spec-driven LLM code generation engine (Gemini API)
├── jira_agent_runner.py        # Automated Jira issue and epic generator
├── debug_run.py                # Local execution test script for PDF parsing
├── .github/
│   └── workflows/
│       └── jira-transitions.yml # GitHub Actions workflow for Jira state transitions
├── db/
│   └── personal-expense-tracker.db  # Production SQLite database file
├── data/                       # Raw input PDF statements, exports, and test artifacts
├── docs/
│   ├── ARCHITECTURE.md         # Master System Architecture Document (This file)
│   └── specs/                  # Feature and module specifications
│       ├── database_repository_spec.md
│       ├── pdf_parser_spec.md
│       ├── ui_ingestion_spec.md
│       └── ui_categorisation_spec.md
└── src/                        # Core application Python source code
├── app.py                  # Streamlit presentation layer & UI components
├── pdf_parser.py           # Statement parsing & PDF text extraction engine
└── repository.py           # Centralized SQLite repository layer (DatabaseRepository)

### Module Boundary & Ownership Contracts

1. **`src/repository.py` (`DatabaseRepository`)**:
   - Exclusively owns SQLite database initialization, table creation DDLs, schema migrations, baseline data seeding, and query CRUD executions.
   - **Contract Violation**: No `CREATE TABLE` DDL queries or direct `sqlite3.connect()` calls may exist in `src/app.py` or `src/pdf_parser.py`.

2. **`src/pdf_parser.py` (`HKStatementParser`)**:
   - Exclusively owns PDF page text extraction, line parsing, anchor matching, string cleaning, token discarding, fee waiver filtering, and date calculations.
   - Imports `DatabaseRepository` to resolve reference entities (`merchant`, `country`, `currency`) and persist ingested batch transactions.
   - **Contract Violation**: Must not import `streamlit` or render UI elements.

3. **`src/app.py` (`PersonalExpenseTracker`)**:
   - Exclusively owns Streamlit layout rendering, sticky CSS header injection, sidebar navigation, form input validation, and modal confirmation dialogs (`@st.dialog`).
   - Executes data reads and updates strictly through `DatabaseRepository` instance methods.

   ---

## 3. Database Schema & Entity Contracts (`db/personal-expense-tracker.db`)

The SQLite database is initialized and managed exclusively by `DatabaseRepository` inside `src/repository.py`.

### 3.1 Entity-Relationship DDL Definitions

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

### 3.2 Reserved Keyword & String Safety Standard
- **SQLite Double-Quote Constraint**: Because `"transaction"` is an SQLite reserved keyword, all DDL and DML SQL strings MUST enclose the table name in double quotes (`"transaction"`).
- **Clean Escape Formatting**: When embedding SQL inside Python multiline strings, use clean double quotes (`FROM "transaction" t`) and avoid redundant nested single quotes (e.g., never write `FROM "'transaction'" t`).

### 3.3 Idempotent Reference Data Seeding
Upon database initialization, `DatabaseRepository.init_db()` executes `INSERT OR IGNORE` statements to guarantee baseline entity existence:
1. **Category ID 1**: Fixed default `(1, 'Uncategorised')`.
2. **Canonical Categories**: `Automotive`, `Bank Fees`, `Dining & Cafes`, `Fuel`, `Groceries`, `Haircut`, `Health & Fitness`, `Medical`, `Pet`, `Shopping & Retail`, `Subscriptions`, `Transport`, `Utilities`.
3. **ISO Reference Data**: Seeds 45 ISO countries (e.g., `AT`, `AU`, `HK`, `US`, `VN`) into `"country"` and maps their 45 corresponding currencies (e.g., `EUR`, `AUD`, `HKD`, `USD`, `VND`) into `"currency"`.

---
## 4. Categorisation & Fallback Hierarchy Rules

The PET categorisation engine operates on a strict single source of truth model designed to balance global automation with single-transaction flexibility.

### 4.1 Single Source of Truth Hierarchy
                      ┌────────────────────────┐
                      │ Ingested PDF Statement │
                      └───────────┬────────────┘
                                  │
                                  ▼
         ┌───────────────────────────────────────────────────┐
         │ Raw Merchant Extraction & Keyword Regex Evaluation│
         └────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
         ┌─────────────────────────────────────────────────────┐
         │ merchant.category_id Set at Entity Baseline Level.  │
         │ (Single Source of Truth for Global Merchant Mapping)│
         └────────────────────────┬────────────────────────────┘
                                  │
                                  ▼
         ┌──────────────────────────────────────────────────┐
         │ transaction.category_id Set to NULL at Ingestion │
         └────────────────────────┬─────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ SQL COALESCE Query Strategy (get_transactions_dataframe)                 │
│                                                                          │
│ COALESCE(override_cat.category_name, default_cat.category_name)          │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌──────────────────────┐                           ┌────────────────────────┐
│ transaction.category_│                           │ transaction.category_  │
│ id IS NULL           │                           │ id IS NOT NULL         │
└───────────┬──────────┘                           └───────────┬────────────┘
            │                                                  │
            ▼                                                  ▼
┌──────────────────────┐                           ┌────────────────────────┐
│ Inherits default     │                           │ Single Transaction     │
│ merchant.category_id │                           │ Manual Override Active │
└──────────────────────┘                           └────────────────────────┘

### 4.2 Categorisation Lifecycle Rules

1. **Baseline Merchant Mapping**:
   - `merchant.category_id` acts as the primary single source of truth for default categorisation across all transactions linked to that merchant.
   - When a new merchant entity is created during PDF ingestion, keyword regex matching evaluates `merchant_name` against default rules to set its initial `merchant.category_id`. Unmatched merchants default to `1` (`Uncategorised`).

2. **Ingestion Contract**:
   - When new bank PDF statements are processed by `pdf_parser.py`, `transaction.category_id` is explicitly inserted as `NULL`.
   - This ensures individual transactions defer directly to the parent `merchant.category_id` by default.

3. **Single Transaction Override**:
   - Manually updating an individual transaction's category in the UI updates `transaction.category_id` directly for that single row.
   - The parent `merchant.category_id` remains unchanged.

4. **Global Merchant Re-Mapping**:
   - Updating a merchant's category in the UI updates `merchant.category_id` directly.
   - All transactions for that merchant where `transaction.category_id IS NULL` instantly display under the new category across all UI pages.

5. **SQL Query Resolution (`COALESCE`)**:
   - All transaction reads (such as `DatabaseRepository.get_transactions_dataframe()`) MUST evaluate categories using:
     `COALESCE(override_cat.category_name, default_cat.category_name)`

---

## 5. PDF Ingestion & Anonymisation Engine (`src/pdf_parser.py`)

The statement ingestion engine (`HKStatementParser`) handles PDF extraction, line-bundling, privacy scrubbing, keyword auto-categorisation, and database batch persistence.

### 5.1 Page Routing & Anchor Rules
- **Page 1 (Hybrid Summary & Partial Transactions)**:
  - **Start Anchor**: Begins extracting transactions upon reading table headers (`Post date` / `Trans date` / `Description of transaction`).
  - **Stop Anchor**: Halts page parsing immediately upon hitting `MINIMUM PAYMENT SUMMARY` or `SUMMARY 戶口概要`.
  - **Exclusion Rule**: Ignores balance summary rows containing `PREVIOUS BALANCE` or `上月結欠/結餘`.
- **Page 2 (Marketing & Terms Insert)**: Skipped completely during PDF parsing.
- **Page 3+ (Continuation Pages)**: Processes full-page transaction tables top-to-bottom.
- **Global Stop Anchor**: Terminates parsing entirely across the entire document upon reading:
  `*FOR CREDIT CARD TRANSACTIONS EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS`.

---

### 5.2 Multi-Line Transaction Bundling & Anonymisation
A single credit card transaction visual row in the PDF table is split across up to 3 physical lines:
- **Line 1 (Primary Data)**: Contains `Post Date`, `Trans Date`, `Merchant Description`, `Suburb`, `Country`, `AUD Amount` (if foreign spend), and `HKD Amount`.
- **Line 2 (Payment Metadata - Privacy Scrubbing)**: Contains Apple Pay tokens (`APPLE PAY-MOBILE:XXXX`). **Rule**: Stripped and discarded completely during parsing to ensure zero personal/tokenized account data enters the database.
- **Line 3 (Exchange Rate)**: Captures foreign exchange rate metadata (`*EXCHANGE RATE: X.XXXXX`) when present.

---

### 5.3 Ingestion Edge Cases & Exclusion Filters
1. **Fee Reversal Suppression**: If a `CARD ANNUAL FEE` transaction is immediately followed by an `ANNUAL FEE REFUND` (or vice-versa on the same date with matching net amounts), both transactions are suppressed during parsing and excluded from database insertion.
2. **Payment String Filtering**: Discards non-expense records such as `IFS PAYMENT` and `PAYMENT - THANK YOU`.
3. **Cross-Year Boundary Calculation**: Converts raw PDF date tokens (e.g., `09JUN`) to standard `DD-MM-YYYY` format. If transaction month (e.g., `DEC` / `12`) is greater than statement header month (e.g., `JAN` / `1`), the transaction year is automatically inferred as `statement_year - 1`.
4. **Duplicate Prevention**: Before writing records, `init_db(filename)` checks `statement_log`. If `filename` has already been ingested, parsing halts with `ValueError("Statement '<filename>' has already been processed.")`.

---

### 5.4 Dynamic Merchant & Keyword Categorisation Hierarchy
When a new statement is processed by `pdf_parser.py`, resolving the `category_id` for an extracted merchant follows a strict database-first priority hierarchy:

1. **Exact Database Merchant Lookup**: If `merchant_name` already exists in the SQLite `"merchant"` table, retain its existing mapped `category_id` (preserving all manual mappings executed via the Categorise UI).
2. **Dynamic Database Keyword Lookup**: Evaluate the new merchant string against any active global merchant rules or previously mapped merchant patterns stored in SQLite.
3. **Static Keyword Dictionary Fallback**: If no database entity or pattern matches, evaluate `merchant_name` against the baseline `DEFAULT_CATEGORIES_KEYWORDS` dictionary:
   - **Automotive**: `MEEK AUTOMOTIVE`, `SHANNONS`, `SUPERCHEAP AUTO`, `AUTOMOTIVE`, `MECHANIC`
   - **Bank Fees**: `DCC FEE`, `FOREIGN TRANSACTION FEE`, `LATE FEE`, `INTEREST CHARGE`
   - **Dining & Cafes**: `EL JANNAH`, `GYG`, `MCDONALD`, `CAFE`, `RESTAURANT`, `COFFEE`, `BAKERY`, `PATISSERIE`, `SQ *`
   - **Fuel**: `BP `, `BP CONNECT`, `SHELL`, `AMPOL`, `7-ELEVEN`, `UNITED PETROLEUM`, `CALTEX`
   - **Groceries**: `WOOLWORTHS`, `COLES`, `ALDI`, `ZETCITI`, `SUPERMARKET`, `IGAMARKET`, `GROCER`
   - **Haircut**: `SQ *STUDIO NO. 4`, `BARBER`, `HAIR`, `SALON`
   - **Health & Fitness**: `CHEMIST WAREHOUSE`, `GYM`, `PHARMACY`, `CHEMIST`, `HEALTH`, `FITNESS`
   - **Medical**: `DOCTOR`, `CLINIC`, `DENTAL`, `MEDICAL`
   - **Pet**: `PETBARN`, `VET`
   - **Shopping & Retail**: `AMAZON`, `UNIQLO`, `BUNNINGS`, `KMART`, `TARGET`, `APPLE`
   - **Subscriptions**: `CANVA`, `NETFLIX`, `SPOTIFY`, `APPLE.COM/BILL`, `YOUTUBE`, `PRIME`, `DISNEY`
   - **Transport**: `OPAL`, `PARKING`, `UBER`, `TAXI`, `TRANSPORT`
   - **Utilities**: `TELSTRA`, `OPTUS`, `ENERGY`, `WATER`, `AGL`, `ORIGIN`
4. **Default Fallback**: Assign `1` (`Uncategorised`) if neither database nor keyword matching yields a result.

---

## 6. UI Specifications & Streamlit Architecture (`src/app.py`)

The presentation layer is encapsulated inside the `PersonalExpenseTracker` class in `src/app.py`.

### 6.1 Sticky Header CSS Injection & Navigation
- **Sidebar Alignment**: Hides native Streamlit sidebar headers (`[data-testid="stSidebarHeader"]`) and sets top padding to `0rem` for flush top alignment.
- **Solid Sticky Top Header**: Targets `[data-testid="stHeader"]` with `#0e1117` background color and `z-index: 999`. Injects a persistent page title (`.sticky-page-title`) matching the active navigation choice.
- **Sidebar Navigation Framework**: Powered by `streamlit_option_menu.option_menu` with white text and active dark highlight (`#31333F`). Current menu options: `["Dashboard", "Upload", "Categorise", "Charts"]`.
  - *Architecture Evolution Note*: The sidebar navigation options, icon mappings, and styling configurations are subject to future refinement as new analytical views and administrative controls are added.
  
---

### 6.2 Streamlit `@st.dialog` Architecture & Modal Rules
To prevent Streamlit session state locks and fragment rendering errors, all modal dialogs follow strict structural rules:
1. **Module-Level Declarations**: All `@st.dialog` functions (`confirm_add_category_dialog`, `confirm_merchant_mapping_dialog`, `confirm_tx_category_dialog`) MUST be declared as top-level standalone functions outside the `PersonalExpenseTracker` class.
2. **Parameter Constraints**: Dialog functions MUST NOT accept `self` or `DatabaseRepository` class instances as parameters. Pass only primitive data types (e.g., `category_name`, `selected_merchant`, `target_id`).
3. **Internal Repository Instantiation**: Dialog functions must instantiate `DatabaseRepository(DB_PATH)` locally inside the function body upon execution.
4. **State Leak Prevention**: Do NOT store sticky boolean flags in `st.session_state` (e.g., `show_dialog = True`). Trigger `@st.dialog` functions directly upon validated button clicks.

---

### 6.3 Page Layout Specifications
- **Dashboard Page Layout**: *(Specification Pending)*
- **Upload Page Layout**:
  - **Top Row (Equal 215px Bordered Cards)**: Uses `st.columns(3)` wrapped in flex containers.
    - *Card 1*: File uploader & "Process Statement" button.
    - *Card 2*: Metric display rendering total transaction count in scaled `8.8rem` typography.
    - *Card 3*: Statement period rendering "From:" and "To:" dates in `2rem` font size.
  - **Bottom Row**: Sliced 10-row paginated table listing raw transactions with Previous/Next controls.
- **Categorise Page Layout**:
  - **Row 1 (3 Equal Columns)**:
    - *Column 1*: "Add new category" (validated input with regex `^[A-Za-z\s&\-\/]+$` and duplicate checks).
    - *Column 2*: "Merchant mapping" (2 sub-columns: read-only `Current category` + selectbox `New category`).
    - *Column 3*: "Update transaction category" (2 sub-columns for single-transaction overrides).
  - **Row 2 (Full Width)**: Full-width table displaying uncategorised merchants (`m.category_id = 1`) paginated at 5 records per page.
- **Charts Page Layout**:
  - **Row 1 (`st.columns([3, 2])`)**:
    - *Column 1*: Plotly Donut Chart (`hole=0.55`) displaying total AUD spend formatted as `$XX,XXX.XX` centered in the cutout, with sub-metric caption *"Transactions in currencies other than AUD"* for native foreign spend.
    - *Column 2*: Filter Control Card featuring Date Range Presets (defaulting to `"This Month"`), Custom Date Picker, Category Multi-Select, and Configurable Outlier Threshold input (defaulting to `$1,000`).
  - **Row 2 (Full Width)**: Category Budget Statistics DataFrame rendering `Category`, `Total Spend (AUD)`, `Monthly Average (AUD)`, `% of Total`, `Txn Count`, and `Max Single Txn (AUD)` with outlier indicators.

---

## 7. CI/CD & Jira Automation Workflow (`.github/workflows/jira-transitions.yml`)

The repository integrates GitHub Actions with Atlassian Jira to execute dynamic issue status transitions on every git push to `main`.

### 7.1 Key Extraction & Parsing
- Parses `github.event.head_commit.message` using regex `grep -oE 'PET-[0-9]+'` to extract all referenced Jira issue keys (e.g., `PET-12 PET-13`) into a space-separated string.

---

### 7.2 Action Execution & Target Transition Mapping
Uses official GitHub Actions (`atlassian/gajira-login@v3` and `atlassian/gajira-transition@v3`) targeting backend Jira transition arrow names:

| Commit Keyword Match | Jira Workflow Target Transition Arrow | Outcome State |
| :--- | :--- | :--- |
| `implementing` | `"In Progress"` | Epic moves to In Progress |
| `epiccompleted` / `epicdone` | `"Done"` | Epic moves to Done |
| `design` | `"Define"` | Story moves to IN DESIGN |
| `defined` | `"Defined"` | Story moves to READY FOR DEV |
| `start` / `indev` | `"In Sprint"` | Story moves to IN DEV |
| `engineered` / `devcomplete` | `"Engineered"` | Story moves to DEV COMPLETED |
| `readyfortest` / `testready` | `"Assigned"` | Story moves to READY FOR TEST |
| `testing` | `"Test Cases Defined"` | Story moves to IN TESTING |
| `cleared` / `testcomplete` | `"Test Cases Cleared"` | Story moves to TEST COMPLETED |
| `awaitingbuild` / `readyforbuild` | `"Awaiting Build"` | Story moves to READY FOR BUILD |
| `inbuild` | `"Build Assigned"` | Story moves to IN BUILD |
| `deployed` / `done` | `"Deployed"` | Story moves to DONE |