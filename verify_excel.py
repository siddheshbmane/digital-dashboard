import pandas as pd
try:
    df = pd.read_excel("/Users/siddhesh/Google AG/Dashboard/test/leads-sample-template edited.xlsx")
    print("Successfully read Excel file!")
    print(df.head())
except Exception as e:
    print(f"Error reading Excel file: {e}")
