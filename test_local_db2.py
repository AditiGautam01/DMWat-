"""
test_local_db2.py — Validates the python-ibmdb driver against local Db2 HEE.

Tests:
  1. ibm_db low-level connection (Windows implicit auth)
  2. ibm_db_dbi DB-API 2.0 connection
  3. ibm_db_ctx context manager
  4. Basic CRUD operations
"""
import os
os.add_dll_directory(r'C:\PROGRA~1\IBM\SQLLIB\BIN')

import ibm_db
import ibm_db_dbi
from ibm_db_ctx import Db2connect

DB_NAME = "SAMPLE"
SEPARATOR = "-" * 50

def test_ibm_db_connection():
    """Test 1: Low-level ibm_db driver."""
    print(f"\n{SEPARATOR}")
    print("TEST 1: ibm_db — Low-level driver connection")
    print(SEPARATOR)

    conn = ibm_db.connect(DB_NAME, "", "")
    print("[OK] Connected successfully")

    # Server info
    info = ibm_db.server_info(conn)
    print(f"  DBMS:       {info.DBMS_NAME}")
    print(f"  Version:    {info.DBMS_VER}")
    print(f"  DB Name:    {info.DB_NAME}")
    print(f"  Codepage:   {info.DB_CODEPAGE}")

    # Client info
    client = ibm_db.client_info(conn)
    print(f"  Driver:     {client.DRIVER_NAME}")
    print(f"  ODBC Ver:   {client.ODBC_VER}")

    # Quick query
    stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT DATE, CURRENT TIME, CURRENT USER FROM SYSIBM.SYSDUMMY1")
    row = ibm_db.fetch_tuple(stmt)
    print(f"  Date:       {row[0]}")
    print(f"  Time:       {row[1]}")
    print(f"  User:       {row[2].strip()}")

    ibm_db.close(conn)
    print("[OK] Connection closed")

def test_dbapi_connection():
    """Test 2: DB-API 2.0 (ibm_db_dbi) connection."""
    print(f"\n{SEPARATOR}")
    print("TEST 2: ibm_db_dbi — DB-API 2.0 connection")
    print(SEPARATOR)

    conn = ibm_db_dbi.connect(DB_NAME, "", "")
    print("[OK] Connected successfully")
    print(f"  API Level:     {ibm_db_dbi.apilevel}")
    print(f"  Param Style:   {ibm_db_dbi.paramstyle}")

    cursor = conn.cursor()

    # Count tables in schema
    cursor.execute("SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT USER")
    count = cursor.fetchone()[0]
    print(f"  Tables owned:  {count}")

    # List first 5 tables
    cursor.execute("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT USER FETCH FIRST 5 ROWS ONLY")
    tables = cursor.fetchall()
    if tables:
        print(f"  Sample tables: {', '.join(t[0] for t in tables)}")
    else:
        print("  (No user tables found)")

    cursor.close()
    conn.close()
    print("[OK] Connection closed")

def test_context_manager():
    """Test 3: Context manager (ibm_db_ctx)."""
    print(f"\n{SEPARATOR}")
    print("TEST 3: ibm_db_ctx — Context manager")
    print(SEPARATOR)

    with Db2connect(DB_NAME, "", "") as conn:
        print("[OK] Connected via context manager")
        stmt = ibm_db.exec_immediate(conn, "VALUES (1 + 1)")
        row = ibm_db.fetch_tuple(stmt)
        print(f"  1 + 1 = {row[0]}")

    print("[OK] Auto-closed on exit")

def test_crud():
    """Test 4: Basic CRUD operations."""
    print(f"\n{SEPARATOR}")
    print("TEST 4: CRUD — Create, Insert, Read, Drop")
    print(SEPARATOR)

    conn = ibm_db.connect(DB_NAME, "", "")

    table = "IBMDB_DRIVER_TEST"

    # Drop if exists
    try:
        ibm_db.exec_immediate(conn, f"DROP TABLE {table}")
    except:
        pass

    # CREATE
    ibm_db.exec_immediate(conn, f"CREATE TABLE {table} (ID INT, NAME VARCHAR(50))")
    print(f"[OK] Created table {table}")

    # INSERT (parameterised)
    insert = ibm_db.prepare(conn, f"INSERT INTO {table} VALUES (?, ?)")
    params = ((1, 'Alice'), (2, 'Bob'), (3, 'Charlie'))
    ibm_db.execute_many(insert, params)
    print(f"[OK] Inserted {len(params)} rows")

    # READ
    stmt = ibm_db.exec_immediate(conn, f"SELECT * FROM {table} ORDER BY ID")
    print("  Rows:")
    row = ibm_db.fetch_assoc(stmt)
    while row:
        print(f"    {row['ID']:>3}  {row['NAME']}")
        row = ibm_db.fetch_assoc(stmt)

    # DROP
    ibm_db.exec_immediate(conn, f"DROP TABLE {table}")
    print(f"[OK] Dropped table {table}")

    ibm_db.close(conn)
    print("[OK] All CRUD operations passed")


if __name__ == "__main__":
    print("=" * 50)
    print("  python-ibmdb Driver Validation")
    print(f"  ibm_db version: {ibm_db.__version__}")
    print("=" * 50)

    try:
        test_ibm_db_connection()
        test_dbapi_connection()
        test_context_manager()
        test_crud()

        print(f"\n{'=' * 50}")
        print("  ALL TESTS PASSED [OK]")
        print(f"{'=' * 50}")

    except Exception as e:
        print(f"\n[FAIL] FAILED: {e}")
        try:
            print(f"  Connection error: {ibm_db.conn_errormsg()}")
        except:
            pass
