import requests
import json
import sys
import uuid

def test_sse():
    url = "http://localhost:8000/chat"
    payload = {
        "session_id": f"test_sse_{uuid.uuid4()}",
        "message": "AI summary"
    }
    headers = {"Content-Type": "application/json"}
    
    print("Sending request to /chat...", flush=True)
    with requests.post(url, json=payload, headers=headers, stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data_str = decoded_line[6:]
                    try:
                        data = json.loads(data_str)
                        evt_type = data.get('type')
                        if evt_type == 'chunk':
                            if 'step_id' in data:
                                print(f"  Chunk with step_id: {data['step_id']} -> {data.get('content')[:10]}", flush=True)
                        else:
                            print(f"Event: {evt_type}", flush=True)
                            if evt_type == 'message':
                                if 'step_id' in data:
                                    print(f"  Message with step_id: {data['step_id']}", flush=True)
                            if evt_type == 'step_status':
                                print(f"  Step: {data.get('step_id')} - {data.get('status')}", flush=True)
                            if evt_type == 'trace':
                                print(f"  Trace: {data.get('content')[:50]}...", flush=True)
                            if evt_type == 'session_plan':
                                print(f"  Plan steps: {len(data.get('steps', []))}", flush=True)
                            if evt_type == 'session_summary':
                                print(f"  Summary: {data.get('summary')}", flush=True)
                    except json.JSONDecodeError:
                        pass

if __name__ == "__main__":
    test_sse()
