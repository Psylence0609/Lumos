/**
 * Returns live microphone frequency levels for visualization.
 * Uses Web Audio API: getUserMedia → AudioContext → AnalyserNode → getByteFrequencyData.
 * Only active when isActive is true; cleans up stream and context when false.
 */
import { useState, useEffect, useRef } from "react";

const BAR_COUNT = 48;
const SMOOTHING = 0.7;

export function useMicrophoneLevels(isActive: boolean): number[] {
  const [levels, setLevels] = useState<number[]>(() => Array(BAR_COUNT).fill(0));
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);
  const dataRef = useRef<Uint8Array | null>(null);

  useEffect(() => {
    if (!isActive) {
      setLevels(Array(BAR_COUNT).fill(0));
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (ctxRef.current?.state !== "closed") {
        ctxRef.current?.close();
        ctxRef.current = null;
      }
      analyserRef.current = null;
      dataRef.current = null;
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;

        const ctx = new AudioContext();
        if (cancelled) {
          ctx.close();
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        ctxRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = SMOOTHING;
        analyser.minDecibels = -60;
        analyser.maxDecibels = -10;
        source.connect(analyser);
        analyserRef.current = analyser;

        const bufferLength = analyser.frequencyBinCount;
        const data = new Uint8Array(bufferLength);
        dataRef.current = data;

        const update = () => {
          if (cancelled || !analyserRef.current || !dataRef.current) return;
          analyserRef.current.getByteFrequencyData(dataRef.current as Uint8Array<ArrayBuffer>);
          const raw = dataRef.current;
          const step = Math.floor(raw.length / BAR_COUNT);
          const next = Array.from({ length: BAR_COUNT }, (_, i) => {
            let sum = 0;
            for (let j = 0; j < step; j++) sum += raw[i * step + j] ?? 0;
            return (sum / step) / 255;
          });
          setLevels(next);
          rafRef.current = requestAnimationFrame(update);
        };
        rafRef.current = requestAnimationFrame(update);
      } catch (e) {
        if (!cancelled) console.warn("Microphone levels unavailable:", e);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [isActive]);

  return levels;
}
