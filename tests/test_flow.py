import requests
import os
import time

BASE_URL = "http://127.0.0.1:8000"

def run_test():
    print("--- Starting Integration Test ---")
    
    # 1. Login
    print("1. Logging in as admin...")
    login_data = {"username": "admin"}
    response = requests.post(f"{BASE_URL}/token", json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   Login successful.")

    # 2. Upload Data
    print("2. Uploading Excel data...")
    file_path = os.path.join(os.path.dirname(__file__), "test_data.xlsx")
    if not os.path.exists(file_path):
        print("   Test data file not found. Run generate_data.py first.")
        return

    with open(file_path, "rb") as f:
        files = {"file": ("test_data.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = requests.post(f"{BASE_URL}/upload/households/", headers=headers, files=files)
    
    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        return
    print(f"   Upload successful: {response.json()}")

    # 3. Trigger Scoring
    print("3. Triggering Scoring Calculation...")
    response = requests.post(f"{BASE_URL}/scoring/calculate", headers=headers)
    if response.status_code != 200:
        print(f"Scoring failed: {response.text}")
        return
    print(f"   Scoring successful: {response.json()}")

    # 4. Verify Results
    print("4. Verifying Results...")
    response = requests.get(f"{BASE_URL}/households/", headers=headers)
    households = response.json()
    
    print(f"   Found {len(households)} households.")
    for h in households:
        print(f"   - {h['name']}: Score {h['total_score']:.2f} (Members: {len(h['people'])})")
        
    if len(households) > 0 and households[0]['total_score'] > 0:
        print("\nSUCCESS: System is functioning correctly.")
    else:
        print("\nWARNING: Scores might be zero or no households found.")

if __name__ == "__main__":
    # Wait a bit for server to start if running in automation
    time.sleep(2) 
    run_test()
