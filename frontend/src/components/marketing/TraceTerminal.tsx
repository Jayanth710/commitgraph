"use client";
import { useEffect, useRef } from "react";

const MONO = "'JetBrains Mono', monospace";

/** [prefix, prefixColor, tag, detail] */
const LINES: [string, string, string, string][] = [
  ["→", "#60a5fa", "ingest", "gmail#18f2 · 1 new message"],
  ["→", "#a855f7", "redact", "−312 tokens · 2 PII masked"],
  ["→", "#60a5fa", "extract", "2 commitments · 148ms"],
  ["→", "#60a5fa", "resolve", "merged thread#a91 · 62ms"],
  ["✓", "#34d399", "reconcile", "dedup 1 · upsert 1"],
  ["✓", "#2dd4bf", "commit#c41", "\u0022Send Q3 forecast\u0022 · due Fri · 0.92"],
  ["✓", "#fbbf24", "brief", "scheduled AM · from DB"],
  ["—", "#64748b", "eval gate", "precision 0.87 · passed ✓"],
];

/** LangSmith-style streaming trace terminal. Loops forever. */
export default function TraceTerminal() {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    let i = 0;
    const add = () => {
      const [pre, col, tag, det] = LINES[i % LINES.length];
      const row = document.createElement("div");
      row.style.cssText =
        "opacity:0;transform:translateY(4px);transition:opacity .3s ease, transform .3s ease;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
      row.innerHTML =
        '<span style="color:' + col + ';font-weight:600;">' + pre +
        '</span> <span style="color:#cbd5e1;">' + tag +
        '</span> <span style="color:#64748b;">' + det + "</span>";
      box.appendChild(row);
      requestAnimationFrame(() => {
        row.style.opacity = "1";
        row.style.transform = "none";
      });
      i++;
      if (i % LINES.length === 0) {
        const sep = document.createElement("div");
        sep.style.cssText = "height:10px;";
        box.appendChild(sep);
      }
      while (box.children.length > 8) box.removeChild(box.firstChild as Node);
    };
    add();
    const id = setInterval(add, 850);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="cg-card"
      data-reveal
      data-delay="80"
      style={{
        marginTop: 18,
        borderRadius: 18,
        border: "1px solid rgba(148,163,184,0.14)",
        background: "#080b12",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "12px 16px",
          borderBottom: "1px solid rgba(148,163,184,0.1)",
          background: "rgba(255,255,255,0.02)",
        }}
      >
        <span style={{ width: 9, height: 9, borderRadius: 999, background: "#f87171" }} />
        <span style={{ width: 9, height: 9, borderRadius: 999, background: "#fbbf24" }} />
        <span style={{ width: 9, height: 9, borderRadius: 999, background: "#34d399" }} />
        <span style={{ marginLeft: 8, fontFamily: MONO, fontSize: 11.5, color: "#64748b" }}>
          langsmith · live trace
        </span>
        <span
          style={{
            marginLeft: "auto",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontFamily: MONO,
            fontSize: 10.5,
            color: "#34d399",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: "#34d399",
              animation: "cg-pulse 1.6s ease infinite",
            }}
          />
          streaming
        </span>
      </div>
      <div
        ref={boxRef}
        style={{
          fontFamily: MONO,
          fontSize: 12.5,
          lineHeight: 2,
          padding: "14px 18px",
          height: 210,
          overflow: "hidden",
          color: "#94a3b8",
        }}
      />
    </div>
  );
}
