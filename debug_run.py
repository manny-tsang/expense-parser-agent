from src.pdf_parser import parse_statement

# Update filename if needed
pdf_file = "data/2026-07-07_Statement.pdf"
output_file = "data/txn-output.csv"

print("Starting debug run...")
df = parse_statement(pdf_file, output_file)
print(f"Total rows extracted: {len(df)}")
if not df.empty:
    print(df.head())