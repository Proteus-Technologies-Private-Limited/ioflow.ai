#!/usr/bin/env python3
"""Test if the basic MCP setup works"""
import sys
import json

# Send a simple initialization message
print(json.dumps({
    "jsonrpc": "2.0",
    "method": "initialized",
    "params": {
        "serverInfo": {
            "name": "ioflow-test",
            "version": "1.0.0"
        }
    }
}), file=sys.stderr)

# Keep process alive
while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        # Echo back for debugging
        sys.stderr.write(f"Received: {line}")
    except:
        break