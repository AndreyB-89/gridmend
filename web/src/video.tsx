import { useCallback, useEffect, useRef, useState } from 'react';
import type { VideoState } from './types.ts';
import { RingViewer } from './components/RingViewer.tsx';

const TERMINAL = new Set(['ACCEPTED', 'FAILED', 'RETRY_EXHAUSTED', 'TIME_LIMIT', 'PROVIDER_LIMIT', 'STALE', 'MOCK_REFERENCE_READY']);
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `Request failed (${res.status}).`);
  return data as T;
}
const post = <T,>(url: string, data: unknown) => request<T>(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});

export function useVideo() {
  const resetRequested = useRef(new URLSearchParams(window.location.search).get('reset') === '1');
  const [job, setJob] = useState<VideoState | null>(null);
  const [active, setActive] = useState(!resetRequested.current && !!localStorage.getItem('gridmend-video-job'));
  const [preview, setPreview] = useState<string | null>(null);
  const [mediaKind, setMediaKind] = useState<'photo' | 'video'>(localStorage.getItem('gridmend-media-kind') === 'photo' ? 'photo' : 'video');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const current = useRef<VideoState | null>(null);
  const pending = useRef(false);
  const update = useCallback((data: VideoState) => { current.current = data; setJob(data); }, []);
  useEffect(() => {
    const id = localStorage.getItem('gridmend-video-job');
    const g = generation.current;
    if (resetRequested.current) {
      resetRequested.current = false;
      localStorage.removeItem('gridmend-video-job');
      localStorage.removeItem('gridmend-media-kind');
      const url = new URL(window.location.href);
      url.searchParams.delete('reset');
      window.history.replaceState(window.history.state, '', url);
      if (id) void post(`/api/reconstructions/${id}/invalidate`, {}).catch(e => {
        if (g === generation.current) { setActive(true); setError(`Could not stop the previous reconstruction: ${e.message}`); }
      });
      return;
    }
    if (id) void request<VideoState>(`/api/reconstructions/${id}`).then(data => { if (g === generation.current) update(data); }).catch(e => { if (g === generation.current) setError(String(e.message)); });
  }, [update]);
  useEffect(() => {
    if (!job || TERMINAL.has(job.status)) return;
    let alive = true;
    let timer: number;
    const g = generation.current;
    const poll = async () => {
      try {
        const data = await request<VideoState>(`/api/reconstructions/${job.job_id}`);
        if (alive && g === generation.current && !pending.current && data.revision >= (current.current?.revision ?? 0)) update(data);
      } catch (e) { if (alive && g === generation.current) setError((e as Error).message); }
      if (alive) timer = window.setTimeout(poll, 2000);
    };
    timer = window.setTimeout(poll, 1000);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [job?.job_id, job?.status, update]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const clear = async () => {
    generation.current++;
    const old = current.current;
    current.current = null; setJob(null); setActive(false); setPreview(null); setError(null);
    pending.current = false;
    localStorage.removeItem('gridmend-video-job');
    localStorage.removeItem('gridmend-media-kind');
    if (old) await post(`/api/reconstructions/${old.job_id}/invalidate`, {});
  };
  const upload = async (file: File) => {
    const g = generation.current + 1;
    try {
      await clear();
      if (g !== generation.current) return;
      const kind = file.type.startsWith('image/') || /\.(jpe?g|png|webp)$/i.test(file.name) ? 'photo' : 'video';
      setMediaKind(kind);
      setActive(true); setBusy(true); setPreview(URL.createObjectURL(file));
      const fd = new FormData(); fd.append(kind, file);
      const data = await request<VideoState>('/api/reconstructions', {method: 'POST', body: fd});
      if (g !== generation.current) { await post(`/api/reconstructions/${data.job_id}/invalidate`, {}); return; }
      localStorage.setItem('gridmend-video-job', data.job_id);
      localStorage.setItem('gridmend-media-kind', kind);
      update(data);
    } catch (e) { if (g === generation.current) { setActive(true); setError((e as Error).message); } }
    finally { if (g === generation.current) setBusy(false); }
  };
  const send = async (text: string) => {
    const j = current.current;
    if (!j || pending.current) return false;
    pending.current = true; setBusy(true); setError(null);
    const g = generation.current;
    update({...j, reference: [], result: []});
    try {
      const data = await post<VideoState>(`/api/reconstructions/${j.job_id}/messages`, {revision: j.revision, message: text, request_id: crypto.randomUUID()});
      if (g === generation.current) { update(data); return true; }
    } catch (e) { if (g === generation.current) setError((e as Error).message); }
    finally { if (g === generation.current) { pending.current = false; setBusy(false); } }
    return false;
  };
  const confirm = async () => {
    const j = current.current;
    if (!j || pending.current) return;
    pending.current = true; setBusy(true); setError(null);
    const g = generation.current;
    try { const data = await post<VideoState>(`/api/reconstructions/${j.job_id}/confirm`, {revision: j.revision}); if (g === generation.current) update(data); }
    catch (e) { if (g === generation.current) setError((e as Error).message); }
    finally { if (g === generation.current) { pending.current = false; setBusy(false); } }
  };
  return {job, active, preview, mediaKind, busy, error, upload, clear, send, confirm};
}
export type VideoControl = ReturnType<typeof useVideo>;

export function VideoPreview({video, onUpload}: {video: VideoControl; onUpload: (file: File | undefined) => void}) {
  const source = video.preview ?? (video.job ? `/api/reconstructions/${video.job.job_id}/files/original-${video.mediaKind}.bin?status=${encodeURIComponent(video.job.status)}` : null);
  return <><div className="canvas-wrap">{source ? (video.mediaKind === 'photo'
    ? <img src={source} alt="Uploaded part" style={{width: '100%', height: '100%', objectFit: 'contain', display: 'block'}} />
    : <video src={source} controls playsInline style={{width: '100%', height: '100%', objectFit: 'contain', display: 'block'}} />) : <p className="small-note">Original preview is not available.</p>}</div>
    <div className="change-photo"><label className="link file-link">Change photo or video<input type="file" accept="image/jpeg,image/png,image/webp,video/*,.mov,.mkv" onChange={e => onUpload(e.target.files?.[0])}/></label></div></>;
}
export function VideoChat({video}: {video: VideoControl}) {
  return <>{video.job?.messages.map((m,i) => <div className={`msg ${m.role === 'user' ? 'me' : 'ai'}`} key={m.id ?? i}><div className="av" aria-hidden="true">{m.role === 'user' ? 'You' : 'AI'}</div><div className="bubble"><p style={{whiteSpace:'pre-wrap'}}>{m.text}</p></div></div>)}
    {!video.job && !video.error && <div className="msg ai"><div className="av">AI</div><div className="bubble"><p>Loading your {video.mediaKind}…</p></div></div>}
    {video.job?.status === 'INGESTING' && <div className="msg ai"><div className="av">AI</div><div className="bubble"><p>Preparing your {video.mediaKind} for reconstruction…</p></div></div>}
    {video.job?.status === 'AWAITING_CONFIRMATION' && <div className="msg ai draft"><div className="av">AI</div><div className="bubble"><p>Confirm the measurements and intact shape shown above. I will build the complete reference and start reconstruction.</p><div className="bubble-actions"><button className="btn go" disabled={video.busy} onClick={() => void video.confirm()}>Confirm and build</button></div></div></div>}
    {video.error && <div className="msg ai warn"><div className="av">!</div><div className="bubble"><p role="alert">{video.error}</p></div></div>}
    {video.busy && <div className="msg ai"><div className="av">AI</div><div className="bubble"><p>Reading your answer…</p></div></div>}
  </>;
}
export function VideoResult({video}: {video: VideoControl}) {
  const j = video.job;
  const full = j?.reference.find(a => a.name === 'reference_full.stl');
  const repair = j?.status === 'ACCEPTED' ? j.result.find(a => a.name === 'repair_part_aligned.stl') : null;
  return <div className={`viewer ${full ? 'has-model' : ''}`}><div className="v-top"><div><h2>{repair ? 'Proposed missing part' : full ? 'Complete reference' : 'Reconstruction'}</h2><p className="sub">{j?.status.replaceAll('_',' ').toLowerCase() ?? 'Waiting for photo or video'}</p></div></div>
    {full ? <RingViewer ringUrl={full.url} segmentUrl={repair?.url ?? null} referenceMode/> : <div className="viewer-empty"><p>No 3D model yet. Confirm the intact shape and measurements first.</p></div>}
    {full && <div className="legend"><span className="pill"><span className="sw y"/>Complete reference</span>{repair && <span className="pill"><span className="sw"/>Proposed missing material</span>}</div>}</div>;
}
