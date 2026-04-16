import requests

def test():
    req = {
        "table_name": "EMPLOYEE",
        "question": "what is the salary of john geyer?"
    }
    
    print("--- Asking /api/question ---")
    r1 = requests.post("http://127.0.0.1:8000/api/question", json=req)
    if r1.ok:
        print(r1.json().get('answer'))
    else:
        print("Error:", r1.text)
        
    print("\n--- Asking /api/pipeline/unified ---")
    req["maximo_entity"] = "workorders"
    r2 = requests.post("http://127.0.0.1:8000/api/pipeline/unified", json=req)
    if r2.ok:
        print(r2.json().get('answer'))
    else:
        print("Error:", r2.text)

if __name__ == "__main__":
    test()
