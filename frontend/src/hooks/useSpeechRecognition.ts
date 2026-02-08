/**
 * Hook wrapping the Web Speech API for push-to-talk speech recognition.
 *
 * Works in Chrome, Edge, Safari (with webkit prefix).
 * Falls back gracefully if the browser doesn't support it.
 */
import { useState, useRef, useCallback, useEffect } from "react";

interface UseSpeechRecognitionOptions {
  /** Language for recognition (default: "en-US") */
  lang?: string;
  /** Called with partial (interim) transcript while the user is speaking */
  onInterim?: (text: string) => void;
  /** Called with the final transcript when the user stops speaking */
  onResult?: (text: string) => void;
  /** Called on any recognition error */
  onError?: (error: string) => void;
  /** Continuous mode — keeps listening until explicitly stopped (default false) */
  continuous?: boolean;
}

interface UseSpeechRecognitionReturn {
  /** Whether the browser supports the Web Speech API */
  isSupported: boolean;
  /** Whether the microphone is actively listening */
  isListening: boolean;
  /** The current transcript (interim + final) */
  transcript: string;
  /** Start listening */
  startListening: () => void;
  /** Stop listening */
  stopListening: () => void;
  /** Clear the transcript */
  clearTranscript: () => void;
}

// Get the SpeechRecognition constructor (vendor-prefixed in some browsers)
const SpeechRecognitionAPI =
  typeof window !== "undefined"
    ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    : null;

export function useSpeechRecognition(
  options: UseSpeechRecognitionOptions = {}
): UseSpeechRecognitionReturn {
  const {
    lang = "en-US",
    onInterim,
    onResult,
    onError,
    continuous = false,
  } = options;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<any>(null);
  const finalTranscriptRef = useRef("");
  const silenceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldStopRef = useRef(false); // Flag to prevent auto-restart after timeout

  // Store latest callbacks in refs so recognition event handlers see them
  const onResultRef = useRef(onResult);
  const onInterimRef = useRef(onInterim);
  const onErrorRef = useRef(onError);
  useEffect(() => { onResultRef.current = onResult; }, [onResult]);
  useEffect(() => { onInterimRef.current = onInterim; }, [onInterim]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  const isSupported = !!SpeechRecognitionAPI;

  const startListening = useCallback(() => {
    if (!SpeechRecognitionAPI) {
      onErrorRef.current?.("Speech recognition is not supported in this browser");
      return;
    }

    // Reset stop flag when starting fresh
    shouldStopRef.current = false;
    
    // Create a fresh instance each time
    const recognition = new SpeechRecognitionAPI();
    recognition.lang = lang;
    recognition.continuous = continuous;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      finalTranscriptRef.current = "";
      setTranscript("");
      shouldStopRef.current = false; // Reset flag on start
      // Clear any existing timeout when starting fresh
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }
    };

    recognition.onresult = (event: any) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }

      if (final) {
        finalTranscriptRef.current += final;
      }

      const fullText = finalTranscriptRef.current + interim;
      setTranscript(fullText);

      if (interim) {
        onInterimRef.current?.(fullText);
      }
      
      // Reset silence timeout on ANY transcription activity (interim or final)
      // This detects when the user has stopped speaking
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
      }

      // For continuous mode: wait for silence timeout before processing
      // For non-continuous mode: process immediately on final results
      if (final && !continuous) {
        // Non-continuous mode: process immediately
        onResultRef.current?.(finalTranscriptRef.current.trim());
      } else if (continuous) {
        // Continuous mode: set timeout to stop listening after 2.5 seconds of no new transcription
        // This triggers when user stops speaking (no new results for 2.5 seconds)
        silenceTimeoutRef.current = setTimeout(() => {
          const finalText = finalTranscriptRef.current.trim();
          if (recognitionRef.current && !shouldStopRef.current) {
            // Set flag to prevent auto-restart
            shouldStopRef.current = true;
            // Abort (more forceful than stop) to prevent auto-restart in continuous mode
            try {
              recognitionRef.current.abort();
            } catch (e) {
              // If abort fails, try stop
              try {
                recognitionRef.current.stop();
              } catch (e2) {
                // Ignore errors if already stopped
              }
            }
            // Clear the ref to prevent any further operations
            recognitionRef.current = null;
            setIsListening(false);
            // Trigger the result callback with the final text (only if we have text)
            if (finalText) {
              onResultRef.current?.(finalText);
            }
          }
        }, 3000); // 3 seconds of silence (no new transcription results)
      }
    };

    recognition.onerror = (event: any) => {
      // Clear timeout on error
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }
      
      // "no-speech" and "aborted" are expected when user releases quickly
      if (event.error === "no-speech" || event.error === "aborted") {
        setIsListening(false);
        return;
      }
      console.error("Speech recognition error:", event.error);
      onErrorRef.current?.(event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      // Clear timeout on end
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }
      
      // If we intentionally stopped (via timeout or manual stop), don't restart
      if (shouldStopRef.current) {
        recognitionRef.current = null;
        return;
      }
      
      // In continuous mode, the Web Speech API will automatically restart
      // We don't need to manually restart it - it handles that itself
      // But we prevent restart if shouldStopRef is true (handled above)
      
      // In non-continuous mode, fire onResult with whatever we got
      if (!continuous && finalTranscriptRef.current.trim()) {
        onResultRef.current?.(finalTranscriptRef.current.trim());
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [lang, continuous]);

  const stopListening = useCallback(() => {
    shouldStopRef.current = true; // Set flag to prevent restart
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
      silenceTimeoutRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort(); // Use abort to prevent auto-restart
      } catch (e) {
        // If abort fails, try stop
        try {
          recognitionRef.current.stop();
        } catch (e2) {
          // Ignore errors if already stopped
        }
      }
      recognitionRef.current = null;
      setIsListening(false);
    }
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscript("");
    finalTranscriptRef.current = "";
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      shouldStopRef.current = true;
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {
          // Ignore errors
        }
      }
    };
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    startListening,
    stopListening,
    clearTranscript,
  };
}
