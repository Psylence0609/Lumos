/**
 * Noise blob behind Lumos title. Two scroll triggers advance through:
 * 2 → (scroll) → 3 → auto 4 → (scroll) → 6
 * Optimized for 60fps with smooth transitions
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { createNoise3D } from "simplex-noise";
import { animate } from "animejs";

const TWO_PI = Math.PI * 2;
const LANDING_BG = "#252123";
const LANDING_FG = "#fafafa";
const BLOB_SCALE = 0.35;
const DOT_RADIUS = 3;

interface NoiseBlobSectionProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  heroScrollRef: React.RefObject<HTMLDivElement | null>;
  heroScrollHeightVh: number;
}

export function NoiseBlobSection({
  containerRef,
  heroScrollRef,
  heroScrollHeightVh,
}: NoiseBlobSectionProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const canvasWrapRef = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(2);
  const [scrollStep, setScrollStep] = useState(2);
  const animRef = useRef({ t: 0 });
  const timeRef = useRef(0);
  const lastFrameTimeRef = useRef(0);
  const noiseRef = useRef(createNoise3D(() => Math.random()));
  const rafRef = useRef<number>(0);
  const transitionRef = useRef({ progress: 0 }); // For smooth transitions

  const draw = useCallback((timestamp: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx || !canvas) return;

    if (!lastFrameTimeRef.current) lastFrameTimeRef.current = timestamp;
    const deltaTime = timestamp - lastFrameTimeRef.current;
    lastFrameTimeRef.current = timestamp;

    timeRef.current += deltaTime * 0.001;

    const rect = canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    const r = Math.min(w, h) * BLOB_SCALE;
    const cx = w / 2;
    const cy = h / 2;
    const noise = noiseRef.current;
    const anim = animRef.current;
    const time = timeRef.current;
    const transition = transitionRef.current.progress;

    const cos = Math.cos;
    const sin = Math.sin;

    ctx.fillStyle = LANDING_BG;
    ctx.fillRect(0, 0, w, h);

    if (step === 2) {
      ctx.fillStyle = LANDING_FG;
      ctx.beginPath();
      for (let i = 0; i < 100; i++) {
        let x = cos((i / 100) * TWO_PI);
        let y = sin((i / 100) * TWO_PI);
        const offset = noise(x, y, 0) * (r / 5) * anim.t;
        x = x * (r + offset) + cx;
        y = y * (r + offset) + cy;
        ctx.moveTo(x + DOT_RADIUS, y);
        ctx.arc(x, y, DOT_RADIUS, 0, TWO_PI);
      }
      ctx.fill();
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 3) {
      ctx.strokeStyle = LANDING_FG;
      ctx.lineWidth = 1.5;
      ctx.beginPath();

      const points = [];
      for (let i = 0; i <= 100; i++) {
        let x = cos((i / 100) * TWO_PI);
        let y = sin((i / 100) * TWO_PI);
        const offset = noise(x, y, 0) * (r / 5);
        x = x * (r + offset) + cx;
        y = y * (r + offset) + cy;
        points.push({ x, y, progress: i / 100 });
      }

      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        if (anim.t >= p.progress) {
          if (i === 0) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        }
      }
      ctx.stroke();

      ctx.fillStyle = LANDING_FG;
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        const dotSize = DOT_RADIUS * (1 - anim.t);
        if (dotSize > 0.1) {
          ctx.moveTo(p.x + dotSize, p.y);
          ctx.arc(p.x, p.y, dotSize, 0, TWO_PI);
        }
      }
      ctx.fill();

      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 4) {
      const rings = 70;
      ctx.lineWidth = 1;
      ctx.fillStyle = LANDING_BG;

      // Blend between single outline and full rings based on transition
      const maxRings = Math.floor(rings * anim.t);
      
      for (let j = 0; j <= maxRings; j++) {
        const rad = (r / rings) * (rings - j);
        ctx.beginPath();
        for (let i = 0; i <= 100; i++) {
          let x = cos((i / 100) * TWO_PI);
          let y = sin((i / 100) * TWO_PI);
          const offset = noise(x, y + j * 0.03, 0) * (rad / 5);
          x = x * (rad + offset) + cx;
          y = y * (rad + offset) + cy;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        
        // Smooth transition to grayscale
        const gray = Math.floor((j / rings) * 175 + 80);
        const alpha = Math.min(1, transition * 3); // Fade in grayscale
        ctx.strokeStyle = `rgba(${gray}, ${gray}, ${gray}, ${alpha})`;
        if (transition < 0.3) {
          ctx.strokeStyle = LANDING_FG; // Keep white initially
        }
        ctx.stroke();
      }
      
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 6) {
      const rings = 70;
      ctx.lineWidth = 1;
      ctx.fillStyle = LANDING_BG;

      for (let j = 0; j < rings; j++) {
        const rad = (r / rings) * (rings - j);
        ctx.beginPath();
        for (let i = 0; i <= 100; i++) {
          let x = cos((i / 100) * TWO_PI);
          let y = sin((i / 100) * TWO_PI);
          const offset = noise(x, y + j * 0.03, time * 0.5) * (rad / 5);
          x = x * (rad + offset) + cx;
          y = y * (rad + offset) + cy;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = `rgb(${(j / rings) * 175 + 80}, ${(j / rings) * 175 + 80}, ${(j / rings) * 175 + 80})`;
        ctx.stroke();
      }
      
      rafRef.current = requestAnimationFrame(draw);
      return;
    }
  }, [step]);

  // Resize canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = canvasWrapRef.current;
    if (!canvas || !wrap) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      if (w <= 0 || h <= 0) return;

      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
      }

      lastFrameTimeRef.current = 0;
      rafRef.current = requestAnimationFrame(draw);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    window.addEventListener("resize", resize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [draw, step]);

  // Scroll handler with smooth transitions
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let scrollTimeout: number;
    const updateStepFromScroll = () => {
      if (scrollTimeout) cancelAnimationFrame(scrollTimeout);

      scrollTimeout = requestAnimationFrame(() => {
        const scrollTop = container.scrollTop;
        const heroHeightPx = (heroScrollHeightVh / 100) * window.innerHeight;
        const progress = Math.max(0, Math.min(1, scrollTop / heroHeightPx));

        let newScrollStep = 2;
        if (progress < 0.25) {
          newScrollStep = 2;
        } else if (progress < 0.6) {
          newScrollStep = 3;
        } else {
          newScrollStep = 6;
        }

        if (newScrollStep !== scrollStep) {
          setScrollStep(newScrollStep);
          setStep(newScrollStep);
          
          // Reset transition progress when changing steps
          transitionRef.current.progress = 0;
        }
      });
    };

    updateStepFromScroll();
    container.addEventListener("scroll", updateStepFromScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", updateStepFromScroll);
      if (scrollTimeout) cancelAnimationFrame(scrollTimeout);
    };
  }, [containerRef, heroScrollHeightVh, scrollStep]);

  // Animate steps with smooth transitions
  useEffect(() => {
    if (step === 2 || step === 3 || step === 4) {
      animRef.current.t = 0;
      timeRef.current = 0;
      lastFrameTimeRef.current = 0;
      transitionRef.current.progress = 0;

      const anim = animate(animRef.current, {
        t: 1,
        duration: 3000,
        easing: "easeOutQuad",
        complete: () => {
          if (step === 3) {
            // Smooth transition from 3 to 4
            animate(transitionRef.current, {
              progress: 1,
              duration: 1500,
              easing: "easeInOutQuad",
              complete: () => {
                setStep(4);
              },
            });
          }
        },
      });

      // Animate transition progress for step 4
      if (step === 4) {
        animate(transitionRef.current, {
          progress: 1,
          duration: 2000,
          easing: "easeInOutQuad",
        });
      }

      return () => {
        anim.pause();
      };
    }

    if (step === 6) {
      timeRef.current = 0;
      lastFrameTimeRef.current = 0;
      transitionRef.current.progress = 0;
      
      // Smooth fade-in for step 6
      animate(transitionRef.current, {
        progress: 1,
        duration: 1500,
        easing: "easeInOutQuad",
      });
    }
  }, [step]);

  // Start draw loop
  useEffect(() => {
    if (step >= 2) {
      lastFrameTimeRef.current = 0;
      rafRef.current = requestAnimationFrame(draw);
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [step, draw]);

  return (
    <div
      className="pointer-events-none"
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 0,
        overflow: "visible",
        willChange: "transform",
      }}
    >
      <div ref={canvasWrapRef}>
        <canvas
          ref={canvasRef}
          className="noise-blob-canvas block"
          style={{
            width: "110vmin",
            height: "110vmin",
            maxWidth: "min(110vmin, 140vw)",
            maxHeight: "min(110vmin, 140vh)",
            background: LANDING_BG,
          }}
        />
      </div>
    </div>
  );
}
