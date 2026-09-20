"""Explicit LIVE checks. Lists models, tests image+JSON, checks Devin auth. No session created."""
import base64
import json
import os
import time
from pathlib import Path
import cv2
import httpx
import numpy as np
from dotenv import load_dotenv
from engine.reconstruction.store import atomic_json, redact


def main():
    load_dotenv('.env')
    out = Path('artifacts/provider-checks')
    out.mkdir(parents=True, exist_ok=True)
    img = np.full((160, 240, 3), 255, np.uint8)
    cv2.circle(img, (70, 80), 35, (255, 0, 0), -1)
    cv2.rectangle(img, (150, 45), (210, 110), (0, 0, 255), -1)
    cv2.imwrite(str(out / 'vision-probe.png'), img)
    url = 'data:image/png;base64,' + base64.b64encode(cv2.imencode('.png', img)[1]).decode()
    c = httpx.Client(timeout=55)
    headers = {'Authorization': 'Bearer ' + os.environ['NEBIUS_API_KEY']}
    r = c.get('https://api.tokenfactory.nebius.com/v1/models', headers=headers)
    r.raise_for_status()
    models = r.json()
    atomic_json(out / 'nebius-models.json', models)
    selected = None
    for model in ['moonshotai/Kimi-K3', 'moonshotai/Kimi-K2.6', 'Qwen/Qwen3.5-397B-A17B']:
        if model not in [m['id'] for m in models['data']]:
            continue
        body = {'model': model, 'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Identify the colored shapes. JSON only: {"left_color":string,"left_shape":string,"right_color":string,"right_shape":string}. No dimensions.'},
            {'type': 'image_url', 'image_url': {'url': url}}]}],
            'response_format': {'type': 'json_object'}, 'temperature': 0, 'max_tokens': 700}
        started = time.monotonic()
        try:
            r = c.post('https://api.tokenfactory.nebius.com/v1/chat/completions', headers=headers, json=body)
            data = r.json()
            atomic_json(out / (model.split('/')[-1] + '.json'), {'model': model, 'status': r.status_code,
                'request': body, 'response': data, 'latency_ms': round((time.monotonic()-started)*1000),
                'image_path': str(out / 'vision-probe.png'), 'checked_at': time.time()})
            print(json.dumps(redact({'model': model, 'status': r.status_code, 'response': data})))
            if r.status_code == 200:
                answer = json.loads(data['choices'][0]['message'].get('content') or '')
                if 'blue' in str(answer.get('left_color')).lower() and 'red' in str(answer.get('right_color')).lower() and 'circle' in str(answer.get('left_shape')).lower():
                    selected = model
                    atomic_json(out / 'selected-model.json', {'model': model, 'checked_at': time.time(),
                        'reason': 'Account-listed requested-family model. Real image + JSON-object response correctly identified controlled colors and shapes.',
                        'structured_output': 'json_object with local typed validation'})
                    break
        except Exception as exc:
            print(model, type(exc).__name__)
    r = c.get('https://api.devin.ai/v1/sessions', params={'limit': 1}, headers={'Authorization': 'Bearer ' + os.environ['DEVIN_API_KEY']})
    atomic_json(out / 'devin-auth.json', {'api_version': 'v1', 'status': r.status_code, 'checked_at': time.time(), 'usage': None, 'session_created': False})
    print('Devin v1 authentication:', r.status_code, 'Selected vision/JSON model:', selected)
    return 0 if selected and r.status_code == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
