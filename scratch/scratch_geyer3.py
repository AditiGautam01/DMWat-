from db2_watsonx_pipeline import db2_connect
import ibm_db

def check():
    conn = db2_connect()
    stmt = ibm_db.exec_immediate(conn, "SELECT * FROM EMPLOYEE FETCH FIRST 15 ROWS ONLY")
    row = ibm_db.fetch_assoc(stmt)
    while row:
        if 'GEYER' in row['LASTNAME'].upper():
            print(row)
        row = ibm_db.fetch_assoc(stmt)

    ibm_db.close(conn)

if __name__ == "__main__":
    check()
