"use client";
import { useEffect } from "react";

/** Scroll-reveal: adds .cg-visible to every [data-reveal] element when it
 *  enters the viewport. Pair with the [data-reveal] rules in marketing.css.
 *  Optional per-element stagger via data-delay="120" (ms). */
export function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>("[data-reveal]");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          const el = e.target as HTMLElement;
          el.style.transitionDelay = (el.dataset.delay || "0") + "ms";
          el.classList.add("cg-visible");
          io.unobserve(el);
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}
