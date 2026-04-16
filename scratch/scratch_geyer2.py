from db2_watsonx_pipeline import db2_connect
import ibm_db

def check():
    conn = db2_connect()
    
    for limit in [15, 20, 25]:
        stmt = ibm_db.exec_immediate(conn, f"SELECT LASTNAME FROM EMPLOYEE FETCH FIRST {limit} ROWS ONLY")
        row = ibm_db.fetch_assoc(stmt)
        found = False
        while row:
            if 'GEYER' in row['LASTNAME'].upper():
                found = True
            row = ibm_db.fetch_assoc(stmt)
        print(f"Is Geyer in top {limit} rows? {found}")

    ibm_db.close(conn)

if __name__ == "__main__":
    check()
