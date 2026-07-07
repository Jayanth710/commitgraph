"use client";
import React, { useEffect } from "react";
import Tour from "./Tour";
import TraceTerminal from "./TraceTerminal";
import CountUp from "./CountUp";
import { useReveal } from "./useReveal";

/* ── tokens ────────────────────────────────────────────── */
const SIGN_IN = "/login";
const LIVE_DEMO = "/login"; // point at a demo account / tour when you have one
const MONO = "'JetBrains Mono', monospace";
const A = "#3b82f6";
const MUTED = "#94a3b8";
const DIM = "#64748b";
const LIGHT = "#cbd5e1";
const BORDER = "1px solid rgba(148,163,184,0.14)";
const CARD_BG = "rgba(255,255,255,0.025)";

const eyebrow: React.CSSProperties = { fontFamily: MONO, fontSize: 12, letterSpacing: 2, color: A };
const h2Style: React.CSSProperties = {
  margin: "14px 0 0",
  fontSize: "clamp(28px, 3.6vw, 46px)",
  fontWeight: 700,
  letterSpacing: "-0.025em",
  lineHeight: 1.08,
};
const card: React.CSSProperties = { padding: 26, borderRadius: 18, border: BORDER, background: CARD_BG };
const sec: React.CSSProperties = {
  position: "relative",
  zIndex: 1,
  maxWidth: 1180,
  margin: "0 auto",
  padding: "70px 32px 40px",
};
const primaryBtn: React.CSSProperties = {
  padding: "13px 24px",
  fontSize: 15,
  fontWeight: 600,
  color: "#fff",
  borderRadius: 11,
  background: A,
  boxShadow: "0 10px 30px -8px rgba(59,130,246,0.7)",
  textDecoration: "none",
};
const ghostBtn: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "13px 22px",
  fontSize: 15,
  fontWeight: 500,
  color: LIGHT,
  borderRadius: 11,
  border: "1px solid rgba(148,163,184,0.22)",
  textDecoration: "none",
};

function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={A} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="4.5" r="2.5" />
      <path d="m10.2 6.3-3.9 3.9" />
      <circle cx="4.5" cy="12" r="2.5" />
      <path d="M7 12h10" />
      <circle cx="19.5" cy="12" r="2.5" />
      <circle cx="12" cy="19.5" r="2.5" />
      <path d="m13.8 17.7 3.9-3.9" />
    </svg>
  );
}

const pill = (bg: string, color: string): React.CSSProperties => ({
  fontSize: 11,
  padding: "4px 9px",
  borderRadius: 999,
  fontWeight: 500,
  background: bg,
  color,
  whiteSpace: "nowrap",
});

function MiniRow({ title, meta, tag, last = false }: { title: string; meta: string; tag: React.ReactNode; last?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 10,
        padding: 16,
        borderBottom: last ? "none" : "1px solid rgba(148,163,184,0.1)",
      }}
    >
      <div>
        <div style={{ fontSize: 14, fontWeight: 500 }}>{title}</div>
        <div style={{ marginTop: 5, fontSize: 12, color: DIM }}>{meta}</div>
      </div>
      {tag}
    </div>
  );
}

/* ── page ──────────────────────────────────────────────── */
export default function LandingPage() {
  useReveal();

  const replayTour = (e: React.MouseEvent) => {
    e.preventDefault();
    const host = document.querySelector("[data-tour]");
    if (host) {
      const r = host.getBoundingClientRect();
      window.scrollTo({ top: r.top + window.pageYOffset - 96, behavior: "smooth" });
    }
    window.dispatchEvent(new CustomEvent("cg-tour-replay"));
  };

  // scrollspy + cursor spotlight
  useEffect(() => {
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".cg-navlink"));
    const onScroll = () => {
      let active: HTMLAnchorElement | null = null;
      links.forEach((a) => {
        const s = document.getElementById((a.getAttribute("href") || "").slice(1));
        if (s && s.getBoundingClientRect().top < 150) active = a;
      });
      links.forEach((a) => a.classList.toggle("cg-active", a === active));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    let spot: HTMLDivElement | null = null;
    let onMove: ((e: MouseEvent) => void) | null = null;
    if (!window.matchMedia("(pointer: coarse)").matches) {
      spot = document.createElement("div");
      spot.style.cssText =
        "position:fixed;top:0;left:0;width:520px;height:520px;border-radius:999px;background:radial-gradient(circle,rgba(59,130,246,0.10),transparent 60%);pointer-events:none;z-index:60;transform:translate(-50%,-50%);opacity:0;transition:opacity .5s ease;mix-blend-mode:screen;";
      document.body.appendChild(spot);
      onMove = (e: MouseEvent) => {
        if (!spot) return;
        spot.style.opacity = "1";
        spot.style.left = e.clientX + "px";
        spot.style.top = e.clientY + "px";
      };
      window.addEventListener("mousemove", onMove, { passive: true });
    }
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (onMove) window.removeEventListener("mousemove", onMove);
      spot?.remove();
    };
  }, []);

  return (
    <div className="cg-landing" style={{ position: "relative", overflow: "hidden", background: "#05070d", color: "#f1f5f9", fontFamily: "'Inter', sans-serif" }}>
      {/* ambient glows */}
      <div style={{ position: "absolute", top: -160, left: "50%", transform: "translateX(-50%)", width: 900, height: 520, background: "radial-gradient(ellipse at center, rgba(59,130,246,0.22), transparent 68%)", pointerEvents: "none", zIndex: 0 }} />
      <div style={{ position: "absolute", top: 1400, right: -200, width: 620, height: 620, background: "radial-gradient(circle at center, rgba(139,92,246,0.12), transparent 66%)", pointerEvents: "none", zIndex: 0 }} />

      {/* NAV */}
      <nav className="cg-nav" style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 32px", background: "rgba(5,7,13,0.72)", backdropFilter: "blur(14px)", borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
        <a href="#top" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none", color: "inherit" }}>
          <Logo />
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.01em" }}>CommitGraph</span>
        </a>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <a href="#how" className="cg-navlink">How it works</a>
          <a href="#workflows" className="cg-navlink">Workflows</a>
          <a href="#trust" className="cg-navlink">Trust</a>
          <a href={SIGN_IN} style={{ padding: "9px 15px", fontSize: 14, fontWeight: 500, color: LIGHT, borderRadius: 9, border: "1px solid rgba(148,163,184,0.2)", textDecoration: "none" }}>Sign in</a>
          <a href={LIVE_DEMO} style={{ padding: "9px 16px", fontSize: 14, fontWeight: 600, color: "#fff", borderRadius: 9, background: A, boxShadow: "0 6px 20px -6px rgba(59,130,246,0.6)", textDecoration: "none" }}>Live demo</a>
        </div>
      </nav>

      {/* HERO */}
      <div id="top" style={{ position: "relative", zIndex: 1 }}>
        <section className="cg-sec" style={{ maxWidth: 1180, margin: "0 auto", padding: "148px 32px 40px", textAlign: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 13px", borderRadius: 999, border: "1px solid rgba(148,163,184,0.2)", background: "rgba(255,255,255,0.03)", fontFamily: MONO, fontSize: 11.5, letterSpacing: 1.5, color: A, animation: "cg-rise 0.7s ease both" }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: A, animation: "cg-pulse 2s ease infinite" }} />
            AI COMMUNICATION INTELLIGENCE
          </div>
          <h1 style={{ margin: "24px auto 0", maxWidth: 900, fontSize: "clamp(38px, 6vw, 72px)", lineHeight: 1.02, fontWeight: 800, letterSpacing: "-0.03em", animation: "cg-rise 0.7s ease 0.08s both" }}>
            Every promise in your inbox,{" "}
            <span style={{ background: `linear-gradient(120deg, ${A}, #93c5fd)`, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
              tracked automatically.
            </span>
          </h1>
          <p style={{ margin: "22px auto 0", maxWidth: 640, fontSize: "clamp(16px, 1.6vw, 20px)", lineHeight: 1.55, color: MUTED, animation: "cg-rise 0.7s ease 0.16s both" }}>
            CommitGraph turns Gmail, Outlook &amp; Slack into commitments, job-application timelines, and daily briefs — one LangGraph pipeline, grounded in the exact line that earned it.
          </p>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginTop: 32, flexWrap: "wrap", animation: "cg-rise 0.7s ease 0.24s both" }}>
            <a href={LIVE_DEMO} onClick={replayTour} style={primaryBtn}>Try the live demo</a>
            <a href="#how" style={ghostBtn}>Watch the workflow<span style={{ color: A }}>↓</span></a>
          </div>
          <div style={{ marginTop: 56, padding: 20, borderRadius: 22, border: BORDER, background: "linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.008))", boxShadow: "0 40px 90px -40px rgba(0,0,0,0.8)", animation: "cg-rise 0.9s ease 0.34s both" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "4px 6px 14px" }}>
              <span style={{ width: 11, height: 11, borderRadius: 999, background: "#f87171" }} />
              <span style={{ width: 11, height: 11, borderRadius: 999, background: "#fbbf24" }} />
              <span style={{ width: 11, height: 11, borderRadius: 999, background: "#34d399" }} />
              <span style={{ marginLeft: 10, fontFamily: MONO, fontSize: 11, color: DIM }}>commitgraph · guided tour</span>
            </div>
            <Tour />
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 28, marginTop: 30, flexWrap: "wrap", fontFamily: MONO, fontSize: 13, color: DIM, animation: "cg-rise 0.9s ease 0.44s both" }}>
            <span><b style={{ color: "#e2e8f0" }}>87%</b> precision</span>
            <span style={{ opacity: 0.35 }}>·</span>
            <span><b style={{ color: "#e2e8f0" }}>sub-second</b> latency</span>
            <span style={{ opacity: 0.35 }}>·</span>
            <span><b style={{ color: "#e2e8f0" }}>−30%</b> LLM tokens</span>
            <span style={{ opacity: 0.35 }}>·</span>
            <span><b style={{ color: "#e2e8f0" }}>300+</b> labeled emails</span>
          </div>
        </section>
      </div>

      {/* HOW IT WORKS */}
      <section id="how" className="cg-sec" style={{ ...sec, padding: "90px 32px 40px" }}>
        <div data-reveal>
          <div style={eyebrow}>ARCHITECTURE</div>
          <h2 style={{ ...h2Style, maxWidth: 720 }}>One pipeline. Three products.</h2>
          <p style={{ margin: "16px 0 0", maxWidth: 640, fontSize: 17, lineHeight: 1.6, color: MUTED }}>
            The same three-node LangGraph pipeline — <b style={{ color: LIGHT }}>extract → resolve → reconcile</b> — powers commitment tracking, job-application lifecycles, and daily briefs. Build once, ship three features.
          </p>
        </div>

        <div className="cg-2col" data-reveal data-delay="80" style={{ marginTop: 40, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
          <div className="cg-card" style={card}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: "#ea4335" }} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>Gmail · webhook</span>
            </div>
            <p style={{ margin: "12px 0 0", fontSize: 14.5, lineHeight: 1.6, color: MUTED }}>
              Pub/Sub push notifications processed <b style={{ color: LIGHT }}>inline</b> — sub-second webhook-to-processing latency.
            </p>
          </div>
          <div className="cg-card" style={card}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: "#0a84ff" }} />
              <span style={{ width: 8, height: 8, borderRadius: 999, background: "#a855f7" }} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>Outlook &amp; Slack · Redis Streams</span>
            </div>
            <p style={{ margin: "12px 0 0", fontSize: 14.5, lineHeight: 1.6, color: MUTED }}>
              Consumer groups decouple ingestion — Microsoft Graph needs sub-second ACK, so processing is <b style={{ color: LIGHT }}>queued</b>, not blocking.
            </p>
          </div>
        </div>

        <div className="cg-3col" data-reveal data-delay="140" style={{ marginTop: 18, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 18 }}>
          {[
            ["01 · EXTRACT", "Structured extraction", "Structured-output LLM prompts with retry logic pull commitments, lifecycle events, and brief material."],
            ["02 · RESOLVE", "Entity resolution", "People and threads are normalized into a common schema across every account and channel."],
            ["03 · RECONCILE", "Dedupe & upsert", "Embedding similarity suppresses duplicates across forwarded threads; two-tier upsert keeps one record per item."],
          ].map(([tag, title, body]) => (
            <div key={tag} className="cg-card" style={card}>
              <div style={{ fontFamily: MONO, fontSize: 12, color: A }}>{tag}</div>
              <h3 style={{ margin: "12px 0 0", fontSize: 18, fontWeight: 600 }}>{title}</h3>
              <p style={{ margin: "10px 0 0", fontSize: 14, lineHeight: 1.6, color: MUTED }}>{body}</p>
            </div>
          ))}
        </div>

        <TraceTerminal />
      </section>

      {/* WORKFLOWS */}
      <section id="workflows" className="cg-sec" style={sec}>
        <div data-reveal>
          <div style={eyebrow}>WHAT YOU GET</div>
          <h2 style={h2Style}>Three workflows, one inbox.</h2>
        </div>

        {/* commitments */}
        <div className="cg-row" data-reveal data-delay="60" style={{ marginTop: 44, display: "grid", gridTemplateColumns: "1fr 1.1fr", gap: 44, alignItems: "center" }}>
          <div>
            <div style={{ fontFamily: MONO, fontSize: 12, color: "#2dd4bf" }}>COMMITMENT EXTRACTION</div>
            <h3 style={{ margin: "12px 0 0", fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em" }}>Who owes what, to whom, by when.</h3>
            <p style={{ margin: "14px 0 0", fontSize: 15.5, lineHeight: 1.6, color: MUTED }}>
              Every action item is tracked with direction (<b style={{ color: LIGHT }}>I owe</b> / <b style={{ color: LIGHT }}>owed to me</b>), owner, target, due date, and a confidence score. Low-confidence items route to a human review queue.
            </p>
          </div>
          <div className="cg-card" style={{ padding: 8, borderRadius: 18, border: BORDER, background: "rgba(255,255,255,0.02)" }}>
            <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid rgba(148,163,184,0.1)" }}>
              <MiniRow title="Send Q3 forecast to Babitha" meta="You → babitha@acme.com · Due Fri, Jul 10" tag={<span style={pill("rgba(30,58,138,0.5)", "#93c5fd")}>confirmed</span>} />
              <MiniRow title="Review contract redlines" meta="← legal@partner.io · Due yesterday" tag={<span style={pill("rgba(127,29,29,0.5)", "#fca5a5")}>overdue</span>} />
              <MiniRow title="Share onboarding deck" meta="You → sam@acme.com · confidence 62%" tag={<span style={pill("rgba(120,53,15,0.5)", "#fcd34d")}>review</span>} last />
            </div>
          </div>
        </div>

        {/* jobs */}
        <div className="cg-row cg-row-flip" data-reveal data-delay="60" style={{ marginTop: 40, display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 44, alignItems: "center" }}>
          <div className="cg-card" style={{ padding: 8, borderRadius: 18, border: BORDER, background: "rgba(255,255,255,0.02)" }}>
            <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid rgba(148,163,184,0.1)" }}>
              <MiniRow title="Stripe — Senior SWE" meta="3 emails · 2 threads merged" tag={<span style={pill("rgba(30,58,138,0.5)", "#93c5fd")}>interview</span>} />
              <MiniRow title="Vercel — Frontend Eng" meta="offer received · Jul 2" tag={<span style={pill("rgba(6,78,59,0.6)", "#6ee7b7")}>offer</span>} />
              <MiniRow title="Datadog — Platform" meta="applied · Jun 28" tag={<span style={pill("rgba(51,65,85,0.6)", LIGHT)}>applied</span>} last />
            </div>
          </div>
          <div>
            <div style={{ fontFamily: MONO, fontSize: 12, color: "#60a5fa" }}>JOB APPLICATION TRACKING</div>
            <h3 style={{ margin: "12px 0 0", fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em" }}>Every application, one timeline.</h3>
            <p style={{ margin: "14px 0 0", fontSize: 15.5, lineHeight: 1.6, color: MUTED }}>
              Lifecycle events — applied, interview, rejected, offer — are detected and consolidated. A two-tier upsert (thread-ID, then company + role) keeps forwarded threads as one coherent history.
            </p>
          </div>
        </div>

        {/* daily brief */}
        <div className="cg-row" data-reveal data-delay="60" style={{ marginTop: 40, display: "grid", gridTemplateColumns: "1fr 1.1fr", gap: 44, alignItems: "center" }}>
          <div>
            <div style={{ fontFamily: MONO, fontSize: 12, color: "#fbbf24" }}>DAILY BRIEF</div>
            <h3 style={{ margin: "12px 0 0", fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em" }}>Your morning, summarized.</h3>
            <p style={{ margin: "14px 0 0", fontSize: 15.5, lineHeight: 1.6, color: MUTED }}>
              Morning and evening summaries generated from structured data — commitments due, overdue items, follow-ups, job updates, and deadlines. No inbox archaeology.
            </p>
          </div>
          <div className="cg-card" style={{ padding: 22, borderRadius: 18, border: BORDER, background: "linear-gradient(180deg, rgba(251,191,36,0.06), rgba(255,255,255,0.015))" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, color: "#fbbf24" }}>☀ Morning Brief · Mon, Jul 7</div>
            <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 11, fontSize: 14, color: LIGHT }}>
              <div style={{ display: "flex", gap: 10 }}><span style={{ color: "#f87171" }}>●</span> 1 overdue — contract redlines from legal@partner.io</div>
              <div style={{ display: "flex", gap: 10 }}><span style={{ color: "#60a5fa" }}>●</span> 2 due today — Q3 forecast, onboarding deck</div>
              <div style={{ display: "flex", gap: 10 }}><span style={{ color: "#34d399" }}>●</span> 3 follow-ups waiting on replies</div>
              <div style={{ display: "flex", gap: 10 }}><span style={{ color: "#fbbf24" }}>●</span> Job update — Vercel moved to offer</div>
            </div>
          </div>
        </div>
      </section>

      {/* TRUST */}
      <section id="trust" className="cg-sec" style={sec}>
        <div data-reveal>
          <div style={eyebrow}>TRUST &amp; PRIVACY</div>
          <h2 style={{ ...h2Style, maxWidth: 760 }}>Grounded in evidence. Private by design.</h2>
        </div>

        <div className="cg-2col" style={{ marginTop: 40, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* evidence */}
          <div className="cg-card" data-reveal data-delay="60" style={{ padding: 30, borderRadius: 20, border: BORDER, background: CARD_BG }}>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>The line that earned it</h3>
            <p style={{ margin: "12px 0 22px", fontSize: 14.5, lineHeight: 1.6, color: MUTED }}>
              Every commitment links back to the exact sentence in the source message. Verify in a glance — no blind trust.
            </p>
            <div style={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.12)", background: "#0a0e18", overflow: "hidden" }}>
              <div style={{ padding: "12px 14px", borderBottom: "1px solid rgba(148,163,184,0.1)", fontSize: 12, color: DIM }}>Re: Q3 planning · Gmail</div>
              <div style={{ padding: "16px 14px", fontSize: 14, lineHeight: 1.7, color: MUTED }}>
                Thanks for the notes.{" "}
                <span style={{ background: "rgba(59,130,246,0.22)", color: "#dbeafe", padding: "2px 4px", borderRadius: 4, boxShadow: "inset 0 0 0 1px rgba(59,130,246,0.4)" }}>
                  I&apos;ll get you the Q3 forecast by Friday.
                </span>{" "}
                Let me know if the format works.
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 14px", borderTop: "1px solid rgba(148,163,184,0.1)", fontSize: 12, color: DIM }}>
                <span style={{ color: A }}>↳</span> extracted: <b style={{ color: LIGHT }}>Send Q3 forecast</b> · due Fri · confidence 92%
              </div>
            </div>
          </div>
          {/* pii */}
          <div className="cg-card" data-reveal data-delay="120" style={{ padding: 30, borderRadius: 20, border: BORDER, background: CARD_BG }}>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>No PII ever reaches the model</h3>
            <p style={{ margin: "12px 0 22px", fontSize: 14.5, lineHeight: 1.6, color: MUTED }}>
              Quotes and signatures are stripped, forwards unwrapped, and PII redacted <b style={{ color: LIGHT }}>before</b> the LLM — cutting input 60–80% and token cost ~30%.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ borderRadius: 10, border: "1px solid rgba(248,113,113,0.25)", background: "rgba(127,29,29,0.12)", padding: "12px 14px", fontSize: 13, lineHeight: 1.6, color: MUTED }}>
                <span style={{ fontFamily: MONO, fontSize: 10, color: "#f87171" }}>BEFORE</span>
                <br />
                Call me at <span style={{ background: "rgba(248,113,113,0.25)", color: "#fecaca", padding: "1px 4px", borderRadius: 3 }}>(415) 555-0192</span>, card{" "}
                <span style={{ background: "rgba(248,113,113,0.25)", color: "#fecaca", padding: "1px 4px", borderRadius: 3 }}>4242 4242 4242 4242</span>
              </div>
              <div style={{ borderRadius: 10, border: "1px solid rgba(52,211,153,0.25)", background: "rgba(6,78,59,0.14)", padding: "12px 14px", fontSize: 13, lineHeight: 1.6, color: LIGHT }}>
                <span style={{ fontFamily: MONO, fontSize: 10, color: "#34d399" }}>SENT TO LLM</span>
                <br />
                Call me at <span style={{ fontFamily: MONO, color: "#6ee7b7" }}>[PHONE]</span>, card <span style={{ fontFamily: MONO, color: "#6ee7b7" }}>[CARD]</span>
              </div>
            </div>
          </div>
        </div>

        <div className="cg-2col" style={{ marginTop: 20, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* review queue */}
          <div className="cg-card" data-reveal data-delay="60" style={{ padding: 30, borderRadius: 20, border: BORDER, background: CARD_BG }}>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Human in the loop</h3>
            <p style={{ margin: "12px 0 22px", fontSize: 14.5, lineHeight: 1.6, color: MUTED }}>
              Low-confidence extractions never auto-commit. They queue for a one-glance review — evidence attached, approve or reject.
            </p>
            <div style={{ borderRadius: 12, border: "1px solid rgba(148,163,184,0.12)", background: "#0a0e18", padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>Share onboarding deck</div>
                <span style={pill("rgba(120,53,15,0.5)", "#fcd34d")}>confidence 62%</span>
              </div>
              <div style={{ marginTop: 10, fontSize: 13, lineHeight: 1.6, color: MUTED }}>
                &quot;…I can probably get the deck over to Sam{" "}
                <span style={{ background: "rgba(251,191,36,0.16)", color: "#fde68a", padding: "1px 4px", borderRadius: 3 }}>sometime next week</span>
                …&quot;
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
                <span style={{ flex: 1, textAlign: "center", padding: "8px 0", borderRadius: 8, border: "1px solid rgba(52,211,153,0.35)", color: "#6ee7b7", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Approve</span>
                <span style={{ flex: 1, textAlign: "center", padding: "8px 0", borderRadius: 8, border: "1px solid rgba(248,113,113,0.3)", color: "#fca5a5", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Reject</span>
              </div>
            </div>
          </div>
          {/* reminders */}
          <div className="cg-card" data-reveal data-delay="120" style={{ padding: 30, borderRadius: 20, border: BORDER, background: CARD_BG }}>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Never miss a deadline</h3>
            <p style={{ margin: "12px 0 26px", fontSize: 14.5, lineHeight: 1.6, color: MUTED, maxWidth: 620 }}>
              Commitments with due dates sync to Google Calendar and ping you on your channel — <b style={{ color: LIGHT }}>1 day before</b> and again <b style={{ color: LIGHT }}>3 hours before</b>.
            </p>
            <div style={{ position: "relative", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              <div style={{ position: "absolute", top: 13, left: "8%", right: "8%", height: 2, background: `linear-gradient(90deg, rgba(59,130,246,0.15), ${A}, rgba(59,130,246,0.15))` }} />
              {[
                ["#64748b", "rgba(100,116,139,0.15)", "Thu 5:00 PM", "Ping — 1 day before"],
                [A, "rgba(59,130,246,0.2)", "Fri 2:00 PM", "Ping — 3 hours before"],
                ["#f87171", "rgba(248,113,113,0.18)", "Fri 5:00 PM", "Deadline · Q3 forecast"],
              ].map(([dot, ring, time, label]) => (
                <div key={time} style={{ position: "relative" }}>
                  <div style={{ width: 12, height: 12, borderRadius: 999, background: dot, boxShadow: `0 0 0 4px ${ring}` }} />
                  <div style={{ marginTop: 16, fontSize: 13, fontWeight: 600 }}>{time}</div>
                  <div style={{ marginTop: 3, fontSize: 12.5, color: DIM }}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* METRICS + STACK */}
      <section id="metrics" className="cg-sec" style={sec}>
        <div className="cg-2col" style={{ display: "grid", gridTemplateColumns: "1.7fr 1fr", gap: 20, alignItems: "stretch" }}>
          <div className="cg-card cg-card-lg" data-reveal style={{ padding: 44, borderRadius: 24, border: BORDER, background: "linear-gradient(180deg, rgba(59,130,246,0.06), rgba(255,255,255,0.01))" }}>
            <div style={eyebrow}>EVALUATION</div>
            <h2 style={{ margin: "14px 0 6px", fontSize: "clamp(26px, 3.4vw, 42px)", fontWeight: 700, letterSpacing: "-0.025em" }}>Measured, not vibes.</h2>
            <p style={{ margin: "0 0 34px", fontSize: 15.5, color: MUTED, maxWidth: 620, lineHeight: 1.6 }}>
              Evaluated on 300+ real labeled emails, with the eval suite running as a <b style={{ color: LIGHT }}>regression gate on every prompt change</b>.
            </p>
            <div className="cg-nums" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 22 }}>
              {[
                [87, "Extraction precision"],
                [78, "Recall"],
                [92, "Direction accuracy"],
              ].map(([n, label]) => (
                <div key={label as string}>
                  <div style={{ fontSize: "clamp(34px, 4vw, 52px)", fontWeight: 800, letterSpacing: "-0.03em", color: "#fff" }}>
                    <CountUp to={n as number} />
                  </div>
                  <div style={{ marginTop: 4, fontSize: 13, color: MUTED }}>{label}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 30, paddingTop: 26, borderTop: "1px solid rgba(148,163,184,0.12)", display: "flex", gap: 32, flexWrap: "wrap", fontFamily: MONO, fontSize: 13, color: MUTED }}>
              <span><b style={{ color: "#fff" }}>−30%</b> token cost</span>
              <span><b style={{ color: "#fff" }}>60–80%</b> input reduction</span>
              <span><b style={{ color: "#fff" }}>sub-second</b> webhook latency</span>
              <span><b style={{ color: "#fff" }}>300+</b> labeled eval emails</span>
            </div>
          </div>

          {/* stack (vertical) */}
          <div className="cg-card" data-reveal data-delay="100" style={{ padding: "28px 30px", borderRadius: 24, border: BORDER, background: "rgba(255,255,255,0.02)", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 16 }}>
            <div style={eyebrow}>STACK</div>
            {[
              ["BACKEND", <>Python · FastAPI<br />PostgreSQL · Redis Streams</>],
              ["AI", <>LangGraph · LiteLLM<br />LangSmith (trace + eval)</>],
              ["FRONTEND", <>Next.js · TypeScript<br />Tailwind · shadcn/ui</>],
              ["INFRA", <>GCP Cloud Run<br />Vercel · Multi-tenant</>],
            ].map(([label, body], idx) => (
              <div key={label as string} style={idx === 0 ? undefined : { borderTop: "1px solid rgba(148,163,184,0.12)", paddingTop: 14 }}>
                <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: 1.5, color: DIM }}>{label}</div>
                <div style={{ marginTop: 6, fontSize: 14, lineHeight: 1.7, color: LIGHT }}>{body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cg-sec" style={{ ...sec, padding: "60px 32px 100px", textAlign: "center" }}>
        <div data-reveal>
          <h2 style={{ margin: "0 auto", maxWidth: 700, fontSize: "clamp(30px, 4.4vw, 56px)", fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1.05 }}>
            See your commitments, live.
          </h2>
          <p style={{ margin: "18px auto 0", maxWidth: 520, fontSize: 17, color: MUTED, lineHeight: 1.55 }}>
            Multi-tenant. Connect Gmail, Outlook &amp; Slack, sync your calendar, and let the pipeline do the reading.
          </p>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginTop: 30, flexWrap: "wrap" }}>
            <a href={LIVE_DEMO} onClick={replayTour} style={{ ...primaryBtn, padding: "14px 26px", borderRadius: 12 }}>Try the live demo</a>
            <a href={SIGN_IN} style={{ ...ghostBtn, padding: "14px 24px", borderRadius: 12 }}>Sign in</a>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ position: "relative", zIndex: 1, borderTop: "1px solid rgba(148,163,184,0.1)", padding: "26px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <Logo size={18} />
          <span style={{ fontSize: 14, fontWeight: 600 }}>CommitGraph</span>
        </div>
        <span style={{ fontFamily: MONO, fontSize: 12, color: DIM }}>Agentic Communication Intelligence · Gmail · Outlook · Slack</span>
      </footer>
    </div>
  );
}
