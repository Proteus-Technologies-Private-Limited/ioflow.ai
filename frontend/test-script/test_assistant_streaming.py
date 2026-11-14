"""
Test script to verify real-time streaming of assistant responses
"""

import asyncio
import websockets
import json
import time

async def test_streaming():
    uri = "ws://localhost:7001/api/assistant/ws/test_streaming_session"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        # Wait for connection confirmation
        await asyncio.sleep(0.5)
        
        # Send a test message that should trigger streaming response
        message = {
            "type": "send_message",
            "text": "Please design a workflow that monitors server health and sends alerts when CPU usage exceeds 80%. The workflow should check every 5 minutes.",
            "agent_id": "flow_designer",
            "api_key": "test-api-key",  # Will need to be replaced with actual key
            "model": "gemini-2.0-flash-exp"
        }
        
        print("Sending message...")
        await websocket.send(json.dumps(message))
        
        # Listen for streaming responses
        print("\nStreaming responses:")
        print("-" * 50)
        
        start_time = time.time()
        text_events = []
        tool_events = []
        
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(response)
                
                elapsed = time.time() - start_time
                
                if data.get("type") == "stream_event":
                    event_data = data.get("data", {})
                    
                    # Track text streaming
                    if event_data.get("text"):
                        text_events.append({
                            "time": elapsed,
                            "text": event_data["text"][:50] + "..." if len(event_data["text"]) > 50 else event_data["text"]
                        })
                        print(f"[{elapsed:.2f}s] TEXT: {event_data['text'][:100]}...")
                    
                    # Track tool calls
                    elif event_data.get("tool_calls"):
                        tool_events.append({
                            "time": elapsed,
                            "tools": [tc["name"] for tc in event_data["tool_calls"]]
                        })
                        print(f"[{elapsed:.2f}s] TOOL CALL: {event_data['tool_calls']}")
                    
                    # Track tool responses
                    elif event_data.get("tool_responses"):
                        print(f"[{elapsed:.2f}s] TOOL RESPONSE: {len(event_data['tool_responses'])} response(s)")
                    
                elif data.get("type") == "execution_complete":
                    print(f"\n[{elapsed:.2f}s] EXECUTION COMPLETE")
                    if data.get("data", {}).get("response"):
                        print(f"Final response: {data['data']['response'][:200]}...")
                    break
                    
                elif data.get("type") == "error":
                    print(f"\n[{elapsed:.2f}s] ERROR: {data.get('message')}")
                    break
                    
        except asyncio.TimeoutError:
            print("\nTimeout waiting for response")
        
        print("\n" + "-" * 50)
        print(f"Summary:")
        print(f"- Total text events: {len(text_events)}")
        print(f"- Total tool events: {len(tool_events)}")
        print(f"- Text streaming timeline:")
        for event in text_events[:5]:  # Show first 5 text events
            print(f"  [{event['time']:.2f}s] {event['text']}")
        if len(text_events) > 5:
            print(f"  ... and {len(text_events) - 5} more text events")

if __name__ == "__main__":
    print("Testing Assistant Real-Time Streaming")
    print("=" * 50)
    asyncio.run(test_streaming())
