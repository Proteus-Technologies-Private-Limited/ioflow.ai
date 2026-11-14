#!/usr/bin/env python3
"""
Script to get JWT authentication token from IOFlow
"""

import requests
import json
import sys

def get_jwt_token(base_url, email, password):
    """Login and get JWT token"""
    login_url = f"{base_url}/api/v1/auth/login"
    
    payload = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(login_url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        token = data.get("access_token")
        user_info = data.get("user", {})
        
        print(f"Successfully logged in as: {user_info.get('email')}")
        print(f"Role: {user_info.get('role')}")
        print(f"\nJWT Token:")
        print(f"{token}")
        print(f"\nUse this token in the Authorization header:")
        print(f"Authorization: Bearer {token}")
        
        return token
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

if __name__ == "__main__":
    # Configuration
    BASE_URL = "http://localhost:8000"
    
    print("IOFlow Authentication Token Generator")
    print("=" * 40)
    
    email = input("Enter your IOFlow email: ")
    password = input("Enter your IOFlow password: ")
    
    token = get_jwt_token(BASE_URL, email, password)
    
    if token:
        print(f"\n\nFor MCP Server, set this environment variable:")
        print(f"export IOFLOW_API_KEY=\"Bearer {token}\"")