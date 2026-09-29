import pandas as pd

def process_date(table):
    #find columns with dates using regex over the columns
    temp_table = table.copy()
    date_columns = [col for col in temp_table.columns if temp_table[col].astype(str).str.contains(r'\d{2}/\d{2}/\d{4}').any()]
    for col in date_columns:
        temp_table[col] = pd.Series(temp_table[col]).str.extract(r'(\d{2}/\d{2}/\d{4})')
    return temp_table