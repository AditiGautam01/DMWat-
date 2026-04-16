import ibm_db
from db2_watsonx_pipeline import db2_connect

def check():
    conn = db2_connect()
    print("Checking for John Geyer...")
    
    # Check if he is in the table at all
    stmt1 = ibm_db.exec_immediate(conn, "SELECT FIRSTNME, LASTNAME, SALARY FROM EMPLOYEE WHERE LASTNAME LIKE '%GEYER%'")
    row = ibm_db.fetch_assoc(stmt1)
    if row:
        print("Found in DB2:", row)
    else:
        print("Not found in DB2 at all.")
        
    # Check if he is in the FIRST 20 rows
    stmt2 = ibm_db.exec_immediate(conn, "SELECT FIRSTNME, LASTNAME FROM EMPLOYEE FETCH FIRST 20 ROWS ONLY")
    row = ibm_db.fetch_assoc(stmt2)
    found_in_top_20 = False
    count = 0
    while row:
        count += 1
        if 'GEYER' in row['LASTNAME'].upper():
            found_in_top_20 = True
        row = ibm_db.fetch_assoc(stmt2)
        
    print(f"Total rows retrieved in top 20: {count}")
    print(f"Is Geyer in the first 20 rows?: {found_in_top_20}")
    
    # Count total rows to be sure
    stmt3 = ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM EMPLOYEE")
    print("Total rows in EMPLOYEE:", ibm_db.fetch_tuple(stmt3)[0])
    
    ibm_db.close(conn)

if __name__ == "__main__":
    check()
