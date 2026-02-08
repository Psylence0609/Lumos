/**
 * Voice Alert overlay — shows when the system has a message for the user.
 *
 * Audio rules:
 * - Audio ALWAYS auto-plays when an alert arrives (threats, voice responses, etc.)
 * - A "Replay" button appears after the first play (never a "Play" button).
 * - For permission-required alerts: user holds the mic button to speak their response.
 *   The backend LLM parses intent (approve, deny, or partial instructions).
 * - Falls back to Approve / Deny buttons for quick tap responses.
 * - Info-only alerts auto-dismiss after audio finishes (with a Dismiss button as fallback).
 */
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Volume2, Check, X, Mic, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/utils";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import type { VoiceAlert as VoiceAlertType } from "@/types";

/** How long (ms) to keep an info-only alert visible after audio finishes */
const AUTO_DISMISS_DELAY = 4000;

/* inject keyframes */
const cssId = "va-anim-css";
const css = `
@keyframes va-bar { 0%,100%{height:3px} 50%{height:12px} }
@keyframes va-ring { 0%{transform:scale(1) translateZ(0);opacity:0.5} 100%{transform:scale(2.2) translateZ(0);opacity:0} }
@keyframes va-glow { 0%,100%{box-shadow:0 0 8px rgba(139,92,246,0.2)} 50%{box-shadow:0 0 20px rgba(139,92,246,0.5)} }
`;

interface Props {
  alert: VoiceAlertType | null;
  onDismiss: () => void;
}

/* ── Sound wave bars ── */
function SoundWaveBars() {
  return (
    <div className="flex items-center gap-0.5 h-3 ml-1">
      {[0, 0.15, 0.3, 0.12, 0.25].map((delay, i) => (
        <span
          key={i}
          className="w-0.5 rounded-full bg-primary"
          style={{ animation: `va-bar 0.6s ${delay}s ease-in-out infinite`, minHeight: 3 }}
        />
      ))}
    </div>
  );
}

/* ── Siri-like listening rings ── */
function ListeningRings() {
  return (
    <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
      {[0, 0.6, 1.2].map((delay, i) => (
        <span
          key={i}
          className="absolute w-6 h-6 rounded-full border border-red-400/40"
          style={{ animation: `va-ring 1.8s ${delay}s ease-out infinite` }}
        />
      ))}
    </span>
  );
}

/* ── Typewriter text ── */
function TypewriterMessage({ text }: { text: string }) {
  const [reveal, setReveal] = useState(text.length);
  const prevRef = useRef(text);

  useEffect(() => {
    if (prevRef.current === text) return;
    prevRef.current = text;
    setReveal(0);
    const len = text.length;
    const step = Math.max(1, Math.floor(len / 60));
    let i = 0;
    const id = setInterval(() => {
      i += step;
      if (i >= len) { setReveal(len); clearInterval(id); }
      else setReveal(i);
    }, 15);
    return () => clearInterval(id);
  }, [text]);

  return (
    <p className="text-sm text-muted-foreground mb-4">
      {text.slice(0, reveal)}
      {reveal < text.length && (
        <span className="inline-block w-0.5 h-3.5 bg-primary/50 align-middle ml-px animate-pulse" />
      )}
    </p>
  );
}

export function VoiceAlert({ alert, onDismiss }: Props) {
  const [responding, setResponding] = useState(false);
  const [sttStatus, setSttStatus] = useState<"idle" | "listening" | "processing">("idle");
  const [sttText, setSttText] = useState("");
  const [hasPlayed, setHasPlayed] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isHolding, setIsHolding] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const hasAutoPlayed = useRef<string | null>(null);
  const autoDismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestSttTextRef = useRef("");

  /* inject CSS */
  useEffect(() => {
    if (document.getElementById(cssId)) return;
    const s = document.createElement("style");
    s.id = cssId;
    s.textContent = css;
    document.head.appendChild(s);
  }, []);

  // --- STT for hold-to-speak ---
  const {
    isSupported: sttSupported,
    isListening,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    continuous: true,
    onResult: (text) => {
      // Update accumulated text (fired by silence timeout in continuous mode)
      latestSttTextRef.current = text;
      setSttText(text);
    },
    onInterim: (text) => {
      // Update text in real-time as user speaks
      latestSttTextRef.current = text;
      setSttText(text);
    },
    onError: () => {
      setSttStatus("idle");
      setIsHolding(false);
    },
  });

  // --- Auto-play audio when a new alert arrives ---
  useEffect(() => {
    if (!alert) {
      hasAutoPlayed.current = null;
      setSttStatus("idle");
      setSttText("");
      setHasPlayed(false);
      setErrorMessage(null);
      setIsPlaying(false);
      setIsHolding(false);
      latestSttTextRef.current = "";
      if (autoDismissTimer.current) {
        clearTimeout(autoDismissTimer.current);
        autoDismissTimer.current = null;
      }
      return;
    }

    if (alert.alert_id === hasAutoPlayed.current) return;
    hasAutoPlayed.current = alert.alert_id;

    if (alert.audio_base64 && audioRef.current) {
      audioRef.current.src = `data:audio/mpeg;base64,${alert.audio_base64}`;
      setIsPlaying(true);
      audioRef.current.play().catch(() => {
        setIsPlaying(false);
      });
      setHasPlayed(true);

      audioRef.current.onended = () => {
        setIsPlaying(false);
        // Info-only alerts: auto-dismiss after delay
        if (!alert.require_permission) {
          autoDismissTimer.current = setTimeout(() => {
            onDismiss();
          }, AUTO_DISMISS_DELAY);
        }
        // Permission-required alerts: wait for user to use hold-to-speak or buttons
        // (no automatic listening)
      };
    } else if (!alert.require_permission && !alert.audio_base64) {
      autoDismissTimer.current = setTimeout(() => {
        onDismiss();
      }, AUTO_DISMISS_DELAY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alert?.alert_id]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (isListening) stopListening();
      if (autoDismissTimer.current) clearTimeout(autoDismissTimer.current);
    };
  }, [isListening, stopListening]);

  if (!alert) return null;

  const replayAudio = () => {
    if (alert.audio_base64 && audioRef.current) {
      if (autoDismissTimer.current) {
        clearTimeout(autoDismissTimer.current);
        autoDismissTimer.current = null;
      }
      audioRef.current.src = `data:audio/mpeg;base64,${alert.audio_base64}`;
      setIsPlaying(true);
      audioRef.current.play();
      if (audioRef.current) {
        audioRef.current.onended = () => setIsPlaying(false);
      }
    }
  };

  const handleResponse = async (approved: boolean | null, userText: string = "") => {
    setResponding(true);
    if (isListening) stopListening();
    setSttStatus("processing");
    setErrorMessage(null);

    try {
      const response = await apiFetch("/voice/permission", {
        method: "POST",
        body: JSON.stringify({
          alert_id: alert.alert_id,
          approved: approved,
          user_text: userText,
          modifications: {},
        }),
      });

      // Check if there's an error message from clarity check
      if (response.error_message) {
        setErrorMessage(response.error_message);
        setSttStatus("idle");
        setSttText("");
        setResponding(false);
        return;
      }
    } catch (e) {
      console.error("Permission response failed:", e);
      setErrorMessage("Failed to process your response. Please try again.");
      setSttStatus("idle");
      setResponding(false);
      return;
    }
    setResponding(false);
    setSttStatus("idle");
    setSttText("");
    latestSttTextRef.current = "";
    onDismiss();
  };

  // --- Hold-to-speak handlers ---
  const handleHoldStart = (e: React.PointerEvent) => {
    e.preventDefault();
    if (responding) return;
    setIsHolding(true);
    setSttStatus("listening");
    setSttText("");
    latestSttTextRef.current = "";
    setErrorMessage(null);
    startListening();
  };

  const handleHoldEnd = () => {
    if (!isHolding) return;
    setIsHolding(false);
    if (isListening) stopListening();

    const text = latestSttTextRef.current.trim();
    if (text) {
      setSttStatus("processing");
      // Send with approved=null — the backend LLM determines intent
      // (approve all, deny all, or specific instructions like "turn up the heating only")
      handleResponse(null, text);
    } else {
      setSttStatus("idle");
    }
  };

  const needsPermGlow = alert.require_permission;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.8, y: 30 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
        transition={{ type: "spring", stiffness: 400, damping: 30 }}
        className="fixed right-4 left-4 sm:left-auto sm:right-6 z-50 sm:w-96 bg-card border border-border rounded-xl shadow-2xl overflow-hidden backdrop-blur-sm max-h-[85vh] overflow-y-auto"
        style={{
          bottom: "calc(1rem + env(safe-area-inset-bottom, 0px))",
          ...(needsPermGlow ? { animation: "va-glow 2s ease-in-out infinite" } : {}),
        }}
      >
        <div className="p-4">
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
              className="relative"
            >
              <Volume2 className="w-5 h-5 text-primary" />
            </motion.div>
            {isPlaying && <SoundWaveBars />}
            <span className="text-sm font-semibold">
              {alert.require_permission ? "Voice Alert" : "Smart Home"}
            </span>
            {isHolding && (
              <motion.span
                animate={{ opacity: [1, 0.4] }}
                transition={{ repeat: Infinity, duration: 0.8 }}
                className="ml-auto text-[10px] text-red-400 flex items-center gap-1 relative"
              >
                <span className="relative">
                  <Mic className="w-3 h-3 relative z-10" />
                  <ListeningRings />
                </span>
                Listening…
              </motion.span>
            )}
          </div>

          {/* Alert message — typewriter */}
          <TypewriterMessage text={alert.message} />

          {/* Replay button */}
          {alert.audio_base64 && hasPlayed && (
            <Button variant="outline" size="sm" className="mb-3 w-full" onClick={replayAudio}>
              <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Replay
            </Button>
          )}

          <audio ref={audioRef} />

          {/* Error message */}
          {errorMessage && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mb-3 px-3 py-2 rounded-lg bg-red-950/30 border border-red-500/30"
            >
              <p className="text-xs text-red-300">{errorMessage}</p>
            </motion.div>
          )}

          {/* Live STT transcript while holding the mic button */}
          {isHolding && sttText && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mb-3 px-3 py-2 rounded-lg bg-zinc-800/60 border border-zinc-700"
            >
              <p className="text-xs text-zinc-300 italic">
                "{sttText}"
                <motion.span
                  animate={{ opacity: [1, 0] }}
                  transition={{ repeat: Infinity, duration: 0.8 }}
                >
                  |
                </motion.span>
              </p>
            </motion.div>
          )}

          {/* Processing indicator */}
          {sttStatus === "processing" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-3 px-3 py-2 rounded-lg bg-zinc-800/60 border border-zinc-700"
            >
              <p className="text-xs text-zinc-400 flex items-center gap-2">
                <motion.span
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                  className="inline-block w-3 h-3 border border-zinc-500 border-t-transparent rounded-full"
                />
                Processing your response…
              </p>
              {sttText && (
                <p className="text-xs text-zinc-300 italic mt-1">"{sttText}"</p>
              )}
            </motion.div>
          )}

          {/* Permission buttons */}
          {alert.require_permission ? (
            <div className="space-y-2">
              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  size="sm"
                  onClick={() => handleResponse(true)}
                  disabled={responding}
                >
                  <Check className="w-3.5 h-3.5 mr-1" /> Approve
                </Button>
                <Button
                  variant="destructive"
                  className="flex-1"
                  size="sm"
                  onClick={() => handleResponse(false)}
                  disabled={responding}
                >
                  <X className="w-3.5 h-3.5 mr-1" /> Deny
                </Button>
              </div>

              {sttSupported && (
                <Button
                  variant="outline"
                  size="sm"
                  className={`w-full text-xs select-none touch-none ${
                    isHolding
                      ? "border-red-500/50 text-red-400 bg-red-950/20"
                      : ""
                  }`}
                  onPointerDown={handleHoldStart}
                  onPointerUp={handleHoldEnd}
                  onPointerLeave={handleHoldEnd}
                  onPointerCancel={handleHoldEnd}
                  onContextMenu={(e) => e.preventDefault()}
                  disabled={responding}
                >
                  <Mic className="w-3.5 h-3.5 mr-1.5" />
                  {isHolding ? "Release to Send" : "Hold to Speak"}
                </Button>
              )}
            </div>
          ) : (
            <Button variant="secondary" size="sm" className="w-full" onClick={onDismiss}>
              Dismiss
            </Button>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
