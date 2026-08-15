"""Smoke test for DeepSeek API."""
import os
import sys
import httpx

api_key = os.environ.get('DEEPSEEK_API_KEY', '')
if not api_key:
    print('DEEPSEEK_API_KEY env not set')
    sys.exit(1)

resp = httpx.post(
    'https://api.deepseek.com/v1/chat/completions',
    headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    },
    json={
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': 'You are a helpful assistant. Reply briefly.'},
            {'role': 'user', 'content': 'What is 1+1? Just the number.'},
        ],
        'max_tokens': 50,
        'temperature': 0,
    },
    timeout=30,
)
print('status:', resp.status_code)
print('body:', resp.text[:500])
