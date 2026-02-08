import { useEffect, useRef, useState } from "react";
import { animate, onScroll, stagger, splitText, utils } from "animejs";

interface BulbSectionProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
}

const TAGLINE = "Sustainable, Personalized and Proactive home automation.";
const HOVER_COLORS = ["#FF4B4B", "#FFCC2A", "#B7FF54", "#57F695"];

export function BulbSection({ containerRef }: BulbSectionProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const lampRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const taglineRef = useRef<HTMLParagraphElement>(null);
  const [hasEntered, setHasEntered] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    const target = sectionRef.current;
    const lamp = lampRef.current;
    if (!container || !target || !lamp) return;

    const duration = 2000;
    // Roll starts when section enters view (0%) and completes at 20%
    // Stays centered 20%-80%, then scrolls away
    const ROLL_START = 0;
    const ROLL_END = 0.2;
    const STAY_END = 0.8;

    const rollIn = animate(lamp, {
      x: ["15rem", "0"], // Right to center
      rotate: "-1turn", // Roll counterclockwise from right
      duration,
      ease: "outQuad",
      autoplay: false,
    });

    const observer = onScroll({
      container,
      target,
      axis: "y",
      enter: 0, // Start observing when section just enters viewport
      onUpdate: (obs) => {
        // obs.progress goes from 0 (section enters) to 1 (section exits)
        const scrollP = Math.max(0, Math.min(1, obs.progress));

        if (scrollP <= ROLL_END) {
          // Rolling in phase (0% to 20% of section scroll)
          const rollP = scrollP / ROLL_END;
          rollIn.seek(rollP * duration);
        } else {
          // Stay centered phase (20% onwards)
          rollIn.seek(duration); // Keep at end position
        }
      },
    });

    return () => {
      observer.revert();
      rollIn.cancel();
    };
  }, [containerRef]);

  // Light-up glow after lamp rolls in
  useEffect(() => {
    const container = containerRef.current;
    const target = sectionRef.current;
    if (!container || !target) return;

    const observer = onScroll({
      container,
      target,
      axis: "y",
      enter: 0.15, // Trigger when 15% into the section (near end of roll)
      onEnter: () => setHasEntered(true),
    });

    return () => {
      observer.revert();
    };
  }, [containerRef]);

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

  // Tagline: splitText with line y animation + word hover color (same as reference)
  useEffect(() => {
    const p = taglineRef.current;
    if (!p || !hasEntered) return;
    p.textContent = TAGLINE;
    const colors: string[] = [];
    const split = splitText(p, { lines: true });
    split.addEffect(({ lines }: { lines: HTMLElement[] }) =>
      animate(lines, {
        y: ["50%", "-50%"],
        loop: true,
        alternate: true,
        delay: stagger(400),
        ease: "inOutQuad",
      })
    );
    split.addEffect((splitInstance: { words: HTMLElement[] }) => {
      splitInstance.words.forEach(($el: HTMLElement, i: number) => {
        const color = colors[i];
        if (color) utils.set($el, { color });
        $el.addEventListener("pointerenter", () => {
          animate($el, {
            color: utils.randomPick(HOVER_COLORS) as string,
            duration: 250,
          });
        });
      });
      return () => {
        splitInstance.words.forEach((w: HTMLElement, i: number) => {
          colors[i] = utils.get(w, "color") as string;
        });
      };
    });
    return () => {
      split.revert();
    };
  }, [hasEntered]);

  return (
    <section
      ref={sectionRef}
      className="min-h-screen flex items-center justify-center bg-background px-4"
      style={{ minHeight: "300vh" }}
    >
      <div className="sticky top-1/2 flex flex-col items-center justify-center -translate-y-1/2 w-full max-w-xl">
        <div
          ref={lampRef}
          className="relative flex justify-center items-end"
          style={{ transform: "translateX(15rem)" }}
        >
          <div
            ref={glowRef}
            className="absolute bottom-0 left-1/2 -translate-x-1/2 w-48 h-16 rounded-full opacity-0"
            style={{
              background:
                "radial-gradient(ellipse 80% 50% at 50% 100%, rgba(250,204,21,0.4) 0%, transparent 70%)",
              filter: "blur(8px)",
            }}
          />
          <DeskLampSvg />
        </div>
        {/* Tagline when lamp is centered: same font as Lumos, enlarged; splitText line + word hover animation */}
        <p
          ref={taglineRef}
          className={`font-lumos mt-8 text-center text-2xl sm:text-3xl md:text-4xl text-muted-foreground font-medium transition-opacity duration-500 ${hasEntered ? "opacity-100" : "opacity-0"}`}
          style={{ maxWidth: "40ch" }}
        />
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
