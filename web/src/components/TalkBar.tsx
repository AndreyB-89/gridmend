import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api.ts";
import type { VoiceResult } from "../types.ts";

const MAX_SECONDS = 30;
const HOLD_MS = 450; // press longer than this = push-to-talk; shorter = tap to toggle
const BARS = 36;

interface Props {
  busy: boolean;
  onError: (msg: string) => void;
  onTranscript: (res: VoiceResult) => void;
  onTypeInstead: () => void;
}

function pickMime(): string {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  if (typeof MediaRecorder === "undefined") return "";
  return options.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

/** Hi-vis push-to-talk bar. Tap to start and tap to send, or hold (button or Space) and release. */
export function TalkBar({ busy, onError, onTranscript, onTypeInstead }: Props) {
  const [recording, setRecording] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(MAX_SECONDS);
  const [transcribing, setTranscribing] = useState(false);
  const [levels, setLevels] = useState<number[]>(() => Array.from({ length: BARS }, (_, i) => 0.12 + 0.08 * Math.abs(Math.sin(i * 0.7))));

  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const pressStartRef = useRef(0);
  const startedByPressRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const rafRef = useRef(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const recordingRef = useRef(false);
  const cancelRef = useRef(false);

  const idle = () => setLevels(Array.from({ length: BARS }, (_, i) => 0.12 + 0.08 * Math.abs(Math.sin(i * 0.7))));

  const stop = useCallback((cancel = false) => {
    cancelRef.current = cancel;
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    cancelAnimationFrame(rafRef.current);
    void audioCtxRef.current?.close().catch(() => undefined);
    audioCtxRef.current = null;
    const rec = recRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
    recordingRef.current = false;
    setRecording(false);
    setSecondsLeft(MAX_SECONDS);
    idle();
  }, []);

  const send = useCallback(
    async (blob: Blob, mime: string) => {
      setTranscribing(true);
      try {
        const ext = mime.includes("ogg") ? "ogg" : mime.includes("mp4") ? "m4a" : "webm";
        const res = await api.voice(blob, `voice.${ext}`);
        onTranscript(res);
      } catch (e) {
        onError(`Voice: ${errorMessage(e)}`);
      } finally {
        setTranscribing(false);
      }
    },
    [onError, onTranscript],
  );

  const start = useCallback(async () => {
    if (recordingRef.current) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      onError("This browser cannot record audio here. Use \"Type instead\".");
      return;
    }
    recordingRef.current = true;
    cancelRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickMime();
      const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        if (cancelRef.current) return;
        const type = rec.mimeType || mime || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        if (blob.size < 500) {
          onError("The recording was too short. Tap the talk bar, speak, then tap again.");
          return;
        }
        void send(blob, type);
      };
      recRef.current = rec;
      rec.start();
      setRecording(true);
      setSecondsLeft(MAX_SECONDS);

      // Live waveform from the real microphone level.
      try {
        const ctx = new AudioContext();
        audioCtxRef.current = ctx;
        const src = ctx.createMediaStreamSource(stream);
        const an = ctx.createAnalyser();
        an.fftSize = 512;
        src.connect(an);
        const buf = new Uint8Array(an.fftSize);
        const hist: number[] = Array(BARS).fill(0.1);
        let last = 0;
        const tick = (now: number) => {
          if (now - last > 70) {
            last = now;
            an.getByteTimeDomainData(buf);
            let sum = 0;
            for (let i = 0; i < buf.length; i++) {
              const v = (buf[i] - 128) / 128;
              sum += v * v;
            }
            const rms = Math.min(1, Math.sqrt(sum / buf.length) * 4.5);
            hist.shift();
            hist.push(0.1 + rms * 0.9);
            setLevels([...hist]);
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      } catch {
        /* waveform is decoration only */
      }

      const t0 = Date.now();
      timerRef.current = window.setInterval(() => {
        const left = MAX_SECONDS - Math.floor((Date.now() - t0) / 1000);
        setSecondsLeft(left);
        if (left <= 0) stop();
      }, 250);
      if (!recordingRef.current) stop();
    } catch (e) {
      recordingRef.current = false;
      setRecording(false);
      onError(`Microphone: ${errorMessage(e)}`);
    }
  }, [onError, send, stop]);

  const locked = busy || transcribing;

  const pressDown = useCallback(() => {
    if (locked) return;
    if (recordingRef.current) {
      startedByPressRef.current = false;
      stop();
      return;
    }
    pressStartRef.current = Date.now();
    startedByPressRef.current = true;
    void start();
  }, [locked, start, stop]);

  const pressUp = useCallback(() => {
    if (!startedByPressRef.current) return;
    startedByPressRef.current = false;
    if (Date.now() - pressStartRef.current >= HOLD_MS) stop();
  }, [stop]);

  useEffect(() => {
    const isTyping = (t: EventTarget | null) => {
      const el = t as HTMLElement | null;
      return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.tagName === "BUTTON" || el.isContentEditable);
    };
    const down = (e: KeyboardEvent) => {
      if (e.key === "Escape" && recordingRef.current) {
        stop(true);
        return;
      }
      if (e.code !== "Space" || e.repeat || isTyping(e.target)) return;
      e.preventDefault();
      pressDown();
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space" || isTyping(e.target)) return;
      e.preventDefault();
      pressUp();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [pressDown, pressUp, stop]);

  useEffect(() => () => stop(true), [stop]);

  const t1 = transcribing ? "Writing it down…" : recording ? "Listening" : busy ? "Reading your answer…" : "Tap to talk";
  const t2 = transcribing
    ? "Speech to text is working"
    : recording
      ? "Tap again to send"
      : "One value at a time";

  return (
    <div className="dock">
      <button
        type="button"
        className={`ptt ${recording ? "rec" : ""} ${locked ? "busy" : ""}`}
        aria-pressed={recording}
        aria-disabled={locked}
        onPointerDown={(e) => {
          e.preventDefault();
          pressDown();
        }}
        onPointerUp={pressUp}
        onPointerLeave={() => recordingRef.current && startedByPressRef.current && pressUp()}
        onKeyDown={(e) => {
          if (e.code === "Space" || e.key === "Enter") {
            e.preventDefault();
            if (!e.repeat) pressDown();
          }
        }}
        onKeyUp={(e) => {
          if (e.code === "Space" || e.key === "Enter") {
            e.preventDefault();
            pressUp();
          }
        }}
      >
        <span className="mic" aria-hidden="true">
          <svg width="34" height="34" viewBox="0 0 24 24">
            <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
            <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        </span>
        <span className="txt">
          <span className="t1">{t1}</span>
          <span className="t2">{t2}</span>
        </span>
        <span className="wave" aria-hidden="true">
          {levels.map((l, i) => (
            <i key={i} style={{ height: `${Math.round(6 + l * 54)}px` }} />
          ))}
        </span>
        <span className="count" aria-live="off">
          0:{String(Math.max(0, secondsLeft)).padStart(2, "0")}
        </span>
      </button>
      <button type="button" className="btn type-btn" onClick={onTypeInstead}>
        Type instead
      </button>
    </div>
  );
}
