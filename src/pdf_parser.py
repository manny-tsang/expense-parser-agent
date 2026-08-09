import os
import re
from typing import Dict, List, Optional, Tuple
import pandas as pd
import pdfplumber


class StatementParser:
    """Parser for extracting, cleaning, and anonymizing HK credit card PDF statement data."""

    MONTH_MAP: Dict[str, int] = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }

    # Regex patterns
    DATE_TOKEN_RE = re.compile(r"(\d{1,2})\s*([A-Za-z]{3})")
    STMT_DATE_RE = re.compile(
        r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b", re.IGNORECASE
    )
    TX_START_RE = re.compile(
        r"^\s*(\d{1,2}\s*[A-Za-z]{3})\s+(\d{1,2}\s*[A-Za-z]{3})\s+(.+)$",
        re.IGNORECASE,
    )
    FX_RATE_RE = re.compile(
        r"\*?\s*EXCHANGE\s+RATE\s*:\s*([\d\.]+)", re.IGNORECASE
    )
    APPLE_PAY_RE = re.compile(r"APPLE\s+PAY-MOBILE\s*:\s*\d+", re.IGNORECASE)
    AMOUNT_PATTERN = re.compile(r"-?[\d,]+\.\d{2}(?:\s*CR)?")

    def __init__(self) -> None:
        self.statement_year: Optional[int] = None
        self.statement_month: Optional[int] = None

    @staticmethod
    def _format_monetary_value(val_str: Optional[str]) -> str:
        """Format raw numeric string into standard dollar representation (e.g. $1,015.72)."""
        if not val_str:
            return ""
        clean_str = val_str.replace(",", "").replace("CR", "").strip()
        try:
            val_float = float(clean_str)
            return f"${val_float:,.2f}"
        except ValueError:
            return ""

    def _parse_date_token(self, date_str: str) -> Optional[Tuple[int, int]]:
        """Extract day and month integer tuple from date string like '09JUN' or '09 JUN'."""
        match = self.DATE_TOKEN_RE.search(date_str)
        if not match:
            return None
        day = int(match.group(1))
        month_str = match.group(2).upper()
        month = self.MONTH_MAP.get(month_str)
        if not month:
            return None
        return day, month

    def _format_tx_date(self, date_str: str) -> str:
        """Convert transaction date token to DD-MM-YYYY applying cross-year logic."""
        parsed = self._parse_date_token(date_str)
        if not parsed or not self.statement_year or not self.statement_month:
            return ""
        day, month = parsed

        # Cross-Year Boundary Rule: If tx month > statement month, it belongs to prior year
        if month > self.statement_month:
            year = self.statement_year - 1
        else:
            year = self.statement_year

        return f"{day:02d}-{month:02d}-{year:04d}"

    def extract_statement_date(self, text_lines: List[str]) -> bool:
        """Locate and set statement year and month from Page 1 text lines."""
        for i, line in enumerate(text_lines):
            if "Statement date" in line or "結單日" in line:
                # Search current and next line for statement date
                search_text = line + " " + (text_lines[i + 1] if i + 1 < len(text_lines) else "")
                match = self.STMT_DATE_RE.search(search_text)
                if match:
                    day_str, month_str, year_str = match.groups()
                    month_num = self.MONTH_MAP.get(month_str.upper())
                    if month_num:
                        self.statement_year = int(year_str)
                        self.statement_month = month_num
                        return True
        return False

    def process_transaction_buffer(self, buffer_lines: List[str]) -> Optional[Dict[str, str]]:
        """Process buffered lines for a single transaction into a structured record."""
        if not buffer_lines:
            return None

        line1 = buffer_lines[0]
        match = self.TX_START_RE.match(line1)
        if not match:
            return None

        post_date_raw, trans_date_raw, rest_of_line = match.groups()

        # Check for Apple Pay token or other line metadata
        fx_rate = ""
        for extra_line in buffer_lines[1:]:
            fx_match = self.FX_RATE_RE.search(extra_line)
            if fx_match:
                fx_rate = fx_match.group(1)

        # Extract monetary amounts from the end of rest_of_line
        amounts = self.AMOUNT_PATTERN.findall(rest_of_line)
        
        aud_amount_raw: Optional[str] = None
        hkd_amount_raw: Optional[str] = None
        
        if len(amounts) >= 2:
            aud_amount_raw = amounts[-2]
            hkd_amount_raw = amounts[-1]
            # Strip amounts from rest_of_line
            idx = rest_of_line.rfind(aud_amount_raw)
            merchant_part = rest_of_line[:idx].strip()
        elif len(amounts) == 1:
            hkd_amount_raw = amounts[-1]
            idx = rest_of_line.rfind(hkd_amount_raw)
            merchant_part = rest_of_line[:idx].strip()
        else:
            merchant_part = rest_of_line.strip()

        # Clean merchant, country, and currency
        tokens = merchant_part.split()
        purchase_currency = ""
        country = ""

        # Check for 3-letter currency code at end of merchant part
        if tokens and len(tokens[-1]) == 3 and tokens[-1].isalpha() and tokens[-1].isupper():
            if tokens[-1] in ["AUD", "USD", "EUR", "GBP", "CAD", "JPY", "SGD", "NZD", "HKD"]:
                purchase_currency = tokens.pop()

        # Check for 2-letter country code at end of merchant part
        if tokens and len(tokens[-1]) == 2 and tokens[-1].isalpha() and tokens[-1].isupper():
            country = tokens.pop()

        merchant_clean = " ".join(tokens).strip()

        # Apply edge case rules
        if aud_amount_raw and not purchase_currency:
            purchase_currency = "AUD"

        if country and not purchase_currency:
            purchase_currency = "HKD"

        if not country:
            country = "HK"
            if not purchase_currency:
                purchase_currency = "HKD"

        return {
            "post_date": self._format_tx_date(post_date_raw),
            "trans_date": self._format_tx_date(trans_date_raw),
            "merchant": merchant_clean,
            "country": country,
            "purchase_currency": purchase_currency,
            "aud_amount": self._format_monetary_value(aud_amount_raw),
            "hkd_amount": self._format_monetary_value(hkd_amount_raw),
            "fx_rate": fx_rate,
        }

    def parse_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Parse PDF document and return extracted dataframe adhering to specification."""
        records: List[Dict[str, str]] = []
        global_stop = False

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if not pdf.pages:
                    return pd.DataFrame(columns=[
                        "post_date", "trans_date", "merchant", "country",
                        "purchase_currency", "aud_amount", "hkd_amount", "fx_rate"
                    ])

                # Step 1: Extract Statement Date from Page 1
                page1_text = pdf.pages[0].extract_text() or ""
                page1_lines = page1_text.splitlines()
                self.extract_statement_date(page1_lines)

                # Process pages according to page routing rules
                for page_idx, page in enumerate(pdf.pages):
                    if global_stop:
                        break

                    page_num = page_idx + 1

                    # Page 2 Skip Rule
                    if page_num == 2:
                        continue

                    page_text = page.extract_text() or ""
                    lines = page_text.splitlines()

                    in_tx_table = False if page_num == 1 else True
                    tx_buffer: List[str] = []

                    for line in lines:
                        # Global Stop Anchor check
                        if "FOR CREDIT CARD TRANSACTIONS EFFECTED IN CURRENCIES OTHER THAN HONG KONG DOLLARS" in line:
                            global_stop = True
                            if tx_buffer:
                                rec = self.process_transaction_buffer(tx_buffer)
                                if rec:
                                    records.append(rec)
                                tx_buffer = []
                            break

                        # Page 1 Specific Anchors
                        if page_num == 1:
                            if "MINIMUM PAYMENT SUMMARY" in line or "SUMMARY 戶口概要" in line:
                                break
                            if not in_tx_table:
                                if any(h in line for h in ["Post date", "Trans date", "Description of transaction"]):
                                    in_tx_table = True
                                continue

                        if not in_tx_table:
                            continue

                        # Exclusion Rule
                        if "PREVIOUS BALANCE" in line or "上月結欠/結餘" in line:
                            continue

                        # Check if line initiates a new transaction
                        if self.TX_START_RE.match(line):
                            if tx_buffer:
                                rec = self.process_transaction_buffer(tx_buffer)
                                if rec:
                                    records.append(rec)
                            tx_buffer = [line]
                        elif tx_buffer:
                            # Append line to existing buffer (e.g., Apple Pay metadata or FX rate line)
                            tx_buffer.append(line)

                    # Process remaining buffer at the end of page
                    if tx_buffer and not global_stop:
                        rec = self.process_transaction_buffer(tx_buffer)
                        if rec:
                            records.append(rec)

        except Exception as err:
            # Gracefully handle PDF extraction exceptions
            print(f"Error reading PDF file '{pdf_path}': {err}")

        columns = [
            "post_date",
            "trans_date",
            "merchant",
            "country",
            "purchase_currency",
            "aud_amount",
            "hkd_amount",
            "fx_rate",
        ]
        
        df = pd.DataFrame(records, columns=columns)
        return df


def parse_statement(pdf_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame:
    """Module entry point to parse HK credit card PDF statement and output structured dataframe/CSV."""
    parser = StatementParser()
    df = parser.parse_pdf(pdf_path)

    if output_csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
        df.to_csv(output_csv_path, index=False)

    return df