import sys
import os
sys.path.append(os.getcwd())
from db2_watsonx_pipeline import db2_connect
import ibm_db

def check_patients_schema():
    conn = db2_connect()
    print("--- PATIENTS TABLE SCHEMA ---")
    sql = """
        SELECT COLNAME, TYPENAME, LENGTH, NULLS
        FROM SYSCAT.COLUMNS
        WHERE TABNAME = 'PATIENTS'
        ORDER BY COLNO
    """
    stmt = ibm_db.exec_immediate(conn, sql)
    row = ibm_db.fetch_assoc(stmt)
    while row:
        print(row)
        row = ibm_db.fetch_assoc(stmt)
    
    print("\n--- CHECKING ROWS ---")
    stmt2 = ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM PATIENTS")
    res = ibm_db.fetch_tuple(stmt2)
    print(f"Current count: {res[0]}")
    
    ibm_db.close(conn)

if __name__ == "__main__":
    check_patients_schema()
