"""Devin legacy v1 adapter. API version verified with a personal-key GET /sessions.

References: docs.devin.ai/api-reference/v1/{sessions,attachments}. No API plan selector
is documented. The credential's existing account/credits determine billing.
"""
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import httpx
from engine.providers.common import ProviderError
from engine.reconstruction.store import digest

BASE = 'https://api.devin.ai/v1'
ARTIFACT_NAMES = ['repair_part.stl', 'surviving_estimate.stl', 'generation.py', 'requirements.txt', 'README.md', 'summary.json', 'evidence.json']
OUTPUT_SCHEMA = {'type': 'object', 'properties': {
    'status': {'type': 'string', 'enum': ['working', 'candidate_ready', 'needs_input']},
    'attempt': {'type': 'integer'}, 'missing_inputs': {'type': 'array', 'items': {'type': 'string'}},
    'artifacts': {'type': 'object', 'properties': {name: {'type': ['string', 'null']} for name in ARTIFACT_NAMES}}},
    'required': ['status', 'attempt', 'missing_inputs', 'artifacts']}


class Devin:
    def __init__(self, store, job, client=None):
        self.store, self.job = store, job
        self.key = os.getenv('DEVIN_API_KEY')
        if not self.key:
            raise ProviderError('PROVIDER_FAILED', 'DEVIN_API_KEY is not configured. No session was created.')
        self.client = client or httpx.Client(timeout=httpx.Timeout(45, connect=15), follow_redirects=False)

    def call(self, method, path, **kwargs):
        log_request = kwargs.get('json', kwargs.get('params'))
        self.store.event(self.job, 'provider_request', provider='DEVIN', method=method, path=path, request=log_request)
        started = time.monotonic()
        try:
            r = self.client.request(method, BASE+path, headers={'Authorization': 'Bearer '+self.key}, **kwargs)
            try:
                data = r.json()
            except ValueError:
                data = r.text
            self.store.event(self.job, 'provider_response', provider='DEVIN', status=r.status_code, response=data,
                request_id=r.headers.get('x-request-id'), latency_ms=round((time.monotonic()-started)*1000),
                usage=data.get('usage') if isinstance(data, dict) else None, cost=None)
            if r.status_code >= 400:
                raise ProviderError('PROVIDER_FAILED', f'Devin returned HTTP {r.status_code}.')
            return data
        except httpx.HTTPError as exc:
            self.store.event(self.job, 'transport_error', provider='DEVIN', method=method, path=path,
                error=type(exc).__name__, latency_ms=round((time.monotonic()-started)*1000))
            raise ProviderError('TIMEOUT' if isinstance(exc, httpx.TimeoutException) else 'PROVIDER_FAILED', 'Devin connection failed; remote request outcome may be unknown.') from None

    def upload(self, path):
        path = Path(path)
        self.store.event(self.job, 'attachment_upload', path=str(path), sha256=digest(path), size_bytes=path.stat().st_size)
        with path.open('rb') as file:
            result = self.call('POST', '/attachments', files={'file': (path.name, file, 'application/octet-stream')}, timeout=180)
        if not isinstance(result, str) or not result.startswith('https://'):
            raise ProviderError('PROVIDER_FAILED', 'Devin returned an invalid attachment URL.')
        return result

    def create(self, prompt):
        payload = {'prompt': prompt, 'idempotent': True, 'title': f'GridMend {self.job["job_id"]} r{self.job["revision"]}',
                   'tags': [self.tag()], 'structured_output_schema': OUTPUT_SCHEMA,
                   'secret_ids': [], 'knowledge_ids': [], 'unlisted': True}
        if self.job['limits']['max_acu'] is not None:
            payload['max_acu_limit'] = self.job['limits']['max_acu']
        return self.call('POST', '/sessions', json=payload)

    def tag(self):
        return f'gridmend-{self.job["job_id"]}-r{self.job["revision"]}'

    def recover(self):
        # A failed/ambiguous create is NEVER blindly repeated. Reconcile by unique tag.
        data = self.call('GET', '/sessions', params={'limit': 100})
        return next((s.get('session_id') for s in data.get('sessions', []) if self.tag() in s.get('tags', [])), None)

    def poll(self):
        return self.call('GET', '/sessions/'+self.job['session_id'])

    def message(self, message):
        return self.call('POST', '/sessions/'+self.job['session_id']+'/message', json={'message': message})

    def terminate(self):
        return self.call('DELETE', '/sessions/'+self.job['session_id'])

    def download(self, url, path):
        # Only the documented authenticated attachment endpoint is accepted from model output.
        u = urlsplit(url)
        if u.scheme != 'https' or u.netloc != 'api.devin.ai' or not re.fullmatch(r'/v1/attachments/[A-Za-z0-9_-]+/[^/]+', u.path) or u.query or u.fragment:
            raise ValueError('Artifact URL must use the documented Devin /v1/attachments/{uuid}/{name} endpoint.')
        self.store.event(self.job, 'artifact_download_request', url=url, path=str(path))
        r = self.client.get(url, headers={'Authorization': 'Bearer '+self.key})
        if r.status_code in (301, 302, 303, 307, 308):
            redirect = urlsplit(urljoin(url, r.headers.get('location', '')))
            host = redirect.hostname or ''
            allowed = ('amazonaws.com', 'blob.core.windows.net', 'storage.googleapis.com', 'devin.ai', 'devinusercontent.com')
            if redirect.scheme != 'https' or not any(host == d or host.endswith('.'+d) for d in allowed) or redirect.username or redirect.port not in (None, 443):
                raise ValueError('Untrusted artifact download redirect.')
            # Credentials MUST NOT be forwarded to storage.
            target = redirect.geturl()
            self.store.event(self.job, 'artifact_redirect', url=target)
        elif r.status_code == 200:
            target = None
        else:
            raise ProviderError('PROVIDER_FAILED', f'Devin artifact returned HTTP {r.status_code}.')
        limit = 64 * 1024 * 1024 if str(path).endswith('.stl') else 2 * 1024 * 1024
        if target:
            with self.client.stream('GET', target) as stream:
                if stream.status_code != 200:
                    raise ProviderError('PROVIDER_FAILED', f'Artifact storage returned HTTP {stream.status_code}.')
                with Path(path).open('xb') as f:
                    size = 0
                    for chunk in stream.iter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise ValueError('Returned artifact exceeds the download size limit.')
                        f.write(chunk)
        else:
            if len(r.content) > limit:
                raise ValueError('Returned artifact exceeds the download size limit.')
            with Path(path).open('xb') as f:
                f.write(r.content)
        self.store.event(self.job, 'artifact_downloaded', path=str(path), sha256=digest(Path(path)), size_bytes=Path(path).stat().st_size)
