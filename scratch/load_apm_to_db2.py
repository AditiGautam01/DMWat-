import pandas as pd
import os
import sys

# Db2 DLL path must be set BEFORE importing ibm_db on Windows
dll_path = os.getenv("DB2_DLL_PATH", r"C:\PROGRA~1\IBM\SQLLIB\BIN")
if sys.platform == "win32" and os.path.isdir(dll_path):
    os.add_dll_directory(dll_path)

import ibm_db
from db2_watsonx_pipeline import db2_connect
import getpass
import time

def load_excel_to_db2(file_path, table_name="AIRCRAFT_PREDICTIVE_MAINTENANCE"):
    print(f"Loading {file_path} into pandas...")
    df = pd.read_excel(file_path)
    print(f"Loaded {len(df)} rows.")

    # Convert timestamps to string format for Db2
    for col in df.select_dtypes(include=['datetime64']).columns:
        df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Connect to DB2
    conn = db2_connect()
    
    # Create Table SQL
    columns = []
    for col_name, dtype in zip(df.columns, df.dtypes):
        col_type = "VARCHAR(255)"
        if "int" in str(dtype):
            col_type = "INTEGER"
        elif "float" in str(dtype):
            col_type = "DECIMAL(10,2)"
        elif "datetime" in str(dtype):
            col_type = "TIMESTAMP"
            
        columns.append(f"{col_name} {col_type}")
        
    create_sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
    
    # Try dropping it first just in case
    try:
        stmt = ibm_db.exec_immediate(conn, f"DROP TABLE {table_name}")
        print(f"Dropped existing table {table_name}")
    except Exception as e:
        pass
        
    try:
        print(f"Creating table {table_name}...")
        stmt = ibm_db.exec_immediate(conn, create_sql)
        print("Table created successfully.")
    except Exception as e:
        print(f"Error creating table: {str(e)}")
        ibm_db.close(conn)
        return
        
    # Insert rows
    print("Inserting rows...")
    insert_sql = f"INSERT INTO {table_name} ({','.join(df.columns)}) VALUES ({','.join(['?' for _ in df.columns])})"
    stmt = ibm_db.prepare(conn, insert_sql)
    
    success = 0
    for i, row in df.iterrows():
        try:
            # handle NaNs
            row_data = tuple(None if pd.isna(x) else x for x in row.values)
            ibm_db.execute(stmt, row_data)
            success += 1
        except Exception as e:
            print(f"Failed to insert row {i}: {str(e)}")
            
    print(f"Successfully inserted {success} out of {len(df)} rows.")
    ibm_db.close(conn)

if __name__ == "__main__":
    file_path = "aircraft_predictive_maintenance (1).xlsx"
    load_excel_to_db2(file_path)
