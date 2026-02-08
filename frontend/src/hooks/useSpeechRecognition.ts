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
      // For hold-to-talk (continuous: false), only send result on release (in onend), not on every final chunk
      if (continuous && final) {
        onResultRef.current?.(finalTranscriptRef.current.trim());
      }
    };

    recognition.onerror = (event: any) => {
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
      // Hold-to-talk: send accumulated transcript only when user releases (stop() was called)
      if (!continuous) {
        const text = finalTranscriptRef.current.trim();
        if (text) {
          onResultRef.current?.(text);
        }
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [lang, continuous]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscript("");
    finalTranscriptRef.current = "";
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
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
