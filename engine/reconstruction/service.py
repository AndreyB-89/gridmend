"""Persistent reconstruction state machine. One tick performs bounded work; HTTP never waits for Devin completion."""
from __future__ import annotations
import json
import os
import threading
import time
import uuid
from pathlib import Path
from string import Template
from api.schemas import ReferenceSpec, VideoState
from cad.reference import build_reference
from engine.providers.common import ProviderError
from engine.providers.devin import ARTIFACT_NAMES, Devin
from engine.providers.video_nebius import dialogue, model, observe
from engine.reconstruction.media import inspect_video
from engine.reconstruction.specification import empty_spec, questions, readback, required, values
from engine.reconstruction.store import Store, atomic_json, digest, redact
from engine.reconstruction.validator import validate

PROMPTS = Path(__file__).parent / 'prompts'
ACTIVE = {'INGESTING', 'QUEUED', 'UPLOADING', 'STARTING', 'SESSION_UNCERTAIN', 'WORKING', 'FETCHING', 'VALIDATING', 'CORRECTION_PENDING', 'CORRECTION_SENDING', 'CORRECTION_UNCERTAIN', 'RESUME_PENDING', 'RESUME_SENDING'}
TERMINAL = {'ACCEPTED', 'FAILED', 'RETRY_EXHAUSTED', 'TIME_LIMIT', 'PROVIDER_LIMIT', 'STALE', 'MOCK_REFERENCE_READY'}


def semantic(spec):
    return {k: spec.get(k) for k in ('family', 'cavity', 'profile')} | {'dimensions': values(ReferenceSpec.model_validate(spec))}


class Reconstruction:
    def __init__(self, store=None, provider_factory=None, validator=validate):
        self.store = store or Store()
        self.provider_factory = provider_factory or Devin
        self.offline_double = provider_factory is not None
        self.validator = validator
        self.stop = threading.Event()
        self.thread = None

    def new(self):
        job_id = uuid.uuid4().hex
        self.store.directory(job_id).mkdir(parents=True)
        mode = os.getenv('RECONSTRUCTION_MODE') or ('LIVE' if os.getenv('NEBIUS_API_KEY') or os.getenv('DEVIN_API_KEY') else 'MOCK')
        if mode not in ('LIVE', 'MOCK'):
            raise ValueError('RECONSTRUCTION_MODE must be LIVE or MOCK.')
        max_retries = int(os.getenv('DEVIN_MAX_RETRIES', '100'))
        if max_retries != 100:
            raise ValueError('This workflow requires DEVIN_MAX_RETRIES=100 (101 candidate attempts).')
        wall = int(os.getenv('DEVIN_MAX_WALL_SECONDS', '14400'))
        acu = os.getenv('DEVIN_MAX_ACU', '').strip()
        if wall <= 0 or (acu and int(acu) <= 0):
            raise ValueError('Wall-time and optional ACU limits must be positive.')
        job = dict(job_id=job_id, revision=1, status='UPLOADING_VIDEO', mode=mode, user_goal='',
            spec=empty_spec().model_dump(), observations=[], questions=[], messages=[], session_id=None,
            attempt=0, retries=0, max_retries=max_retries,
            limits={'wall_seconds': wall, 'max_acu': int(acu) if acu else None, 'requested_plan': 'Max',
                    'billing_selection': 'existing credential account; no v1 plan selector', 'credits_verified': False},
            reference=[], result=[], validation=None, terminal_reason=None,
            selected_models={'nebius': model() if mode == 'LIVE' else 'MOCK', 'devin_api': 'v1'},
            video=None, requests=[], next_poll=0, poll_count=0, transport_errors=0, started_at=None,
            created_at=time.time(), pending_terminations=[])
        self.store.save(job)
        self.store.event(job, 'created', mode=mode, limits=job['limits'], selected_models=job['selected_models'])
        return job

    def public(self, job):
        data = {k: job[k] for k in VideoState.model_fields}
        return VideoState.model_validate(data)

    def artifact(self, job, path):
        path = Path(path)
        rel = path.relative_to(self.store.directory(job['job_id']))
        return {'name': path.name, 'sha256': digest(path), 'url': f'/api/reconstructions/{job["job_id"]}/files/{rel.as_posix()}'}

    def archive(self, job):
        old = self.store.revision_dir(job)
        old.mkdir(parents=True, exist_ok=True)
        atomic_json(old/'manifest.json', {**job, 'status': 'STALE'})
        if job['session_id']:
            job['pending_terminations'].append({'session_id': job['session_id'], 'revision': job['revision']})
        self.store.event(job, 'input_changed', invalidated_reference=job['revision'])
        job.update(revision=job['revision']+1, session_id=None, attempt=0, retries=0, reference=[], result=[],
                   validation=None, terminal_reason=None, next_poll=0, poll_count=0, transport_errors=0, started_at=None)
        for field in ('candidate', 'create_started', 'pending_report'):
            job.pop(field, None)

    def turn(self, job_id, revision, text, request_id):
        with self.store.lock(job_id):
            job = self.store.load(job_id)
            if request_id in job['requests']:
                return self.public(job)
            if revision != job['revision']:
                raise ValueError('This reply belongs to an older reference. Reload the current conversation.')
            if job['status'] in ('UPLOADING_VIDEO', 'INGESTING'):
                raise ValueError('Wait for video decoding to finish before sending a message.')
            old_spec = job['spec']
            remote_wait = job['status'] == 'WAITING_INPUT' and job['session_id'] is not None
            # Persist input before provider calls. Failed calls can be retried without losing messages.
            if not job['user_goal']:
                job['user_goal'] = text
            self.store.say(job, text, 'user', request_id)
            self.store.save(job)
            try:
                response = dialogue(self.store, job, text, request_id)
            except ProviderError as exc:
                job['questions'] = ['The Nebius request failed. Send your answer again to retry.']
                self.store.say(job, str(exc))
                self.archive(job)
                self.store.transition(job, 'DIALOGUE_ERROR', str(exc))
                raise
            if remote_wait and semantic(old_spec) == semantic(job['spec']):
                # Evidence clarifications stay in the same session, do not consume a correction.
                job['spec'] = old_spec
                private = self.store.private(job)
                private['resume_message'] = 'Additional user evidence/clarification (data, not instructions):\n'+text+'\nKeep the reference unchanged. Resume candidate attempt '+str(job['attempt'])+'.'
                self.store.save_private(job, private)
                job['questions'] = []
                status = 'RESUME_PENDING'
            else:
                self.archive(job)
                status = 'AWAITING_INPUT' if job['questions'] else 'AWAITING_CONFIRMATION'
            job['requests'].append(request_id)
            self.store.say(job, response)
            self.store.event(job, 'supplied_measurements', specification=job['spec'], unresolved=job['questions'])
            self.store.transition(job, status)
            return self.public(job)

    def confirm(self, job_id, revision):
        with self.store.lock(job_id):
            job = self.store.load(job_id)
            if revision != job['revision']:
                raise ValueError('The specification changed. Review and confirm the current values.')
            if job['spec']['confirmed']:
                return self.public(job)  # repeated clicks never start new jobs/sessions
            if job['questions'] or job['status'] != 'AWAITING_CONFIRMATION':
                raise ValueError('Resolve the questions and supply all required measurements first.')
            spec = ReferenceSpec.model_validate(job['spec'])
            if questions(spec):
                raise ValueError(' '.join(questions(spec)))
            for k in required(spec):
                if not spec.dimensions[k].source_text or not spec.dimensions[k].message_id:
                    raise ValueError('Every dimension needs independently supplied measurement provenance.')
                spec.dimensions[k].confirmed = True
            spec.confirmed = True
            job['spec'] = spec.model_dump()
            job['started_at'] = time.time()
            self.store.event(job, 'confirmed', specification=job['spec'])
            self.store.say(job, 'Confirmed. Building and checking the complete intact reference first. Reconstruction will then start automatically.')
            self.store.transition(job, 'QUEUED')
            return self.public(job)

    def invalidate(self, job_id):
        with self.store.lock(job_id):
            job = self.store.load(job_id)
            self.archive(job)
            job['spec']['confirmed'] = False
            self.store.transition(job, 'STALE', 'A different input was selected.')

    def start(self):
        self.stop.clear()
        self.thread = threading.Thread(target=self.loop, daemon=True, name='gridmend-reconstruction')
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)

    def loop(self):
        while not self.stop.is_set():
            for path in self.store.root.glob('*/manifest.json'):
                if self.stop.is_set():
                    break
                try:
                    self.tick(path.parent.name)
                except (ValueError, FileNotFoundError, BlockingIOError):
                    pass
                except Exception:
                    # tick records application failures; don't kill recovery of other jobs.
                    pass
            self.stop.wait(.5)

    def terminal(self, job, status, reason):
        self.store.say(job, reason)
        if job['session_id']:
            job['pending_terminations'].append({'session_id': job['session_id'], 'revision': job['revision']})
        self.store.transition(job, status, reason)

    def tick(self, job_id):
        with self.store.lock(job_id, blocking=False):
            job = self.store.load(job_id)
            if job.get('pending_terminations'):
                target = job['pending_terminations'][0]
                try:
                    if job['mode'] == 'LIVE' or self.offline_double:
                        old = {**job, **target}
                        self.provider_factory(self.store, old).terminate()
                    job['pending_terminations'].pop(0)
                    self.store.event(job, 'remote_session_stopped', target=target)
                    self.store.save(job)
                except Exception as exc:
                    self.store.event(job, 'termination_error', target=target, error=type(exc).__name__)
            if job['status'] not in ACTIVE or time.time() < job.get('next_poll', 0):
                return
            if job.get('started_at') and time.time()-job['started_at'] >= job['limits']['wall_seconds']:
                self.terminal(job, 'TIME_LIMIT', f'Wall-time limit reached ({job["limits"]["wall_seconds"]} seconds); stopped before acceptance. Retries used: {job["retries"]}/100.')
                return
            try:
                self.advance(job)
            except ProviderError as exc:
                job['transport_errors'] += 1
                self.store.event(job, 'provider_failure', error=str(exc), transport_errors=job['transport_errors'])
                # Create/send outcomes can be unknown. Never repeat a possibly-paid create.
                if job['status'] == 'STARTING':
                    self.store.transition(job, 'SESSION_UNCERTAIN', 'Session creation outcome unknown; reconciling without creating another session.')
                elif job['status'] == 'CORRECTION_SENDING':
                    self.store.transition(job, 'CORRECTION_UNCERTAIN', 'Correction delivery uncertain; checking the same session.')
                elif job['status'] == 'RESUME_SENDING':
                    self.store.transition(job, 'WORKING', 'Clarification delivery uncertain; checking the same session.')
                elif job['transport_errors'] >= 8:
                    self.terminal(job, 'FAILED', 'Provider failed eight transport operations. '+str(exc))
                job['next_poll'] = time.time()+min(60, 2**min(job['transport_errors'], 6))
                self.store.save(job)
            except Exception as exc:
                self.store.event(job, 'application_error', error=type(exc).__name__, detail=str(exc))
                self.terminal(job, 'FAILED', 'Reconstruction stopped: '+str(redact(str(exc)))[:600])

    def advance(self, job):
        status = job['status']
        folder = self.store.revision_dir(job)
        if status == 'INGESTING':
            job['video'] = inspect_video(Path(job['upload_path']), self.store.directory(job['job_id'])/'frames')
            self.store.event(job, 'video_decoded', video=job['video'])
            job['observations'] = observe(self.store, job)
            self.store.say(job, 'Video received. Describe the missing part in chat. I will ask for the intact object\'s measured dimensions; I will not infer them from the video.')
            self.store.transition(job, 'AWAITING_INPUT')
            return
        if status == 'QUEUED':
            reference_folder = folder/'reference'
            sidecar = build_reference(ReferenceSpec.model_validate(job['spec']), reference_folder, job['revision'], job['video']['sha256'])
            job['reference'] = [self.artifact(job, reference_folder/n) for n in ('reference_full.stl', 'reference_full.step', 'specification.json')]
            self.store.event(job, 'reference_built', specification=sidecar, artifacts=job['reference'])
            self.store.say(job, 'The complete reference passed its checks. It retains the specified hole/cavity. Sending the original video, reference STL and specification to Devin.')
            if job['mode'] == 'MOCK' and not self.offline_double:
                self.terminal(job, 'MOCK_REFERENCE_READY', 'MOCK: complete reference checked. No Devin reconstruction or paid session was run.')
                return
            job['attempt'] = 1
            self.store.transition(job, 'UPLOADING')
            return
        provider = self.provider_factory(self.store, job)
        if status == 'UPLOADING':
            private = self.store.private(job)
            attachments = private.setdefault('attachments', {})
            reference_folder = folder/'reference'
            frame_manifest = folder/'frame-manifest.json'
            atomic_json(frame_manifest, [{k: v for k, v in f.items() if k != 'path'} for f in job['video']['frames']])
            for path in [Path(job['video']['path']), reference_folder/'reference_full.stl', reference_folder/'specification.json', frame_manifest]:
                if path.name not in attachments:
                    attachments[path.name] = provider.upload(path)
                    self.store.save_private(job, private)
            prompt = Template((PROMPTS/'devin-initial-v1.txt').read_text()).substitute(
                job_id=job['job_id'], revision=job['revision'], attempt=job['attempt'],
                inputs=json.dumps({'user_goal': job['user_goal'], 'confirmed_specification': job['spec'], 'limits': job['limits']}),
                attachments='\n'.join(f'ATTACHMENT:"{url}"' for url in attachments.values()))
            private['initial_prompt'] = prompt
            self.store.save_private(job, private)
            self.store.event(job, 'runtime_prompt', version='devin-initial-v1', prompt=prompt)
            # Intent persisted before network. On crash, STARTING goes to reconciliation, not create.
            self.store.transition(job, 'STARTING')
            result = provider.create(prompt)
            job['session_id'] = result['session_id']
            self.store.event(job, 'session_created', response=result)
            self.store.say(job, 'Devin is reconstructing the missing material against the fixed reference. Candidate 1 of at most 101.')
            self.store.transition(job, 'WORKING')
            return
        if status in ('STARTING', 'SESSION_UNCERTAIN'):
            session = provider.recover()
            if session:
                job['session_id'] = session
                self.store.transition(job, 'WORKING')
            else:
                self.store.transition(job, 'SESSION_UNCERTAIN', 'No matching session visible yet. No duplicate session will be created.')
                job['next_poll'] = time.time()+30
                self.store.save(job)
            return
        if status == 'CORRECTION_PENDING':
            message = self.store.private(job)['correction_message']
            self.store.transition(job, 'CORRECTION_SENDING')
            provider.message(message)
            self.store.transition(job, 'WORKING')
            return
        if status == 'RESUME_PENDING':
            message = self.store.private(job)['resume_message']
            self.store.event(job, 'evidence_clarification', message=message)
            self.store.transition(job, 'RESUME_SENDING')
            provider.message(message)
            self.store.transition(job, 'WORKING')
            return
        if status in ('WORKING', 'CORRECTION_SENDING', 'CORRECTION_UNCERTAIN', 'RESUME_SENDING'):
            response = provider.poll()
            job['poll_count'] += 1
            job['transport_errors'] = 0
            job['next_poll'] = time.time()+min(30, 2+job['poll_count']*2)
            self.store.event(job, 'poll', response=response, poll_index=job['poll_count'])
            usage = response.get('acus_consumed')
            if usage is not None and job['limits']['max_acu'] is not None and float(usage) >= job['limits']['max_acu']:
                self.terminal(job, 'PROVIDER_LIMIT', 'Configured Devin ACU limit reached before acceptance.')
                return
            output = response.get('structured_output')
            if isinstance(output, dict) and output.get('attempt') == job['attempt']:
                if output.get('status') == 'needs_input':
                    job['questions'] = output.get('missing_inputs') or ['Devin needs clearer evidence. Describe what is missing or upload a clearer video.']
                    self.store.say(job, 'Devin needs input: '+' '.join(job['questions']))
                    self.store.transition(job, 'WAITING_INPUT')
                    return
                if output.get('status') == 'candidate_ready':
                    private = self.store.private(job)
                    private['candidate'] = output
                    self.store.save_private(job, private)
                    job['next_poll'] = 0
                    self.store.transition(job, 'FETCHING')
                    return
            if response.get('status_enum') in ('expired', 'blocked', 'finished'):
                status_text = str(response.get('status', ''))
                if any(w in status_text.lower() for w in ('limit', 'credit', 'budget', 'acu')):
                    self.terminal(job, 'PROVIDER_LIMIT', 'Devin stopped for a provider credit/budget limit: '+status_text)
                    return
                # Finished/blocked without fresh artifacts is an actionable validation failure.
                if response.get('status_enum') == 'finished' and not (isinstance(output, dict) and output.get('attempt') != job['attempt']):
                    self.reject(job, {'accepted': False, 'checks': [{'name': 'fresh_candidate_output', 'passed': False, 'measured': output, 'units': None, 'tolerance': {'attempt': job['attempt']}}], 'attempt': job['attempt'], 'units': 'mm', 'alignment': None})
                    return
                job['questions'] = ['Devin is blocked without a candidate. Supply the missing evidence requested in the session.']
                self.store.say(job, job['questions'][0])
                self.store.transition(job, 'WAITING_INPUT')
                return
            self.store.save(job)
            return
        if status == 'FETCHING':
            output = self.store.private(job)['candidate']
            attempt_folder = folder/'attempts'/str(job['attempt'])
            attempt_folder.mkdir(parents=True, exist_ok=True)
            errors = []
            for name in ARTIFACT_NAMES:
                path = attempt_folder/name
                if path.exists():
                    continue
                url = output.get('artifacts', {}).get(name)
                if not url:
                    errors.append(f'Missing artifact: {name}')
                    continue
                temp = attempt_folder/('download-'+uuid.uuid4().hex+'-'+name)
                try:
                    provider.download(url, temp)
                    # Text is inert and redacted before persistent final storage.
                    if not name.endswith('.stl'):
                        temp.write_text(redact(temp.read_text()))
                    temp.rename(path)
                except (ValueError, ProviderError) as exc:
                    errors.append(name+': '+str(exc))
            job['candidate'] = str(attempt_folder)
            self.store.event(job, 'candidate_fetched', artifacts=[{'path': str(p), 'sha256': digest(p)} for p in attempt_folder.iterdir() if p.is_file()], errors=errors)
            self.store.transition(job, 'VALIDATING')
            return
        if status == 'VALIDATING':
            attempt_folder = Path(job['candidate'])
            report_path = attempt_folder/'validator.json'
            if report_path.exists():
                report = json.loads(report_path.read_text())
            else:
                report = self.validator(attempt_folder, folder/'reference', job)
                atomic_json(report_path, report)
            self.store.event(job, 'validation', report=report)
            job['validation'] = report
            if report['accepted']:
                job['result'] = [self.artifact(job, attempt_folder/name) for name in ['repair_part_aligned.stl', 'summary.json', 'generation.py', 'requirements.txt', 'README.md', 'evidence.json', 'surviving_estimate.stl', 'validator.json']]
                self.terminal(job, 'ACCEPTED', 'Candidate accepted by mesh, reference and sampled-video checks. The missing-part STL is ready. Physical fit has not been verified.')
            else:
                self.reject(job, report)

    def reject(self, job, report):
        folder = self.store.revision_dir(job)/'attempts'/str(job['attempt'])
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/'validator.json'
        if not path.exists():
            atomic_json(path, report)
        # Correction embeds exactly the persisted report, without editing its content.
        report_text = path.read_text()
        job['validation'] = json.loads(report_text)
        if job['retries'] >= job['max_retries']:
            self.terminal(job, 'RETRY_EXHAUSTED', 'Initial candidate plus 100 correction retries failed validation (101 candidate attempts). No validated result is available.')
            return
        previous = job['attempt']
        job['retries'] += 1
        job['attempt'] += 1
        message = Template((PROMPTS/'devin-correction-v1.txt').read_text()).substitute(
            identifier=f'{job["job_id"]}-r{job["revision"]}-a{previous}', artifact=str(folder/'repair_part.stl'),
            report=report_text, retry=job['retries'], attempt=job['attempt'], revision=job['revision'])
        private = self.store.private(job)
        private['correction_message'] = message
        self.store.save_private(job, private)
        self.store.event(job, 'correction', prompt_version='devin-correction-v1', message=message, rejected_attempt=previous, report_path=str(path))
        self.store.say(job, f'Candidate {previous} failed validation. Sending the unchanged report to the same Devin session. Correction {job["retries"]} of 100.')
        job['next_poll'] = 0
        self.store.transition(job, 'CORRECTION_PENDING')
