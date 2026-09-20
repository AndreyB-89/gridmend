import { useEffect, useRef, useState } from "react";
import type { VoiceResult } from "./types.ts";
import { TalkBar } from "./components/TalkBar.tsx";
import { Icon, TraceTag } from "./components/Bits.tsx";
import { useVideo, VideoPreview, VideoChat, VideoResult } from "./video.tsx";

export default function App() {
  const reconstruction = useVideo();
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [typeOpen, setTypeOpen] = useState(false);
  const [voice, setVoice] = useState<VoiceResult | null>(null);
  const [transcript, setTranscript] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);
  const typeRef = useRef<HTMLInputElement>(null);
  const canSend = !!reconstruction.job && !reconstruction.busy &&
    !["INGESTING", "FAILED", "STALE"].includes(reconstruction.job.status);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [reconstruction.job?.messages.length, voice]);

  const onUpload = (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setTyped("");
    setVoice(null);
    setTypeOpen(true);
    void reconstruction.upload(file);
  };

  const sendTyped = async () => {
    if (!canSend || !typed.trim()) return;
    if (await reconstruction.send(typed.trim())) setTyped("");
  };

  const onTranscript = (result: VoiceResult) => {
    setVoice(result);
    setTranscript(result.transcript);
  };

  const useTranscript = async () => {
    if (!canSend || !transcript.trim()) return;
    if (await reconstruction.send(transcript.trim())) setVoice(null);
  };

  const openType = () => {
    setTypeOpen(true);
    setTimeout(() => typeRef.current?.focus(), 30);
  };

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><h1>FIMI</h1></div>
        <p className="job">Rebuild a broken part from a photo or video</p>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <Icon name="warn" size={22} />
          <p>{error}</p>
          <button type="button" className="btn small ghost-dark" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <main className="cols">
        <section className="col left" aria-label="Photo or video">
          <div className="panel photo">
            {reconstruction.active ? (
              <VideoPreview video={reconstruction} onUpload={onUpload} />
            ) : (
              <div className="photo-empty">
                <label className="btn primary file-btn">
                  <Icon name="up" size={22} />
                  Upload photo or video
                  <input type="file" accept="image/jpeg,image/png,image/webp,video/*,.mov,.mkv" onChange={e => onUpload(e.target.files?.[0])} />
                </label>
              </div>
            )}
          </div>
        </section>

        <section className="panel chat" aria-label="Conversation">
          <div className="chat-head"><h2>Talk it through</h2></div>
          <div className="thread" ref={threadRef} aria-live="polite">
            {reconstruction.active ? <VideoChat video={reconstruction} /> : (
              <div className="msg ai">
                <div className="av" aria-hidden="true">AI</div>
                <div className="bubble">
                  <p>Hello. I rebuild broken parts from a photo or video. You confirm every measurement before I build.</p>
                </div>
              </div>
            )}
            {voice && (
              <div className="msg me">
                <div className="av" aria-hidden="true">You</div>
                <div className="bubble">
                  <div className="voice-line"><span>Voice</span><TraceTag trace={voice.trace} /></div>
                  <label className="sr" htmlFor="transcript">Check and correct what I heard</label>
                  <textarea id="transcript" value={transcript} maxLength={2000} rows={2} onChange={e => setTranscript(e.target.value)} />
                  <p className="soft">Check the words. Fix them if needed.</p>
                  <div className="bubble-actions">
                    <button type="button" className="btn dark" disabled={!canSend || !transcript.trim()} onClick={() => void useTranscript()}>Use this</button>
                    <button type="button" className="btn ghost" onClick={() => setVoice(null)}>Discard</button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <p className="talk-hint">Describe the part and include your measurements. Review and confirm before building.</p>
          {(typeOpen || reconstruction.active) && (
            <form className="typebox" onSubmit={e => { e.preventDefault(); void sendTyped(); }}>
              <label className="sr" htmlFor="typeIn">Describe the reconstruction and measurements</label>
              <input
                id="typeIn"
                ref={typeRef}
                value={typed}
                maxLength={2000}
                placeholder="Describe the part and its measurements"
                onChange={e => setTyped(e.target.value)}
                onKeyDown={e => e.key === "Escape" && setTypeOpen(false)}
              />
              <button type="submit" className="btn" disabled={!canSend || !typed.trim()}>Send</button>
            </form>
          )}
          <TalkBar busy={reconstruction.busy} onError={setError} onTranscript={onTranscript} onTypeInstead={openType} />
        </section>

        <section className="col right" aria-label="Rebuilt part">
          <VideoResult video={reconstruction} />
        </section>
      </main>
    </div>
  );
}
