/**
 * Noise blob behind Lumos title. Scroll within the hero zone (700vh)
 * advances steps 1→7; then scroll continues to lamp.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { createNoise3D } from "simplex-noise";
import { animate } from "animejs";

const TWO_PI = Math.PI * 2;
const LANDING_BG = "#252123";
const LANDING_FG = "#fafafa";
const BLOB_SCALE = 0.4;
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
  const [step, setStep] = useState(1);
  const animRef = useRef({ t: 0 });
  const framesRef = useRef(0);
  const noiseRef = useRef(createNoise3D(() => Math.random()));
  const rafRef = useRef<number>(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx || !canvas) return;

    // Use CSS size (already DPR‑scaled in resize)
    const rect = canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    const r = Math.min(w, h) * BLOB_SCALE;
    const cx = w / 2;
    const cy = h / 2;
    const noise = noiseRef.current;
    const anim = animRef.current;
    const frames = framesRef.current;

    const cos = Math.cos;
    const sin = Math.sin;

    ctx.fillStyle = LANDING_BG;
    ctx.fillRect(0, 0, w, h);

    if (step === 1) {
      ctx.fillStyle = LANDING_FG;
      for (let i = 0; i < 100; i++) {
        const x = cos((i / 100) * TWO_PI) * r + cx;
        const y = sin((i / 100) * TWO_PI) * r + cy;
        ctx.beginPath();
        ctx.arc(x, y, DOT_RADIUS, 0, TWO_PI);
        ctx.fill();
      }
      return;
    }

    if (step === 2) {
      ctx.fillStyle = LANDING_FG;
      for (let i = 0; i < 100; i++) {
        let x = cos((i / 100) * TWO_PI);
        let y = sin((i / 100) * TWO_PI);
        const offset = noise(x, y, 0) * (r / 5) * anim.t;
        x = x * (r + offset) + cx;
        y = y * (r + offset) + cy;
        ctx.beginPath();
        ctx.arc(x, y, DOT_RADIUS, 0, TWO_PI);
        ctx.fill();
      }
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 3) {
      ctx.strokeStyle = LANDING_FG;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i <= 100; i++) {
        let x = cos((i / 100) * TWO_PI);
        let y = sin((i / 100) * TWO_PI);
        const offset = noise(x, y, 0) * (r / 5);
        x = x * (r + offset) + cx;
        y = y * (r + offset) + cy;
        if (anim.t >= i / 100) {
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.fillStyle = LANDING_FG;
        ctx.beginPath();
        ctx.arc(x, y, DOT_RADIUS * (1 - anim.t), 0, TWO_PI);
        ctx.fill();
      }
      ctx.stroke();
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 4) {
      const rings = 70;
      ctx.strokeStyle = LANDING_FG;
      ctx.lineWidth = 1;
      ctx.fillStyle = LANDING_BG;
      for (let j = 0; j <= rings * anim.t; j++) {
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
        ctx.stroke();
      }
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 5) {
      const rings = 70;
      ctx.lineWidth = 1;
      ctx.fillStyle = LANDING_BG;
      for (let j = 0; j < rings; j++) {
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
        ctx.strokeStyle = `rgb(${(j / rings) * 175 + 80}, ${(j / rings) * 175 + 80}, ${(j / rings) * 175 + 80})`;
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
          const offset = noise(x, y + j * 0.03, frames * 0.003) * (rad / 5);
          x = x * (rad + offset) + cx;
          y = y * (rad + offset) + cy;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = `rgb(${(j / rings) * 175 + 80}, ${(j / rings) * 175 + 80}, ${(j / rings) * 175 + 80})`;
        ctx.stroke();
      }
      framesRef.current = frames + 1;
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    if (step === 7) {
      const rings = 40;
      for (let j = 0; j < rings; j++) {
        const rad = (r / rings) * (rings - j);
        ctx.beginPath();
        for (let i = 0; i <= 150; i++) {
          let x = cos((i / 100) * TWO_PI);
          let y = sin((i / 100) * TWO_PI);
          const offset = noise(x, y + j * 0.03, frames * 0.003) * (rad / 3);
          x = x * (rad + offset) + cx;
          y = y * (rad + offset) + cy;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.fillStyle = `hsl(${(j / rings) * 360}, 70%, 70%)`;
        ctx.strokeStyle = `hsl(${(j / rings) * 360}, 70%, 80%)`;
        ctx.fill();
        ctx.stroke();
      }
      framesRef.current = frames + 1;
      rafRef.current = requestAnimationFrame(draw);
    }
  }, [step]);

  // Resize canvas to match wrapper and handle DPR correctly
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
        // Reset transform before scaling so it doesn't stack
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
      }

      draw();
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

  // Drive step 1→7 from scroll position
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateStepFromScroll = () => {
      const scrollTop = container.scrollTop;
      const heroHeightPx = (heroScrollHeightVh / 100) * window.innerHeight;
      const progress = Math.max(0, Math.min(1, scrollTop / heroHeightPx));
      const newStep = progress >= 1 ? 7 : 1 + Math.floor(progress * 7);
      setStep((prev) => (newStep >= 1 && newStep <= 7 ? newStep : prev));
    };

    updateStepFromScroll();
    container.addEventListener("scroll", updateStepFromScroll, { passive: true });
    return () => container.removeEventListener("scroll", updateStepFromScroll);
  }, [containerRef, heroScrollHeightVh]);

  // Animate steps 2–5 and init frames for 6–7
  useEffect(() => {
    if (step >= 2 && step <= 5) {
      animRef.current.t = 0;
      const anim = animate(animRef.current, {
        t: 1,
        duration: 3000,
        ease: "outQuad",
      });
      return () => {
        anim.cancel();
      };
    }
    if (step === 6 || step === 7) {
      framesRef.current = 0;
    }
  }, [step]);

  // Start draw loop for steps 2–7
  useEffect(() => {
    if (step >= 2) {
      draw();
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
