#!/usr/bin/env python
"""Simple test for edge connections"""
import requests
import json
import sys

# Load payload
with open('test-simple-connections.json', 'r') as f:
    payload = json.load(f)

print("=" * 60)
print("Testing SIMPLE edge connections (4 services, 7 edges)")
print("=" * 60)
print(f"\nProject: {payload['ir']['project']}")
print(f"Services: {len(payload['ir']['nodes'])}")
print(f"Edges: {len(payload['ir']['edges'])}")
print("\nEdges being tested:")
for i, edge in enumerate(payload['ir']['edges'], 1):
    print(f"  {i}. {edge['from']} -> {edge['to']}")

print("\n" + "=" * 60)
print("Calling /up API...")
print("=" * 60)

try:
    response = requests.post(
        'http://localhost:8000/up',
        json=payload,
        timeout=600
    )
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n[SUCCESS] Deployment completed!")
        print("\nDeployment Summary:")
        if 'summary' in result:
            summary = result['summary']
            if 'resources' in summary:
                print(f"  Resources: {summary['resources']}")
            if 'duration_sec' in summary:
                print(f"  Duration: {summary['duration_sec']} seconds")
        
        print("\nConnection Exports (bind-*):")
        if 'outputs' in result:
            outputs = result['outputs']
            bind_exports = [k for k in outputs.keys() if k.startswith('bind-')]
            if bind_exports:
                print(f"\nFound {len(bind_exports)} connection exports:")
                for export in bind_exports:
                    print(f"  [OK] {export}")
            else:
                print("  [WARNING] No connection exports found")
            
    else:
        print("\n[ERROR] Deployment failed!")
        print(f"\nResponse: {response.text[:2000]}")
        sys.exit(1)
        
except requests.exceptions.ConnectionError:
    print("\n[ERROR] Could not connect to server at http://localhost:8000")
    print("Make sure the server is running!")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    sys.exit(1)

