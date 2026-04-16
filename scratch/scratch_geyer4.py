from db2_watsonx_pipeline import db2_connect
import ibm_db

def check():
    conn = db2_connect()
    stmt = ibm_db.exec_immediate(conn, "SELECT LASTNAME FROM EMPLOYEE FETCH FIRST 20 ROWS ONLY")
    row = ibm_db.fetch_assoc(stmt)
    c = 0
    while row:
        c += 1
        if 'GEYER' in row['LASTNAME'].upper():
            print(f'FOUND AT INDEX {c-1} (Row {c})')
        row = ibm_db.fetch_assoc(stmt)
    ibm_db.close(conn)

if __name__ == "__main__":
    check()
