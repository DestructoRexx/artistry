import requests
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

print("--- Starting ZisandaHub Checkout Simulation ---")

# 1. Dynamically grab a valid product ID from your local database
try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "zeeuhub"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM product_template WHERE active = TRUE LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        print("❌ Error: No active products found in your local database to test with!")
        exit(1)
        
    test_product_id, test_product_name = row
    print(f"✅ Found active product in DB: '{test_product_name}' (ID: {test_product_id})")

except Exception as e:
    print(f"❌ Database lookup failed: {e}")
    exit(1)

# 2. Prepare mock checkout payload
payload = {
    "customer_name": "Luluto Testbuyer",
    "customer_email": "testbuyer@zisandahub.com",
    "items": [
        {
            "id": test_product_id,
            "quantity": 2
        }
    ]
}

# 3. Send POST request to your FastAPI checkout route
url = "http://127.0.0.1:8000/api/checkout"
print(f"🚀 Sending order payload to FastAPI endpoint ({url})...")

try:
    response = requests.post(url, json=payload)
    print(f"📥 Response Status Code: {response.status_code}")
    print(f"📥 Response Body: {response.json()}")
    
    if response.status_code == 200:
        print("\n🎉 SUCCESS! Order successfully processed and pushed to Odoo 19!")
    else:
        print("\n⚠️ Request received, but Odoo returned an error. Check credentials in .env.")
        
except Exception as e:
    print(f"❌ Failed to connect to FastAPI server. Make sure uvicorn is running! Error: {e}")