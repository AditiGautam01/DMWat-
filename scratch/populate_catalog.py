import sys
import os
sys.path.append(os.getcwd())
from db2_watsonx_pipeline import db2_connect
import ibm_db

def populate():
    conn = db2_connect()
    
    # Sample data records
    data = [
        ("Snow Shovel", 
         '<product id="100-101-01"><description><name>Ergo Snow Shovel</name><price>29.99</price><weight>3.2 lbs</weight><features><f>D-grip handle</f><f>Non-stick blade</f></features></description></product>'),
        ("Lawn Mower", 
         '<product id="100-103-01"><description><name>Toro Recycler 22"</name><price>399.00</price><engine>163cc Briggs &amp; Stratton</engine><warranty>2 years</warranty></description></product>'),
        ("Garden Hose", 
         '<product id="100-105-01"><description><name>FlexiGuard 50ft Hose</name><price>44.50</price><specs><length>50 ft</length><diameter>5/8 inch</diameter></specs></description></product>'),
        ("Power Drill", 
         '<product id="100-107-02"><description><name>DeWalt 20V Max XR</name><price>159.00</price><specs><voltage>20V</voltage><torque>820 UWO</torque></specs></description></product>'),
        ("Work Light", 
         '<product id="100-109-01"><description><name>LED Jobsite Light</name><price>89.95</price><lumens>3000</lumens><runtime>11 hours</runtime></description></product>')
    ]
    
    print(f"Cleaning existing entries in CATALOG...")
    ibm_db.exec_immediate(conn, "DELETE FROM CATALOG")
    
    print(f"Inserting {len(data)} records...")
    sql = "INSERT INTO CATALOG (NAME, CATLOG) VALUES (?, ?)"
    stmt = ibm_db.prepare(conn, sql)
    
    for name, xml_content in data:
        print(f"  Inserting: {name}")
        ibm_db.bind_param(stmt, 1, name)
        ibm_db.bind_param(stmt, 2, xml_content)
        ibm_db.execute(stmt)
        
    print("\nPopulation complete!")
    
    # Final check
    stmt_check = ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM CATALOG")
    count = ibm_db.fetch_tuple(stmt_check)[0]
    print(f"Total rows now in CATALOG: {count}")
    
    ibm_db.close(conn)

if __name__ == "__main__":
    populate()
