#!/usr/bin/env python3
"""
Test script to verify MCP server handles mixed Accept headers correctly.
"""
import requests
import json

# Test configuration
BASE_URL = "https://api.50juice.com"  # Your server URL
TOKEN = "my-token-here"  # Replace with your actual token

# Headers that Cursor sends (causing the 406 error)
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json, text/event-stream, */*",
    "Content-Type": "application/json"
}

# Test data - a simple MCP initialize request
test_data = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "roots": {
                "listChanged": True
            },
            "sampling": {}
        },
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
}

def test_endpoint(endpoint_path, method="POST"):
    """Test an MCP endpoint with mixed Accept headers."""
    url = f"{BASE_URL}{endpoint_path}"
    print(f"\nTesting {method} {url}")
    print(f"Headers: {headers}")
    
    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=test_data, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 406:
            print("❌ FAILED: Still getting 406 Not Acceptable")
            return False
        elif response.status_code in [200, 201, 400, 401, 403]:
            print("✅ SUCCESS: No 406 error (content negotiation working)")
            return True
        else:
            print(f"⚠️  UNEXPECTED: Got status {response.status_code}")
            return True  # Not a 406, so content negotiation is working
            
    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        return False

def main():
    """Run tests on MCP endpoints."""
    print("Testing MCP server with mixed Accept headers...")
    
    endpoints_to_test = [
        ("/mcp", "POST"),
        ("/mcp/messages/", "POST"),
        ("/mcp/http", "POST"),
        ("/health/", "GET"),
    ]
    
    results = []
    for endpoint, method in endpoints_to_test:
        result = test_endpoint(endpoint, method)
        results.append((endpoint, result))
    
    print("\n" + "="*50)
    print("SUMMARY:")
    for endpoint, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {endpoint}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 All tests passed! The 406 error should be fixed.")
    else:
        print("\n❌ Some tests failed. The 406 error may still occur.")

if __name__ == "__main__":
    main() 