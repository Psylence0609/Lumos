import { useRef } from "react";
import { LumosTitle } from "@/components/home/LumosTitle";
import { BulbSection } from "@/components/landing/BulbSection";
import { MoneySavedSection } from "@/components/landing/MoneySavedSection";
import { NoiseBlobSection } from "@/components/landing/NoiseBlobSection";
import { GoogleSignInSection } from "@/components/landing/GoogleSignInSection";

const HERO_SCROLL_HEIGHT_VH = 700;

export function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const heroScrollRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={containerRef}
      className="h-screen overflow-y-auto bg-background scrollbar-hide"
    >
      {/* Hero scroll zone: 700vh tall; content is sticky so title + blob stay on screen while scroll advances steps 1→7 */}
      <div
        ref={heroScrollRef}
        className="overflow-visible"
        style={{ minHeight: `${HERO_SCROLL_HEIGHT_VH}vh` }}
      >
        <div
          className="sticky top-0 min-h-screen w-full flex flex-col items-center justify-center px-4 relative overflow-visible"
          style={{ minHeight: "100vh" }}
        >
          {/* Blob canvas: absolutely centered in this sticky area (behind title) */}
          <NoiseBlobSection
            containerRef={containerRef}
            heroScrollRef={heroScrollRef}
            heroScrollHeightVh={HERO_SCROLL_HEIGHT_VH}
          />
          <LumosTitle size="hero" className="relative z-10" />
        </div>
      </div>

      {/* Desk lamp: bouncy entrance then lights up */}
      <BulbSection containerRef={containerRef} />

      {/* Money saved: counter starts when section enters view */}
      <MoneySavedSection containerRef={containerRef} />

      {/* Google sign-in (to be implemented later) */}
      <GoogleSignInSection />
    </div>
  );
}
