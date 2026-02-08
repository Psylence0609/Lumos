/**
 * Hold-to-talk microphone button with visual feedback.
 *
 * Press and hold → starts recording (browser STT), opens circular popup that emerges from the button with live audio visualization.
 * Release → sends transcribed text to the command handler and closes popup.
 */
import { useState, useCallback, useRef, useEffect, useLayoutEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useMicrophoneLevels } from "@/hooks/useMicrophoneLevels";

/* inject keyframes */
const cssId = "vcb-anim-css";
const css = `
@keyframes vcb-bar { 0%,100%{height:4px;transform:translateZ(0)} 50%{height:14px;transform:translateZ(0)} }
`;

interface Props {
  /** Called when the user finishes speaking with a usable transcript */
  onTranscript: (text: string) => void;
  /** Whether the parent is processing a previous command */
  disabled?: boolean;
  /** Optional: compact size for inline use */
  compact?: boolean;
  /** Optional class overrides */
  className?: string;
}

/* ── Waveform equalizer bars (small, in-button) ── */
function WaveformBars({ compact }: { compact: boolean }) {
  const sz = compact ? "h-3" : "h-4";
  return (
    <div className={cn("flex items-center justify-center gap-[2px]", sz)}>
      {[0, 0.12, 0.06, 0.18, 0.09].map((delay, i) => (
        <span
          key={i}
          className="w-[2px] rounded-full bg-red-400"
          style={{ animation: `vcb-bar 0.5s ${delay}s ease-in-out infinite`, minHeight: 3 }}
        />
      ))}
    </div>
  );
}

const POPUP_SIZE = 320;

/* Build SVG path for a blob whose radius at each angle follows levels (interpolated). */
function blobPathFromLevels(levels: number[], cx: number, cy: number, baseR: number, bulge: number, points: number): string {
  if (levels.length === 0) return "";
  const step = (2 * Math.PI) / points;
  const d: string[] = [];
  for (let k = 0; k <= points; k++) {
    const angle = k * step - Math.PI / 2;
    const levelIndex = (k / points) * levels.length;
    const i0 = Math.floor(levelIndex) % levels.length;
    const i1 = (i0 + 1) % levels.length;
    const t = levelIndex - Math.floor(levelIndex);
    const level = levels[i0] * (1 - t) + levels[i1] * t;
    const r = baseR + level * bulge;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    d.push(`${k === 0 ? "M" : "L"} ${x} ${y}`);
  }
  d.push("Z");
  return d.join(" ");
}

/* ── Circular popup: blob that fluctuates with voice level ── */
function VoicePopup({
  levels,
  transcript,
  interimText,
  origin,
}: {
  levels: number[];
  transcript: string;
  interimText: string;
  origin: { x: number; y: number };
}) {
  const displayText = transcript || interimText;
  const cx = POPUP_SIZE / 2;
  const cy = POPUP_SIZE / 2;
  const baseRadius = 72;
  const maxBulge = 56;
  const pathPoints = 80;
  const blobPath = blobPathFromLevels(levels, cx, cy, baseRadius, maxBulge, pathPoints);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-[99] flex items-center justify-center"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/65 backdrop-blur-sm"
        aria-hidden
      />

      {/* Circle — scale from 0 to emerge */}
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0, opacity: 0 }}
        transition={{ type: "spring", stiffness: 280, damping: 26 }}
        className="absolute z-[100] rounded-full flex flex-col items-center justify-end overflow-hidden"
        style={{
          width: POPUP_SIZE,
          height: POPUP_SIZE,
          left: origin.x - POPUP_SIZE / 2,
          top: origin.y - POPUP_SIZE / 2,
          transformOrigin: "center center",
          background: "linear-gradient(180deg, rgba(18,18,22,0.98) 0%, rgba(12,12,16,0.99) 100%)",
          border: "1px solid rgba(255,255,255,0.1)",
          boxShadow: "0 0 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)",
        }}
      >
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-6 pt-12">
          {/* Voice-reactive blob */}
          <svg
            className="absolute pointer-events-none transition-all duration-75 ease-out"
            width={POPUP_SIZE}
            height={POPUP_SIZE}
            style={{ left: 0, top: 0 }}
          >
            <defs>
              <linearGradient id="vcb-blob-fill" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="hsl(270, 70%, 45%)" stopOpacity="0.85" />
                <stop offset="50%" stopColor="hsl(280, 75%, 52%)" stopOpacity="0.9" />
                <stop offset="100%" stopColor="hsl(260, 80%, 58%)" stopOpacity="0.85" />
              </linearGradient>
              <filter id="vcb-blob-glow">
                <feGaussianBlur stdDeviation="8" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <path
              d={blobPath}
              fill="url(#vcb-blob-fill)"
              filter="url(#vcb-blob-glow)"
              style={{ opacity: 0.95 }}
            />
          </svg>

          {/* Text at bottom of circle */}
          <div className="relative z-10 flex flex-col items-center gap-1.5 px-4 text-center">
            <p className="text-xs sm:text-sm text-zinc-400 min-h-[1.25rem]">
              {displayText ? (
                <>
                  <span className="text-zinc-200 italic">&ldquo;{displayText}&rdquo;</span>
                  <motion.span
                    animate={{ opacity: [1, 0] }}
                    transition={{ repeat: Infinity, duration: 0.8 }}
                    className="ml-0.5"
                  >
                    |
                  </motion.span>
                </>
              ) : (
                "Listening…"
              )}
            </p>
            <p className="text-[10px] text-zinc-500">Release to send</p>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function VoiceChatButton({
  onTranscript,
  disabled = false,
  compact = false,
  className,
}: Props) {
  const [interimText, setInterimText] = useState("");
  const [sent, setSent] = useState(false);
  const sentRef = useRef(false);

  /* inject CSS */
  useEffect(() => {
    if (document.getElementById(cssId)) return;
    const s = document.createElement("style");
    s.id = cssId;
    s.textContent = css;
    document.head.appendChild(s);
  }, []);

  const handleResult = useCallback(
    (text: string) => {
      if (sentRef.current) return;
      sentRef.current = true;
      setSent(true);
      onTranscript(text);
      setTimeout(() => {
        setSent(false);
        sentRef.current = false;
        setInterimText("");
      }, 500);
    },
    [onTranscript]
  );

  const {
    isSupported,
    isListening,
    transcript,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    continuous: false,
    onInterim: setInterimText,
    onResult: handleResult,
    onError: (err) => {
      console.warn("STT error:", err);
      setInterimText("");
    },
  });

  const levels = useMicrophoneLevels(isListening);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [popupOrigin, setPopupOrigin] = useState({ x: 0, y: 0 });
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const HOLD_DELAY_MS = 220;

  /* Stop when pointer is released anywhere (e.g. user dragged off button) */
  useEffect(() => {
    if (!isListening) return;
    const onDocPointerUp = () => stopListening();
    document.addEventListener("pointerup", onDocPointerUp);
    document.addEventListener("pointercancel", onDocPointerUp);
    return () => {
      document.removeEventListener("pointerup", onDocPointerUp);
      document.removeEventListener("pointercancel", onDocPointerUp);
    };
  }, [isListening, stopListening]);

  useLayoutEffect(() => {
    if (!isListening || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setPopupOrigin({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    });
  }, [isListening]);

  if (!isSupported) {
    return (
      <button
        disabled
        title="Speech recognition not supported in this browser"
        className={cn(
          "flex items-center justify-center rounded-md border border-border bg-muted text-zinc-600 cursor-not-allowed",
          compact ? "h-9 w-9" : "h-10 w-10",
          className
        )}
      >
        <MicOff className={compact ? "w-4 h-4" : "w-5 h-5"} />
      </button>
    );
  }

  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    if (disabled) return;
    if (holdTimerRef.current) return;
    sentRef.current = false;
    setSent(false);
    setInterimText("");
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setPopupOrigin({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    holdTimerRef.current = window.setTimeout(() => {
      holdTimerRef.current = null;
      startListening();
    }, HOLD_DELAY_MS);
  };

  const handlePointerUp = () => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    if (isListening) {
      stopListening();
    }
  };

  return (
    <div className="relative">
      {/* The button */}
      <motion.button
        ref={buttonRef}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onPointerCancel={handlePointerUp}
        disabled={disabled}
        whileTap={{ scale: 0.92 }}
        className={cn(
          "relative flex items-center justify-center rounded-md border transition-all duration-200 select-none touch-none",
          compact ? "h-9 w-9" : "h-10 w-10",
          isListening
            ? "bg-red-500/20 border-red-500/50 text-red-400"
            : "bg-muted border-border text-muted-foreground hover:text-foreground hover:border-zinc-500",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
        title="Hold to talk — release to send"
      >
        {/* Inner pulsing ring */}
        <AnimatePresence>
          {isListening && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: [0.4, 0.1, 0.4], scale: [1, 1.6, 1] }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ repeat: Infinity, duration: 1.5, ease: [0.45, 0, 0.55, 1] }}
              className="absolute inset-0 rounded-md border-2 border-red-500/40"
            />
          )}
        </AnimatePresence>

        {/* Outer second ring */}
        <AnimatePresence>
          {isListening && (
            <motion.span
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: [0.2, 0.05, 0.2], scale: [1.1, 1.9, 1.1] }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ repeat: Infinity, duration: 2, ease: [0.45, 0, 0.55, 1], delay: 0.3 }}
              className="absolute inset-[-4px] rounded-lg border border-red-500/20"
            />
          )}
        </AnimatePresence>

        {disabled ? (
          <Loader2 className={cn("animate-spin", compact ? "w-4 h-4" : "w-5 h-5")} />
        ) : isListening ? (
          <WaveformBars compact={compact} />
        ) : (
          <Mic className={cn(compact ? "w-4 h-4" : "w-5 h-5")} />
        )}
      </motion.button>

      {/* Circular popup — portaled so it emerges from button position */}
      <AnimatePresence>
        {isListening && (
          <VoicePopup
            levels={levels}
            transcript={transcript}
            interimText={interimText}
            origin={popupOrigin}
          />
        )}
      </AnimatePresence>

    </div>
  );
}
