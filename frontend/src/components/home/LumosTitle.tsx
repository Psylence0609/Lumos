/**
 * Dashboard title "Lumos" with anime.js splitText — front (Lum) yellow, back (os) wine red.
 * https://animejs.com/documentation/text/splittext/textsplitter-settings/accessible
 */
import { useEffect, useRef } from "react";
import { createTimeline, splitText, stagger } from "animejs";
import { cn } from "@/lib/utils";

const TITLE_TEXT = "Lumos";
const YELLOW = "#facc15";   // front part
const WINE_RED = "#722f37";  // back part

export function LumosTitle({
  className,
  size = "default",
}: {
  className?: string;
  size?: "default" | "hero";
}) {
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const el = titleRef.current;
    if (!el) return;
    el.textContent = TITLE_TEXT;
    const split = splitText(el, { chars: false, debug: true, accessible: true });
    const $accessible = split.$target.firstChild as HTMLElement | null;

    if ($accessible) {
      $accessible.style.cssText = `
        opacity: 0;
        position: absolute;
        color: var(YELLOW);
        width: 100%;
        height: 100%;
        left: 0;
        top: 0;
        outline: currentColor dotted 1px;
      `;
    }

    const chars = split.chars as HTMLElement[];
    const frontCount = 3; // "Lum"
    const frontChars = chars.slice(0, frontCount);
    const backChars = chars.slice(frontCount);  // "os"

    const tl = createTimeline({
      defaults: { ease: "inOutQuad" },
    });
    if ($accessible) tl.add($accessible, { opacity: 0.4, z: "-3.5rem" }, 0);
    tl.add(el, { rotateX: 0, rotateY: 60 }, 0)
      .add(split.words, {
        z: "3rem",
        opacity: 0.9,
        color: YELLOW,
        outlineColor: { from: YELLOW },
        duration: 750,
        delay: stagger(40, { from: "first" }),
      }, 0)
      .init();
  }, []);

  return (
    <div
      className={cn("lumos-title-perspective w-full flex justify-center", className)}
      style={{ perspective: "600px" }}
    >
      <h1
        ref={titleRef}
        className={cn(
          "lumos-title-text font-lumos font-bold tracking-tight text-center",
          size === "hero"
            ? "text-6xl sm:text-7xl md:text-8xl"
            : "text-3xl sm:text-4xl md:text-5xl"
        )}
        style={{ transformStyle: "preserve-3d" }}
        aria-label={TITLE_TEXT}
      />
    </div>
  );
}
