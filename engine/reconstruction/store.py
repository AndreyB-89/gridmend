"""Crash-safe local manifests, process locks, redacted event journals."""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'authorization|api.?key|secret|password|^(?:access_|refresh_)?token$|cookie', k, re.I)
                else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    for k, v in os.environ.items():
        if len(v) > 8 and re.search(r'KEY|TOKEN|SECRET|PASSWORD', k):
            value = value.replace(v, '[REDACTED]')
    value = re.sub(r'data:[^\s"\]]+;base64,[A-Za-z0-9+/=]+', '[BINARY_REDACTED]', value)
    value = re.sub(r'(?i)Bearer\s+[^\s"\x27]+', 'Bearer [REDACTED]', value)
    value = re.sub(r'apk_(?:user_)?[A-Za-z0-9_+=/-]+', '[REDACTED]', value)
    def clean_url(m):
        u = urlsplit(m.group(0))
        return urlunsplit((u.scheme, u.hostname or '', u.path, 'REDACTED' if u.query else '', ''))
    return re.sub(r'https?://[^\s"<>]+', clean_url, value)


def atomic_json(path: Path, data, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data if private else redact(data), f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.getenv('RECONSTRUCTION_ROOT', 'artifacts/reconstruction')).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, job_id):
        if not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise ValueError('Unknown reconstruction.')
        return self.root / job_id

    @contextlib.contextmanager
    def lock(self, job_id, blocking=True):
        folder = self.directory(job_id)
        if not folder.is_dir():
            raise ValueError('Unknown reconstruction.')
        with (folder / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self, job_id):
        return json.loads((self.directory(job_id) / 'manifest.json').read_text())

    def save(self, job):
        atomic_json(self.directory(job['job_id']) / 'manifest.json', job)

    def revision_dir(self, job):
        return self.directory(job['job_id']) / 'revisions' / str(job['revision'])

    def event(self, job, kind, **data):
        event = redact(dict(time=time.time(), job_id=job['job_id'], reference_revision=job['revision'],
                            session_id=job.get('session_id'), attempt=job.get('attempt', 0),
                            retry=job.get('retries', 0), event=kind, **data))
        with (self.directory(job['job_id']) / 'events.jsonl').open('a') as f:
            f.write(json.dumps(event, allow_nan=False) + '\n')
            f.flush()
            os.fsync(f.fileno())

    def transition(self, job, status, reason=None):
        previous = job['status']
        job['status'] = status
        job['terminal_reason'] = reason
        self.event(job, 'status', previous=previous, status=status, reason=reason)
        self.save(job)

    def say(self, job, text, role='assistant', message_id=None):
        msg = dict(role=role, text=redact(text), id=message_id or uuid.uuid4().hex, mode=job['mode'])
        job['messages'].append(msg)
        self.event(job, 'message', message=msg)

    def private(self, job):
        path = self.revision_dir(job) / '.provider.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def save_private(self, job, data):
        # Signed attachment URLs needed across restarts; never logs/public downloads.
        atomic_json(self.revision_dir(job) / '.provider.json', data, private=True)
