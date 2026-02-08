import { useEffect, useRef, useState } from "react";
import { animate, onScroll, stagger, splitText, utils } from "animejs";

interface MoneySavedSectionProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
}

const TARGET_DOLLARS = 1250;
const TICK_MS = 40;
const INCREMENT = TARGET_DOLLARS / 80;
const SUBTEXT = "Mitigate equipment damage and extend device life.";
const HOVER_COLORS = ["#FF4B4B", "#FFCC2A", "#B7FF54", "#57F695"];

export function MoneySavedSection({ containerRef }: MoneySavedSectionProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const subtextRef = useRef<HTMLParagraphElement>(null);
  const [amount, setAmount] = useState(0);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    const target = sectionRef.current;
    if (!container || !target) return;

    const observer = onScroll({
      container,
      target,
      axis: "y",
      enter: 0.2,
      onEnter: () => setStarted(true),
    });

    return () => {
      observer.revert();
    };
  }, [containerRef]);

  useEffect(() => {
    if (!started) return;
    let current = 0;
    const id = setInterval(() => {
      current += INCREMENT;
      if (current >= TARGET_DOLLARS) {
        setAmount(TARGET_DOLLARS);
        clearInterval(id);
        return;
      }
      setAmount(Math.round(current));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [started]);

  // Animated subtext (same as lamp tagline: splitText line y + word hover color)
  useEffect(() => {
    const p = subtextRef.current;
    if (!p || !started) return;
    p.textContent = SUBTEXT;
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
  }, [started]);

  return (
    <section
      ref={sectionRef}
      className="min-h-screen flex flex-col items-center justify-center bg-background px-4"
    >
      <p className="text-muted-foreground text-lg mb-2">Money saved</p>
      <div className="flex items-baseline justify-center gap-3 mb-6">
        <p className="font-lumos text-5xl sm:text-6xl md:text-7xl font-bold text-foreground tabular-nums">
          ${amount.toLocaleString()}
        </p>
        <span className="font-lumos text-2xl sm:text-3xl text-muted-foreground">/year</span>
      </div>
      <p
        ref={subtextRef}
        className="font-lumos text-xl sm:text-2xl text-muted-foreground text-center max-w-[24ch]"
      />
    </section>
  );
}
