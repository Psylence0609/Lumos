/**
 * Hold-to-talk microphone button with visual feedback.
 *
 * Press and hold → starts recording (browser STT).
 * Release → sends transcribed text to the command handler.
 * Pulsing ring + live transcript while listening.
 */
import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

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

export function VoiceChatButton({
  onTranscript,
  disabled = false,
  compact = false,
  className,
}: Props) {
  const [interimText, setInterimText] = useState("");
  const [sent, setSent] = useState(false);
  const sentRef = useRef(false);

  const handleResult = useCallback(
    (text: string) => {
      if (sentRef.current) return; // Avoid double-fire
      sentRef.current = true;
      setSent(true);
      onTranscript(text);
      // Reset after a short delay
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
    onInterim: setInterimText,
    onResult: handleResult,
    onError: (err) => {
      console.warn("STT error:", err);
      setInterimText("");
    },
  });

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
    sentRef.current = false;
    setSent(false);
    setInterimText("");
    startListening();
  };

  const handlePointerUp = () => {
    if (isListening) {
      stopListening();
    }
  };

  const displayText = transcript || interimText;

  return (
    <div className="relative">
      {/* The button */}
      <motion.button
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
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
        title="Hold to talk"
      >
        {/* Pulsing ring while listening */}
        <AnimatePresence>
          {isListening && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: [0.4, 0.1, 0.4], scale: [1, 1.6, 1] }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
              className="absolute inset-0 rounded-md border-2 border-red-500/40"
            />
          )}
        </AnimatePresence>

        {disabled ? (
          <Loader2 className={cn("animate-spin", compact ? "w-4 h-4" : "w-5 h-5")} />
        ) : (
          <Mic className={cn(compact ? "w-4 h-4" : "w-5 h-5")} />
        )}
      </motion.button>

      {/* Live transcript bubble */}
      <AnimatePresence>
        {isListening && displayText && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.95 }}
            className="absolute bottom-full mb-2 right-0 max-w-xs w-max px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 shadow-lg"
          >
            <p className="text-xs text-zinc-300 italic">
              {displayText}
              <motion.span
                animate={{ opacity: [1, 0] }}
                transition={{ repeat: Infinity, duration: 0.8 }}
              >
                |
              </motion.span>
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
