import { useEffect, useRef, useState } from "react";
import { animate, onScroll } from "animejs";

interface BulbSectionProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export function BulbSection({ containerRef }: BulbSectionProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const lampRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const [hasEntered, setHasEntered] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    const target = sectionRef.current;
    const lamp = lampRef.current;
    const glow = glowRef.current;
    if (!container || !target || !lamp) return;

    // Bouncy jump in: start below viewport, overshoot up then settle
    const entrance = animate(lamp, {
      y: ["120%", "-6%", "0%"],
      duration: 1000,
      ease: "outBack",
      autoplay: false,
    });

    const observer = onScroll({
      container,
      target,
      axis: "y",
      enter: 0.2,
      onEnter: () => {
        setHasEntered(true);
        entrance.play();
      },
    });

    return () => {
      observer.revert();
      entrance.cancel();
    };
  }, [containerRef]);

  // Light-up glow after lamp has landed
  useEffect(() => {
    if (!hasEntered || !glowRef.current) return;
    const glow = glowRef.current;
    const anim = animate(glow, {
      opacity: [0, 0.9],
      duration: 800,
      delay: 400,
      ease: "outQuad",
    });
    return () => {
      anim.cancel();
    };
  }, [hasEntered]);

  return (
    <section
      ref={sectionRef}
      className="min-h-screen flex items-center justify-center bg-background px-4"
    >
      <div
        ref={lampRef}
        className="relative flex justify-center items-end"
        style={{ transform: "translateY(120%)" }}
      >
        {/* Glow pool under lamp (lights up after bounce) */}
        <div
          ref={glowRef}
          className="absolute bottom-0 left-1/2 -translate-x-1/2 w-48 h-16 rounded-full opacity-0"
          style={{
            background: "radial-gradient(ellipse 80% 50% at 50% 100%, rgba(250,204,21,0.4) 0%, transparent 70%)",
            filter: "blur(8px)",
          }}
        />
        <DeskLampSvg />
      </div>
    </section>
  );
}

function DeskLampSvg() {
  return (
    <svg
      width="200"
      height="220"
      viewBox="0 0 200 220"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="drop-shadow-lg"
    >
      <defs>
        <linearGradient id="lamp-shade" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3f3f46" />
          <stop offset="50%" stopColor="#27272a" />
          <stop offset="100%" stopColor="#18181b" />
        </linearGradient>
        <linearGradient id="lamp-base" x1="0%" y1="100%" x2="0%" y2="0%">
          <stop offset="0%" stopColor="#18181b" />
          <stop offset="100%" stopColor="#3f3f46" />
        </linearGradient>
        <filter id="lamp-bulb-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
          <feFlood floodColor="rgba(250, 204, 21, 0.6)" floodOpacity="1" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="lamp-glow-ambient" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="12" result="blur" />
          <feFlood floodColor="rgba(250, 204, 21, 0.25)" floodOpacity="1" result="c" />
          <feComposite in="c" in2="blur" operator="in" result="ambient" />
          <feMerge>
            <feMergeNode in="ambient" />
          </feMerge>
        </filter>
      </defs>

      {/* Base */}
      <ellipse cx="100" cy="208" rx="55" ry="10" fill="url(#lamp-base)" stroke="#52525b" strokeWidth="1" />

      {/* Arm: vertical then horizontal */}
      <path
        d="M 100 208 L 100 95 Q 100 75 115 65 L 100 50"
        stroke="#52525b"
        strokeWidth="14"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M 100 208 L 100 95 Q 100 75 115 65 L 100 50"
        stroke="url(#lamp-base)"
        strokeWidth="12"
        strokeLinecap="round"
        fill="none"
      />

      {/* Shade (trapezoid / cone style) */}
      <path
        d="M 55 50 L 145 50 L 125 95 L 75 95 Z"
        fill="url(#lamp-shade)"
        stroke="#52525b"
        strokeWidth="1"
      />

      {/* Bulb inside shade - glowing */}
      <g filter="url(#lamp-bulb-glow)">
        <ellipse cx="100" cy="72" rx="22" ry="18" fill="#fef9c3" stroke="#fde047" strokeWidth="1" />
        <path
          d="M 92 85 L 100 92 L 108 85 L 108 100 L 92 100 Z"
          fill="#27272a"
          stroke="#3f3f46"
          strokeWidth="1"
        />
        <path
          d="M 100 78 Q 88 84 90 92 Q 100 88 110 92 Q 112 84 100 78"
          stroke="rgba(250, 204, 21, 0.95)"
          strokeWidth="2"
          fill="none"
        />
      </g>
    </svg>
  );
}
