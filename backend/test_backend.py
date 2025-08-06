# test_backend.py - Script de test pour diagnostiquer le problème

import requests
import json

BASE_URL = "http://localhost:5001/api"

def test_endpoints():
    print("🔍 Test des endpoints backend...")
    
    # Test 1: Health check
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
    
    # Test 2: Ask GET
    try:
        response = requests.get(f"{BASE_URL}/ask")
        print(f"✅ Ask GET: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"❌ Ask GET failed: {e}")
    
    # Test 3: Debug endpoint
    try:
        response = requests.post(f"{BASE_URL}/debug", 
                               json={"question": "test"}, 
                               headers={"Content-Type": "application/json"})
        print(f"✅ Debug: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"❌ Debug failed: {e}")
    
    # Test 4: Ask POST avec question
    try:
        response = requests.post(f"{BASE_URL}/ask", 
                               json={"question": "Combien d'élèves?"}, 
                               headers={"Content-Type": "application/json"})
        print(f"🔍 Ask POST question: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Ask POST question failed: {e}")
    
    # Test 5: Ask POST avec subject (pour voir l'erreur)
    try:
        response = requests.post(f"{BASE_URL}/ask", 
                               json={"subject": "Combien d'élèves?"}, 
                               headers={"Content-Type": "application/json"})
        print(f"🔍 Ask POST subject: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Ask POST subject failed: {e}")

if __name__ == "__main__":
    test_endpoints()