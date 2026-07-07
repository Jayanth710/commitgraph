"use client";

const MONO = "'JetBrains Mono', monospace";
const A = "#3b82f6"; // accent
const NODE_STROKE = "rgba(148,163,184,0.22)";
const NODE_FILL = "#0b1220";

/** Animated pipeline diagram: sources → PII redaction → LangGraph (3 nodes)
 *  → PostgreSQL → live outputs, plus scheduler → Daily Brief (cron path).
 *  Pure SVG + SMIL — no JS, loops forever. Wrap in an overflow-x:auto
 *  container with minWidth for mobile (see LandingPage). */
export default function PipelineDiagram() {
  return (
    <svg
      viewBox="0 0 1240 420"
      width="100%"
      style={{ display: "block", overflow: "visible", fontFamily: "'Inter', sans-serif" }}
    >
      <defs>
        <filter id="cgGlow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="cgSpine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor={A} stopOpacity="0.05" />
          <stop offset="0.5" stopColor={A} stopOpacity="0.55" />
          <stop offset="1" stopColor={A} stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {/* connectors */}
      <g stroke={A} fill="none" strokeOpacity="0.28" strokeWidth="1.5">
        <path d="M208 144 C 250 144 254 212 290 216" />
        <path d="M208 220 H 290" />
        <path d="M208 296 C 250 296 254 228 290 224" />
        <path d="M440 220 H 490" />
        <path d="M612 220 H 628" strokeOpacity="0.5" />
        <path d="M732 220 H 748" strokeOpacity="0.5" />
        <path d="M870 220 H 900" />
        <path d="M1004 210 C 1030 210 1030 144 1050 144" />
        <path d="M1004 220 H 1050" />
      </g>

      {/* scheduled (cron) path */}
      <path
        d="M952 274 V 346"
        stroke={A}
        strokeOpacity="0.4"
        strokeWidth="1.5"
        fill="none"
        strokeDasharray="3 5"
        style={{ animation: "cg-dash-slow 1.2s linear infinite" }}
      />
      <path d="M1004 372 H 1050" stroke={A} strokeOpacity="0.28" strokeWidth="1.5" fill="none" />
      <text x="962" y="316" fill="#64748b" fontSize="9.5" fontFamily={MONO}>cron</text>

      {/* animated flow line: sources -> DB */}
      <path
        d="M208 220 H 900"
        stroke="url(#cgSpine)"
        strokeWidth="2.5"
        fill="none"
        strokeDasharray="6 8"
        style={{ animation: "cg-dash 0.9s linear infinite" }}
      />

      {/* SOURCES (behind packets so flow emerges from them) */}
      <g>
        <rect x="40" y="120" width="168" height="48" rx="11" fill={NODE_FILL} stroke={NODE_STROKE} />
        <circle cx="66" cy="144" r="5" fill="#ea4335" />
        <text x="84" y="149" fill="#e2e8f0" fontSize="15" fontWeight="500">Gmail</text>
        <text x="192" y="149" textAnchor="end" fill="#64748b" fontSize="9.5" fontFamily={MONO}>webhook</text>
        <rect x="40" y="196" width="168" height="48" rx="11" fill={NODE_FILL} stroke={NODE_STROKE} />
        <circle cx="66" cy="220" r="5" fill="#0a84ff" />
        <text x="84" y="225" fill="#e2e8f0" fontSize="15" fontWeight="500">Outlook</text>
        <text x="192" y="225" textAnchor="end" fill="#64748b" fontSize="9.5" fontFamily={MONO}>stream</text>
        <rect x="40" y="272" width="168" height="48" rx="11" fill={NODE_FILL} stroke={NODE_STROKE} />
        <circle cx="66" cy="296" r="5" fill="#a855f7" />
        <text x="84" y="301" fill="#e2e8f0" fontSize="15" fontWeight="500">Slack</text>
        <text x="192" y="301" textAnchor="end" fill="#64748b" fontSize="9.5" fontFamily={MONO}>stream</text>
      </g>

      {/* packets (rendered before the boxes so they slip behind each node) */}
      <g filter="url(#cgGlow)">
        <circle r="3.5" fill="#ea4335">
          <animateMotion path="M208 144 C 250 144 254 212 290 216" dur="1.5s" begin="0s" repeatCount="indefinite" />
        </circle>
        <circle r="3.5" fill="#0a84ff">
          <animateMotion path="M208 220 H 290" dur="1.5s" begin="0.5s" repeatCount="indefinite" />
        </circle>
        <circle r="3.5" fill="#a855f7">
          <animateMotion path="M208 296 C 250 296 254 228 290 224" dur="1.5s" begin="1s" repeatCount="indefinite" />
        </circle>
      </g>
      <g fill={A} filter="url(#cgGlow)">
        <circle r="4.5">
          <animateMotion path="M290 220 H 900" dur="2.4s" begin="0s" repeatCount="indefinite" />
        </circle>
        <circle r="4.5">
          <animateMotion path="M290 220 H 900" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
        </circle>
        <circle r="4.5">
          <animateMotion path="M290 220 H 900" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
        </circle>
      </g>
      {/* DB -> live outputs */}
      <g filter="url(#cgGlow)">
        <circle r="3.8" fill="#2dd4bf">
          <animateMotion path="M1004 210 C 1030 210 1030 144 1050 144" dur="0.9s" begin="0.3s" repeatCount="indefinite" />
        </circle>
        <circle r="3.8" fill="#60a5fa">
          <animateMotion path="M1004 220 H 1050" dur="0.9s" begin="0.9s" repeatCount="indefinite" />
        </circle>
      </g>
      {/* scheduled brief packets (slow cadence) */}
      <g filter="url(#cgGlow)">
        <circle r="3.4" fill="#fbbf24">
          <animateMotion path="M952 274 V 346" dur="1.4s" begin="0s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.85;1" dur="1.4s" begin="0s" repeatCount="indefinite" />
        </circle>
        <circle r="3.4" fill="#fbbf24">
          <animateMotion path="M1004 372 H 1050" dur="0.7s" begin="1.4s" repeatCount="indefinite" />
        </circle>
      </g>

      {/* PII REDACTION */}
      <rect x="290" y="172" width="150" height="96" rx="14" fill={NODE_FILL} stroke="rgba(148,163,184,0.24)" />
      <path
        d="M365 182 l13 5 v9 c0 8 -5 13 -13 17 c-8 -4 -13 -9 -13 -17 v-9 z"
        fill="none"
        stroke={A}
        strokeWidth="1.6"
      />
      <text x="365" y="228" textAnchor="middle" fill="#f1f5f9" fontSize="14" fontWeight="600">PII Redaction</text>
      <text x="365" y="246" textAnchor="middle" fill="#64748b" fontSize="10" fontFamily={MONO}>strip · redact PII</text>

      {/* LANGGRAPH container */}
      <rect
        x="490" y="120" width="380" height="200" rx="18"
        fill="rgba(96,165,250,0.045)"
        stroke={A} strokeOpacity="0.32" strokeDasharray="2 5"
      />
      <text x="508" y="112" fill={A} fontSize="11" fontWeight="600" letterSpacing="1.5" fontFamily={MONO}>
        LANGGRAPH · 3-NODE PIPELINE
      </text>

      {/* node glows (sequenced) */}
      <g fill="none" stroke={A} strokeWidth="2" filter="url(#cgGlow)">
        <rect x="508" y="170" width="104" height="100" rx="12" opacity="0.1">
          <animate attributeName="opacity" values="0.1;0.9;0.1" keyTimes="0;0.15;0.45" dur="3s" begin="0s" repeatCount="indefinite" />
        </rect>
        <rect x="628" y="170" width="104" height="100" rx="12" opacity="0.1">
          <animate attributeName="opacity" values="0.1;0.9;0.1" keyTimes="0;0.15;0.45" dur="3s" begin="1s" repeatCount="indefinite" />
        </rect>
        <rect x="748" y="170" width="104" height="100" rx="12" opacity="0.1">
          <animate attributeName="opacity" values="0.1;0.9;0.1" keyTimes="0;0.15;0.45" dur="3s" begin="2s" repeatCount="indefinite" />
        </rect>
      </g>
      {/* node bodies */}
      <g>
        <rect x="508" y="170" width="104" height="100" rx="12" fill="#0d1526" stroke={NODE_STROKE} />
        <text x="560" y="216" textAnchor="middle" fill="#f1f5f9" fontSize="15" fontWeight="600">Extract</text>
        <text x="560" y="236" textAnchor="middle" fill="#64748b" fontSize="9.5" fontFamily={MONO}>structured LLM</text>
        <rect x="628" y="170" width="104" height="100" rx="12" fill="#0d1526" stroke={NODE_STROKE} />
        <text x="680" y="216" textAnchor="middle" fill="#f1f5f9" fontSize="15" fontWeight="600">Resolve</text>
        <text x="680" y="236" textAnchor="middle" fill="#64748b" fontSize="9.5" fontFamily={MONO}>entity linking</text>
        <rect x="748" y="170" width="104" height="100" rx="12" fill="#0d1526" stroke={NODE_STROKE} />
        <text x="800" y="216" textAnchor="middle" fill="#f1f5f9" fontSize="15" fontWeight="600">Reconcile</text>
        <text x="800" y="236" textAnchor="middle" fill="#64748b" fontSize="9.5" fontFamily={MONO}>dedupe · upsert</text>
      </g>

      {/* POSTGRES */}
      <g>
        <path d="M900 172 A52 11 0 0 0 1004 172 L1004 268 A52 11 0 0 1 900 268 Z" fill={NODE_FILL} stroke="rgba(148,163,184,0.24)" />
        <ellipse cx="952" cy="172" rx="52" ry="11" fill="#0d1526" stroke={A} strokeOpacity="0.5" />
        <path d="M900 196 A52 11 0 0 0 1004 196" fill="none" stroke="rgba(148,163,184,0.14)" />
        <text x="952" y="228" textAnchor="middle" fill="#f1f5f9" fontSize="13.5" fontWeight="600">PostgreSQL</text>
        <text x="952" y="245" textAnchor="middle" fill="#64748b" fontSize="9" fontFamily={MONO}>reconciled store</text>
      </g>

      {/* SCHEDULER */}
      <g>
        <rect x="900" y="346" width="104" height="52" rx="12" fill={NODE_FILL} stroke={NODE_STROKE} />
        <circle cx="922" cy="372" r="7" fill="none" stroke="#fbbf24" strokeWidth="1.4" />
        <path d="M922 368 V372 L925 375" fill="none" stroke="#fbbf24" strokeWidth="1.4" strokeLinecap="round" />
        <text x="938" y="369" fill="#e2e8f0" fontSize="11.5" fontWeight="500">Scheduler</text>
        <text x="938" y="382" fill="#64748b" fontSize="8.5" fontFamily={MONO}>AM · PM</text>
      </g>

      {/* OUTPUTS */}
      <g>
        <rect x="1050" y="120" width="172" height="48" rx="11" fill={NODE_FILL} stroke={NODE_STROKE} />
        <circle cx="1076" cy="144" r="5" fill="#2dd4bf" />
        <text x="1094" y="149" fill="#e2e8f0" fontSize="14.5" fontWeight="500">Commitments</text>
        <rect x="1050" y="196" width="172" height="48" rx="11" fill={NODE_FILL} stroke={NODE_STROKE} />
        <circle cx="1076" cy="220" r="5" fill="#60a5fa" />
        <text x="1094" y="225" fill="#e2e8f0" fontSize="14.5" fontWeight="500">Job Tracking</text>
        <rect x="1050" y="346" width="172" height="52" rx="11" fill={NODE_FILL} stroke="rgba(251,191,36,0.28)" />
        <circle cx="1076" cy="372" r="5" fill="#fbbf24" />
        <text x="1094" y="369" fill="#e2e8f0" fontSize="14.5" fontWeight="500">Daily Brief</text>
        <text x="1094" y="384" fill="#64748b" fontSize="9" fontFamily={MONO}>generated from DB</text>
      </g>
    </svg>
  );
}
