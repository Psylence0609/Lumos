/**
 * Voice Alert overlay — shows when the system has a message for the user.
 *
 * Audio rules:
 * - Audio ALWAYS auto-plays when an alert arrives (threats, voice responses, etc.)
 * - A "Replay" button appears after the first play (never a "Play" button).
 * - For permission-required alerts: STT auto-activates after audio finishes
 *   to listen for "yes" / "approve" / "no" / "deny".
 * - Falls back to Approve / Deny buttons if STT fails or is unsupported.
 * - Info-only alerts auto-dismiss after audio finishes (with a Dismiss button as fallback).
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Volume2, Check, X, Mic, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/utils";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import type { VoiceAlert as VoiceAlertType } from "@/types";

const APPROVE_WORDS = ["yes", "yeah", "yep", "approve", "approved", "go ahead", "do it", "sure", "okay", "ok"];
const DENY_WORDS = ["no", "nah", "nope", "deny", "denied", "don't", "stop", "cancel"];

/** How long (ms) to keep an info-only alert visible after audio finishes */
const AUTO_DISMISS_DELAY = 4000;

interface Props {
  alert: VoiceAlertType | null;
  onDismiss: () => void;
}

export function VoiceAlert({ alert, onDismiss }: Props) {
  const [responding, setResponding] = useState(false);
  const [sttStatus, setSttStatus] = useState<"idle" | "listening" | "processing">("idle");
  const [sttText, setSttText] = useState("");
  const [hasPlayed, setHasPlayed] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const hasAutoPlayed = useRef<string | null>(null);
  const autoDismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- STT for permission responses ---
  // The speech recognition hook handles the 3 second silence timeout
  // After timeout, we process whatever text was transcribed (no need to check for action words)
  const handleSttResult = useCallback(
    (text: string) => {
      if (!alert?.require_permission || responding) return;

      // Clear any previous error when user starts speaking again
      if (errorMessage) {
        setErrorMessage(null);
      }

      const trimmedText = text.trim();
      
      // If we have any transcribed text after the silence timeout, process it immediately
      if (trimmedText) {
        setSttText(trimmedText);
        setSttStatus("processing");
        
        // Stop listening since we have text and silence timeout occurred
        if (isListening) stopListening();
        
        // Check for explicit approve/deny words, but if none found, pass null
        // Backend will parse the instructions (e.g., "turn up the heating only")
        const lower = trimmedText.toLowerCase();
        const isApprove = APPROVE_WORDS.some((w) => lower.includes(w));
        const isDeny = DENY_WORDS.some((w) => lower.includes(w));
        
        // Pass null if no explicit approve/deny - backend will infer from instructions
        const approved = isApprove ? true : isDeny ? false : null;
        handleResponse(approved, trimmedText);
      } else {
        // No text transcribed - keep listening
        setSttStatus("listening");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [alert, responding, errorMessage, isListening, stopListening]
  );

  const {
    isSupported: sttSupported,
    isListening,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    continuous: true,
    onResult: handleSttResult,
    onInterim: (text) => setSttText(text), // Just update the display, don't process yet
    onError: () => setSttStatus("idle"),
  });

  // --- Auto-play audio when a new alert arrives ---
  useEffect(() => {
    if (!alert) {
      hasAutoPlayed.current = null;
      setSttStatus("idle");
      setSttText("");
      setHasPlayed(false);
      setErrorMessage(null);
      if (autoDismissTimer.current) {
        clearTimeout(autoDismissTimer.current);
        autoDismissTimer.current = null;
      }
      return;
    }

    // Only auto-play once per alert
    if (alert.alert_id === hasAutoPlayed.current) return;
    hasAutoPlayed.current = alert.alert_id;

    if (alert.audio_base64 && audioRef.current) {
      audioRef.current.src = `data:audio/mpeg;base64,${alert.audio_base64}`;
      audioRef.current.play().catch(() => {
        // Browser may block autoplay — user can click Replay
      });
      setHasPlayed(true);

      audioRef.current.onended = () => {
        if (alert.require_permission && sttSupported) {
          // Permission alert: start listening for yes/no
          setSttStatus("listening");
          startListening();
        } else if (!alert.require_permission) {
          // Info-only alert: auto-dismiss after a delay
          autoDismissTimer.current = setTimeout(() => {
            onDismiss();
          }, AUTO_DISMISS_DELAY);
        }
      };
    } else if (alert.require_permission && sttSupported) {
      // No audio but permission needed — start STT immediately
      setSttStatus("listening");
      startListening();
    } else if (!alert.require_permission && !alert.audio_base64) {
      // No audio, no permission — auto-dismiss after short delay
      autoDismissTimer.current = setTimeout(() => {
        onDismiss();
      }, AUTO_DISMISS_DELAY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alert?.alert_id]);

  // Cleanup STT on dismiss
  useEffect(() => {
    return () => {
      if (isListening) stopListening();
      if (autoDismissTimer.current) clearTimeout(autoDismissTimer.current);
    };
  }, [isListening, stopListening]);

  if (!alert) return null;

  const replayAudio = () => {
    if (alert.audio_base64 && audioRef.current) {
      // Cancel any pending auto-dismiss
      if (autoDismissTimer.current) {
        clearTimeout(autoDismissTimer.current);
        autoDismissTimer.current = null;
      }
      audioRef.current.src = `data:audio/mpeg;base64,${alert.audio_base64}`;
      audioRef.current.play();
    }
  };

  const handleResponse = async (approved: boolean | null, userText: string = "") => {
    setResponding(true);
    if (isListening) stopListening();
    setSttStatus("processing");
    setErrorMessage(null); // Clear any previous error

    try {
      const response = await apiFetch("/voice/permission", {
        method: "POST",
        body: JSON.stringify({
          alert_id: alert.alert_id,
          approved: approved, // Can be null if inferred from userText
          user_text: userText || sttText, // Send the natural language response
          modifications: {},
        }),
      });
      
      // Check if there's an error message from clarity check
      if (response.error_message) {
        setErrorMessage(response.error_message);
        setSttStatus("idle");
        setSttText("");
        // Don't dismiss - let user see the error and try again
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
    onDismiss();
  };

  const toggleStt = () => {
    if (isListening) {
      stopListening();
      setSttStatus("idle");
    } else {
      setSttStatus("listening");
      startListening();
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="fixed bottom-6 right-6 z-50 w-96 bg-card border border-border rounded-xl shadow-2xl overflow-hidden"
      >
        <div className="p-4">
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              <Volume2 className="w-5 h-5 text-primary" />
            </motion.div>
            <span className="text-sm font-semibold">
              {alert.require_permission ? "Voice Alert" : "Smart Home"}
            </span>
            {sttStatus === "listening" && (
              <motion.span
                animate={{ opacity: [1, 0.4] }}
                transition={{ repeat: Infinity, duration: 0.8 }}
                className="ml-auto text-[10px] text-red-400 flex items-center gap-1"
              >
                <Mic className="w-3 h-3" /> Listening…
              </motion.span>
            )}
          </div>

          {/* Alert message */}
          <p className="text-sm text-muted-foreground mb-4">{alert.message}</p>

          {/* Error message from clarity check */}
          {errorMessage && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-3 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30"
            >
              <p className="text-xs text-red-400">{errorMessage}</p>
            </motion.div>
          )}

          {/* Replay button — only shown when audio exists and has been played */}
          {alert.audio_base64 && hasPlayed && (
            <Button variant="outline" size="sm" className="mb-3 w-full" onClick={replayAudio}>
              <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Replay
            </Button>
          )}

          <audio ref={audioRef} />

          {/* Live STT transcript */}
          {sttStatus === "listening" && sttText && (
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
              <p className="text-[10px] text-zinc-500 mt-1">
                Say <strong>"yes"</strong> to approve or <strong>"no"</strong> to deny
              </p>
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

              {/* STT toggle — in case auto-listen didn't start or user wants to retry */}
              {sttSupported && (
                <Button
                  variant="outline"
                  size="sm"
                  className={`w-full text-xs ${isListening ? "border-red-500/50 text-red-400" : ""}`}
                  onClick={toggleStt}
                  disabled={responding}
                >
                  <Mic className="w-3.5 h-3.5 mr-1.5" />
                  {isListening ? "Stop Listening" : "Respond by Voice"}
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
