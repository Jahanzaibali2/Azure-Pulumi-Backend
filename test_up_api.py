#!/usr/bin/env python
"""Test script for /up API with edge connections"""
import requests
import json
import sys

# Load payload
with open('test-connections-payload.json', 'r') as f:
    payload = json.load(f)

print("=" * 60)
print("Testing /up API with edge connections")
print("=" * 60)
print(f"\nProject: {payload['ir']['project']}")
print(f"Environment: {payload['ir']['env']}")
print(f"Location: {payload['ir']['location']}")
print(f"\nServices: {len(payload['ir']['nodes'])}")
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
        timeout=600  # 10 minutes for deployment
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
        
        print("\nOutputs (showing first 10):")
        if 'outputs' in result:
            outputs = result['outputs']
            for i, (key, value) in enumerate(list(outputs.items())[:10]):
                print(f"  {key}: {str(value)[:80]}...")
            if len(outputs) > 10:
                print(f"  ... and {len(outputs) - 10} more outputs")
        
        # Check for connection exports
        print("\nConnection Exports (bind-*):")
        bind_exports = [k for k in outputs.keys() if k.startswith('bind-')]
        if bind_exports:
            for export in bind_exports[:15]:
                print(f"  [OK] {export}")
            if len(bind_exports) > 15:
                print(f"  ... and {len(bind_exports) - 15} more connection exports")
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

