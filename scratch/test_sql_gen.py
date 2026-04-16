import os
import sys
sys.path.append(os.getcwd())
from db2_watsonx_pipeline import db2_connect, WatsonxClient, generate_sql, WATSONX_API_KEY, WATSONX_PROJECT, WATSONX_URL
import ibm_db

def test():
    conn = db2_connect()
    wx = WatsonxClient(WATSONX_API_KEY, WATSONX_PROJECT, WATSONX_URL)
    
    print("--- Testing 'List all rows in CATALOG' ---")
    res1 = generate_sql(conn, wx, "List all rows in the CATALOG table")
    print(f"Generated SQL: {res1['sql']}")
    print(f"Result Rows: {len(res1['rows'])}")
    
    print("\n--- Testing 'List all patients' ---")
    res2 = generate_sql(conn, wx, "Show me all information from the PATIENTS table")
    print(f"Generated SQL: {res2['sql']}")
    print(f"Result Rows: {len(res2['rows'])}")
    
    ibm_db.close(conn)

if __name__ == "__main__":
    test()
