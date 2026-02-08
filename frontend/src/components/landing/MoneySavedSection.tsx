import { useEffect, useRef, useState } from "react";
import { onScroll } from "animejs";

interface MoneySavedSectionProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
}

const TARGET_DOLLARS = 1250;
const TICK_MS = 40;
const INCREMENT = TARGET_DOLLARS / 80;

export function MoneySavedSection({ containerRef }: MoneySavedSectionProps) {
  const sectionRef = useRef<HTMLElement>(null);
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

  return (
    <section
      ref={sectionRef}
      className="min-h-screen flex flex-col items-center justify-center bg-background px-4"
    >
      <p className="text-muted-foreground text-lg mb-2">Money saved</p>
      <p className="font-lumos text-5xl sm:text-6xl md:text-7xl font-bold text-foreground tabular-nums">
        ${amount.toLocaleString()}
      </p>
    </section>
  );
}
