"use client";
import { useEffect, useRef } from "react";

/** Auto-playing CommitGraph product tour.
 *  Plays 5 scenes once, then shows a replay end-card.
 *  Also restarts when a `cg-tour-replay` window event fires
 *  (dispatched by the "Try the live demo" buttons).
 *
 *  Markup is injected as HTML (ported verbatim from the design) and driven
 *  imperatively — animations restart naturally when a scene's display flips
 *  from none to flex. Keyframes are injected below so the component is
 *  fully self-contained (no dependency on marketing.css for the tour).
 */
const TOUR_CSS = `
@keyframes cg-t-in { from { opacity: 0; transform: translateY(14px) scale(0.97); } to { opacity: 1; transform: none; } }
@keyframes cg-t-ap { from { opacity: 0; transform: translateY(7px); } to { opacity: 1; transform: none; } }
@keyframes cg-t-out { to { opacity: 0; } }
@keyframes cg-t-core { 0%,100% { box-shadow: 0 0 30px -10px rgba(59,130,246,0.6); transform: scale(1); } 50% { box-shadow: 0 0 52px -6px rgba(59,130,246,0.95); transform: scale(1.045); } }
@keyframes cg-t-slide { from { opacity: 0; transform: translateX(24px); } to { opacity: 1; transform: none; } }
@keyframes cg-t-p1 { 0% { left: 20%; opacity: 0; } 10% { opacity: 1; } 46% { left: 50%; opacity: 1; } 56% { left: 50%; opacity: 0; } 100% { left: 50%; opacity: 0; } }
@keyframes cg-t-p2 { 0% { left: 50%; opacity: 0; } 46% { left: 50%; opacity: 0; } 56% { opacity: 1; } 90% { left: 80%; opacity: 1; } 100% { left: 82%; opacity: 0; } }
@keyframes cg-t-hand { from { transform: translate(-50%,-100%) rotate(0deg); } to { transform: translate(-50%,-100%) rotate(360deg); } }
@keyframes cg-t-tap { 0%,100% { transform: scale(1); } 45% { transform: scale(0.8); } }
@keyframes cg-t-knob { to { transform: translateX(20px); } }
@keyframes cg-t-spin { to { transform: rotate(360deg); } }
@keyframes cg-t-pulse { 0%,100% { opacity: 0.5; } 50% { opacity: 1; } }
[data-tour][data-paused] [data-tscene] * { animation-play-state: paused !important; }
@media (max-width: 640px) {
  #cg-t-stage { height: 400px !important; }
  .cg-t-flow { grid-template-columns: 1fr !important; gap: 10px !important; }
  .cg-t-flow > div:nth-child(2) { display: none !important; }
}
`;

const TOUR_HTML = `<div id="cg-t-stage" style="position: relative; height: 372px; overflow: hidden; border-radius: 12px; background: radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.08), transparent 62%);">

    <!-- SCENE 0 · SIGN IN -->
    <div data-tscene="0" style="position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; padding: 26px;">
      <div style="width: 320px; max-width: 88%; padding: 22px; border-radius: 16px; border: 1px solid rgba(148,163,184,0.16); background: #0b1220; box-shadow: 0 24px 60px -30px #000; animation: cg-t-in 0.55s ease both;">
        <div style="display: flex; align-items: center; gap: 8px; justify-content: center;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent,#3b82f6)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4.5" r="2.5"></circle><path d="m10.2 6.3-3.9 3.9"></path><circle cx="4.5" cy="12" r="2.5"></circle><path d="M7 12h10"></path><circle cx="19.5" cy="12" r="2.5"></circle><circle cx="12" cy="19.5" r="2.5"></circle><path d="m13.8 17.7 3.9-3.9"></path></svg>
          <span style="font-weight: 700; font-size: 15px;">CommitGraph</span>
        </div>
        <h3 style="margin: 14px 0 3px; text-align: center; font-size: 18px; font-weight: 700;">Welcome back</h3>
        <p style="margin: 0 0 15px; text-align: center; font-size: 12px; color: #94a3b8;">Sign in to your workspace</p>
        <div style="padding: 10px 12px; border-radius: 9px; border: 1px solid rgba(148,163,184,0.18); background: #070b13; font-size: 12px; color: #64748b;">you@company.com</div>
        <div style="position: relative; margin-top: 10px;">
          <div style="display: flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 12px; border-radius: 9px; border: 1px solid rgba(148,163,184,0.22); background: #0e1626; font-size: 12.5px; font-weight: 600; color: #e2e8f0; animation: cg-t-out 0.35s ease 1.5s both;">
            <svg width="15" height="15" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6 1.5 7.4 2.7l5.5-5.4C33.6 3.6 29.3 2 24 2 14.6 2 6.4 7.8 2.9 16.1l6.9 5.3C11.5 14.9 17.2 9.5 24 9.5z"></path><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-2.8-.4-4H24v7.6h12.7c-.3 2-1.6 5-4.7 7l7.2 5.6c4.3-4 6.9-9.8 6.9-16.2z"></path><path fill="#FBBC05" d="M9.8 28.6c-.5-1.5-.8-3.1-.8-4.6s.3-3.1.8-4.6l-6.9-5.3C1.1 17.1 0 20.4 0 24s1.1 6.9 2.9 9.9l6.9-5.3z"></path><path fill="#34A853" d="M24 46c5.3 0 9.8-1.7 13-4.8l-7.2-5.6c-1.9 1.3-4.5 2.2-5.8 2.2-6.8 0-12.5-4.5-14.2-10.8l-6.9 5.3C6.4 40.2 14.6 46 24 46z"></path></svg>
            Continue with Google
          </div>
          <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 7px; border-radius: 9px; background: rgba(6,78,59,0.5); border: 1px solid rgba(52,211,153,0.4); color: #6ee7b7; font-size: 12.5px; font-weight: 600; opacity: 0; animation: cg-t-ap 0.35s ease 1.7s both;">✓ Signed in</div>
          <div style="position: absolute; left: 62%; top: 44%; animation: cg-t-tap 1s ease 0.8s both; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));">
            <svg width="20" height="20" viewBox="0 0 24 24"><path d="M4 2 L4 18 L8.5 14 L11.5 20.5 L14 19.3 L10.8 13 L17 13 Z" fill="#fff" stroke="#0b1220" stroke-width="1.2" stroke-linejoin="round"></path></svg>
          </div>
        </div>
      </div>
      <div style="position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; font-size: 12.5px; color: #94a3b8; padding: 0 24px; line-height: 1.5;"><b style="color: var(--accent,#3b82f6);">Step 1 · Sign in.</b> Multi-tenant — your data stays isolated and yours.</div>
    </div>

    <!-- SCENE 1 · CONNECT -->
    <div data-tscene="1" style="position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; padding: 26px;">
      <div style="width: 400px; max-width: 92%; display: flex; flex-direction: column; gap: 9px;">
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: 1.5px; color: var(--accent,#3b82f6); margin-bottom: 2px;">CONNECT YOUR CHANNELS</div>
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; border-radius: 11px; border: 1px solid rgba(148,163,184,0.16); background: #0b1220; animation: cg-t-in 0.45s ease 0.2s both;">
          <div style="display: flex; align-items: center; gap: 10px;"><span style="width: 8px; height: 8px; border-radius: 999px; background: #ea4335;"></span><span style="font-weight: 600; font-size: 13px;">Gmail</span></div>
          <div style="position: relative; width: 110px; height: 28px;">
            <span style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; border-radius: 999px; border: 1px solid rgba(148,163,184,0.28); font-size: 11.5px; color: #cbd5e1; animation: cg-t-out 0.3s ease 0.8s both;">Connect</span>
            <span style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; border-radius: 999px; background: rgba(6,78,59,0.5); border: 1px solid rgba(52,211,153,0.4); color: #6ee7b7; font-size: 11.5px; font-weight: 600; opacity: 0; animation: cg-t-ap 0.4s ease 0.8s both;">Connected ✓</span>
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; border-radius: 11px; border: 1px solid rgba(148,163,184,0.16); background: #0b1220; animation: cg-t-in 0.45s ease 0.35s both;">
          <div style="display: flex; align-items: center; gap: 10px;"><span style="width: 8px; height: 8px; border-radius: 999px; background: #0a84ff;"></span><span style="font-weight: 600; font-size: 13px;">Outlook</span></div>
          <div style="position: relative; width: 110px; height: 28px;">
            <span style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; border-radius: 999px; border: 1px solid rgba(148,163,184,0.28); font-size: 11.5px; color: #cbd5e1; animation: cg-t-out 0.3s ease 1.4s both;">Connect</span>
            <span style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; border-radius: 999px; background: rgba(6,78,59,0.5); border: 1px solid rgba(52,211,153,0.4); color: #6ee7b7; font-size: 11.5px; font-weight: 600; opacity: 0; animation: cg-t-ap 0.4s ease 1.4s both;">Connected ✓</span>
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; border-radius: 11px; border: 1px solid rgba(148,163,184,0.16); background: #0b1220; animation: cg-t-in 0.45s ease 0.5s both;">
          <div style="display: flex; align-items: center; gap: 10px;"><span style="width: 8px; height: 8px; border-radius: 999px; background: #a855f7;"></span><span style="font-weight: 600; font-size: 13px;">Slack</span></div>
          <div style="position: relative; width: 110px; height: 28px;">
            <span style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; border-radius: 999px; border: 1px solid rgba(148,163,184,0.28); font-size: 11.5px; color: #cbd5e1; animation: cg-t-out 0.3s ease 2s both;">Connect</span>
            <span style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; border-radius: 999px; background: rgba(6,78,59,0.5); border: 1px solid rgba(52,211,153,0.4); color: #6ee7b7; font-size: 11.5px; font-weight: 600; opacity: 0; animation: cg-t-ap 0.4s ease 2s both;">Connected ✓</span>
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; border-radius: 11px; border: 1px solid rgba(59,130,246,0.25); background: rgba(30,58,138,0.12); animation: cg-t-in 0.45s ease 0.65s both; margin-top: 3px;">
          <div style="display: flex; align-items: center; gap: 10px;"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4M8 2v4M3 10h18"></path></svg><span style="font-weight: 600; font-size: 13px;">Google Calendar sync</span></div>
          <div style="position: relative; width: 44px; height: 24px; border-radius: 999px; background: rgba(100,116,139,0.4);">
            <div style="position: absolute; inset: 0; border-radius: 999px; background: #059669; opacity: 0; animation: cg-t-ap 0.4s ease 2.5s both;"></div>
            <div style="position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 999px; background: #fff; animation: cg-t-knob 0.4s ease 2.5s both;"></div>
          </div>
        </div>
      </div>
      <div style="position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; font-size: 12.5px; color: #94a3b8; padding: 0 24px; line-height: 1.5;"><b style="color: var(--accent,#3b82f6);">Step 2 · Connect.</b> Link Gmail, Outlook &amp; Slack, then switch on calendar sync.</div>
    </div>

    <!-- SCENE 2 · COMMITMENTS -->
    <div data-tscene="2" style="position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; padding: 22px;">
      <div class="cg-t-flow" style="position: relative; width: 100%; max-width: 820px; display: grid; grid-template-columns: 1fr 132px 1.25fr; align-items: center; gap: 14px;">
        <div style="display: flex; flex-direction: column; gap: 9px;">
          <div style="padding: 9px 11px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.18); background: #0b1220; animation: cg-t-in 0.45s ease 0.1s both;"><div style="display: flex; align-items: center; gap: 7px;"><span style="width: 7px; height: 7px; border-radius: 999px; background: #ea4335;"></span><span style="font-size: 11.5px; font-weight: 600;">Gmail</span></div><div style="margin-top: 4px; font-size: 10.5px; color: #94a3b8;">"I'll send the Q3 forecast by Fri"</div></div>
          <div style="padding: 9px 11px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.18); background: #0b1220; animation: cg-t-in 0.45s ease 0.3s both;"><div style="display: flex; align-items: center; gap: 7px;"><span style="width: 7px; height: 7px; border-radius: 999px; background: #0a84ff;"></span><span style="font-size: 11.5px; font-weight: 600;">Outlook</span></div><div style="margin-top: 4px; font-size: 10.5px; color: #94a3b8;">"Can you review the redlines?"</div></div>
          <div style="padding: 9px 11px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.18); background: #0b1220; animation: cg-t-in 0.45s ease 0.5s both;"><div style="display: flex; align-items: center; gap: 7px;"><span style="width: 7px; height: 7px; border-radius: 999px; background: #a855f7;"></span><span style="font-size: 11.5px; font-weight: 600;">Slack</span></div><div style="margin-top: 4px; font-size: 10.5px; color: #94a3b8;">"deck to Sam sometime next wk"</div></div>
        </div>
        <div style="justify-self: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; width: 128px; height: 128px; border-radius: 26px; border: 1px solid rgba(59,130,246,0.5); background: radial-gradient(circle at 50% 40%, rgba(59,130,246,0.2), rgba(13,21,38,0.9)); animation: cg-t-core 2.4s ease-in-out infinite;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"></path><rect x="4" y="8" width="16" height="12" rx="2"></rect><path d="M2 14h2M20 14h2M15 13v2M9 13v2"></path></svg>
          <span style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: #93c5fd;">AI Agent</span>
          <span style="font-size: 8.5px; color: #64748b; text-align: center; font-family: 'JetBrains Mono', monospace;">reads · reasons · acts</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 7px;">
          <div style="padding: 10px 12px; border-radius: 11px; border: 1px solid rgba(52,211,153,0.3); background: rgba(6,78,59,0.14); animation: cg-t-slide 0.45s ease 1.1s both;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 7px;"><span style="font-size: 12px; font-weight: 600;">Send Q3 forecast → Babitha</span><span style="font-size: 9.5px; padding: 2px 6px; border-radius: 999px; background: rgba(6,78,59,0.6); color: #6ee7b7; font-weight: 600;">92%</span></div>
            <div style="margin-top: 3px; font-size: 10.5px; color: #94a3b8;">You owe · due Wed, Jul 22</div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; padding: 9px 11px; border-radius: 10px; border: 1px solid rgba(59,130,246,0.3); background: rgba(30,58,138,0.18); font-size: 11px; color: #dbeafe; animation: cg-t-slide 0.45s ease 1.5s both;"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4M8 2v4M3 10h18"></path></svg> Calendar · Wed, Jul 22 · 5:00 PM</div>
          <div style="padding: 10px 12px; border-radius: 10px; border: 1px dashed rgba(251,191,36,0.45); background: rgba(120,53,15,0.14); animation: cg-t-slide 0.45s ease 2.1s both;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 7px;"><span style="font-size: 11px; font-weight: 600; color: #fcd34d;">↳ Human review</span><span style="font-size: 9.5px; padding: 2px 6px; border-radius: 999px; background: rgba(120,53,15,0.6); color: #fcd34d; font-weight: 600;">62%</span></div>
            <div style="margin-top: 3px; font-size: 10.5px; color: #94a3b8;">"deck sometime next week" · confirm?</div>
          </div>
        </div>
        <div style="position: absolute; inset: 0; pointer-events: none;">
          <span style="position: absolute; top: 20%; width: 7px; height: 7px; border-radius: 999px; background: #ea4335; box-shadow: 0 0 9px #ea4335; animation: cg-t-p1 2.4s ease-in-out 0s infinite;"></span>
          <span style="position: absolute; top: 50%; width: 7px; height: 7px; border-radius: 999px; background: #0a84ff; box-shadow: 0 0 9px #0a84ff; animation: cg-t-p1 2.4s ease-in-out 0.5s infinite;"></span>
          <span style="position: absolute; top: 80%; width: 7px; height: 7px; border-radius: 999px; background: #a855f7; box-shadow: 0 0 9px #a855f7; animation: cg-t-p1 2.4s ease-in-out 1s infinite;"></span>
          <span style="position: absolute; top: 28%; width: 7px; height: 7px; border-radius: 999px; background: #2dd4bf; box-shadow: 0 0 9px #2dd4bf; animation: cg-t-p2 2.4s ease-in-out 1.2s infinite;"></span>
          <span style="position: absolute; top: 72%; width: 7px; height: 7px; border-radius: 999px; background: #fbbf24; box-shadow: 0 0 9px #fbbf24; animation: cg-t-p2 2.4s ease-in-out 1.6s infinite;"></span>
        </div>
      </div>
      <div style="position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; font-size: 12.5px; color: #94a3b8; padding: 0 24px; line-height: 1.5;"><b style="color: var(--accent,#3b82f6);">Step 3 · Commitments.</b> Messages become commitments, calendar-synced — low-confidence goes to human review.</div>
    </div>

    <!-- SCENE 3 · JOBS -->
    <div data-tscene="3" style="position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; padding: 22px;">
      <div class="cg-t-flow" style="position: relative; width: 100%; max-width: 820px; display: grid; grid-template-columns: 1fr 132px 1.25fr; align-items: center; gap: 14px;">
        <div style="display: flex; flex-direction: column; gap: 9px;">
          <div style="padding: 9px 11px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.18); background: #0b1220; animation: cg-t-in 0.45s ease 0.1s both;"><div style="display: flex; align-items: center; gap: 7px;"><span style="width: 7px; height: 7px; border-radius: 999px; background: #ea4335;"></span><span style="font-size: 11.5px; font-weight: 600;">Gmail</span></div><div style="margin-top: 4px; font-size: 10.5px; color: #94a3b8;">"Stripe: invitation to interview"</div></div>
          <div style="padding: 9px 11px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.18); background: #0b1220; animation: cg-t-in 0.45s ease 0.35s both;"><div style="display: flex; align-items: center; gap: 7px;"><span style="width: 7px; height: 7px; border-radius: 999px; background: #ea4335;"></span><span style="font-size: 11.5px; font-weight: 600;">Gmail · fwd</span></div><div style="margin-top: 4px; font-size: 10.5px; color: #94a3b8;">"Re: your application — Stripe"</div></div>
        </div>
        <div style="justify-self: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; width: 128px; height: 128px; border-radius: 26px; border: 1px solid rgba(59,130,246,0.5); background: radial-gradient(circle at 50% 40%, rgba(59,130,246,0.2), rgba(13,21,38,0.9)); animation: cg-t-core 2.4s ease-in-out infinite;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"></path><rect x="4" y="8" width="16" height="12" rx="2"></rect><path d="M2 14h2M20 14h2M15 13v2M9 13v2"></path></svg>
          <span style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: #93c5fd;">AI Agent</span>
          <span style="font-size: 8.5px; color: #64748b; text-align: center; font-family: 'JetBrains Mono', monospace;">same agent</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 7px;">
          <div style="padding: 11px 13px; border-radius: 11px; border: 1px solid rgba(148,163,184,0.18); background: #0b1220; animation: cg-t-slide 0.45s ease 1.1s both;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 7px;"><span style="font-size: 12.5px; font-weight: 600;">Stripe — Senior SWE</span><span style="font-size: 9.5px; padding: 2px 6px; border-radius: 999px; background: rgba(30,58,138,0.5); color: #93c5fd; font-weight: 600;">interview</span></div>
            <div style="display: flex; align-items: center; gap: 4px; margin-top: 10px; flex-wrap: wrap;">
              <span style="font-size: 9px; padding: 3px 7px; border-radius: 999px; background: rgba(30,58,138,0.4); color: #93c5fd;">applied</span>
              <span style="color: #475569; font-size: 10px;">›</span>
              <span style="font-size: 9px; padding: 3px 7px; border-radius: 999px; background: rgba(30,58,138,0.4); color: #93c5fd;">screen</span>
              <span style="color: #475569; font-size: 10px;">›</span>
              <span style="font-size: 9px; padding: 3px 7px; border-radius: 999px; border: 1px solid var(--accent,#3b82f6); color: #dbeafe; font-weight: 600; animation: cg-t-pulse 1.6s ease 1.6s infinite;">interview</span>
              <span style="color: #475569; font-size: 10px;">›</span>
              <span style="font-size: 9px; padding: 3px 7px; border-radius: 999px; background: rgba(51,65,85,0.4); color: #64748b;">offer</span>
            </div>
          </div>
          <div style="font-size: 10.5px; color: #64748b; padding-left: 3px; animation: cg-t-slide 0.45s ease 1.7s both;">↳ 2 forwarded threads merged into one timeline</div>
        </div>
        <div style="position: absolute; inset: 0; pointer-events: none;">
          <span style="position: absolute; top: 30%; width: 7px; height: 7px; border-radius: 999px; background: #ea4335; box-shadow: 0 0 9px #ea4335; animation: cg-t-p1 2.4s ease-in-out 0s infinite;"></span>
          <span style="position: absolute; top: 62%; width: 7px; height: 7px; border-radius: 999px; background: #ea4335; box-shadow: 0 0 9px #ea4335; animation: cg-t-p1 2.4s ease-in-out 0.6s infinite;"></span>
          <span style="position: absolute; top: 44%; width: 7px; height: 7px; border-radius: 999px; background: #60a5fa; box-shadow: 0 0 9px #60a5fa; animation: cg-t-p2 2.4s ease-in-out 1.2s infinite;"></span>
        </div>
      </div>
      <div style="position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; font-size: 12.5px; color: #94a3b8; padding: 0 24px; line-height: 1.5;"><b style="color: var(--accent,#3b82f6);">Step 4 · Job applications.</b> The same agent tracks every application's lifecycle on one merged timeline.</div>
    </div>

    <!-- SCENE 4 · DAILY BRIEF (morning + night) -->
    <div data-tscene="4" style="position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; padding: 22px;">
      <div class="cg-t-flow" style="position: relative; width: 100%; max-width: 820px; display: grid; grid-template-columns: 1fr 132px 1.25fr; align-items: center; gap: 14px;">
        <!-- scheduler -->
        <div style="justify-self: center; text-align: center; animation: cg-t-in 0.45s ease 0.1s both;">
          <div style="position: relative; width: 66px; height: 66px; border-radius: 999px; border: 2px solid rgba(148,163,184,0.4); margin: 0 auto;">
            <div style="position: absolute; left: 50%; top: 50%; width: 2px; height: 22px; background: var(--accent,#3b82f6); transform-origin: bottom center; transform: translate(-50%,-100%); animation: cg-t-hand 3s linear infinite;"></div>
            <div style="position: absolute; left: 50%; top: 50%; width: 6px; height: 6px; border-radius: 999px; background: var(--accent,#3b82f6); transform: translate(-50%,-50%);"></div>
          </div>
          <div style="margin-top: 9px; font-size: 11px; color: #94a3b8;">Scheduler</div>
          <div style="margin-top: 7px; display: flex; flex-direction: column; gap: 4px; font-size: 9.5px; color: #64748b; font-family: 'JetBrains Mono', monospace;">
            <span style="display: flex; align-items: center; gap: 5px; justify-content: center;"><span style="width: 6px; height: 6px; border-radius: 999px; background: #fbbf24;"></span>6:00 AM</span>
            <span style="display: flex; align-items: center; gap: 5px; justify-content: center;"><span style="width: 6px; height: 6px; border-radius: 999px; background: #818cf8;"></span>6:00 PM</span>
          </div>
        </div>
        <!-- agent + DB -->
        <div style="justify-self: center; display: flex; flex-direction: column; align-items: center; gap: 8px;">
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; width: 128px; height: 110px; border-radius: 26px; border: 1px solid rgba(59,130,246,0.5); background: radial-gradient(circle at 50% 40%, rgba(59,130,246,0.2), rgba(13,21,38,0.9)); animation: cg-t-core 2.4s ease-in-out infinite;">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"></path><rect x="4" y="8" width="16" height="12" rx="2"></rect><path d="M2 14h2M20 14h2M15 13v2M9 13v2"></path></svg>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: #93c5fd;">AI Agent</span>
            <span style="font-size: 8.5px; color: #64748b; text-align: center; font-family: 'JetBrains Mono', monospace;">summarizes</span>
          </div>
          <div style="display: flex; align-items: center; gap: 6px; opacity: 0.9;">
            <svg width="20" height="24" viewBox="0 0 72 82"><path d="M8 16 A28 10 0 0 0 64 16 L64 66 A28 10 0 0 1 8 66 Z" fill="#0b1220" stroke="rgba(148,163,184,0.24)"></path><ellipse cx="36" cy="16" rx="28" ry="10" fill="#0d1526" stroke="rgba(59,130,246,0.5)"></ellipse><path d="M8 40 A28 10 0 0 0 64 40" fill="none" stroke="rgba(148,163,184,0.14)"></path></svg>
            <span style="font-size: 9.5px; color: #64748b; font-family: 'JetBrains Mono', monospace;">reads PostgreSQL</span>
          </div>
        </div>
        <!-- briefs -->
        <div style="display: flex; flex-direction: column; gap: 9px;">
          <div style="position: relative; overflow: hidden; padding: 11px 13px; border-radius: 12px; border: 1px solid rgba(251,191,36,0.28); background: linear-gradient(135deg, rgba(251,191,36,0.13), rgba(255,255,255,0.01)); animation: cg-t-in 0.45s ease 0.6s both;">
            <svg width="50" height="50" viewBox="0 0 24 24" style="position: absolute; right: -8px; top: -8px; opacity: 0.5; animation: cg-t-spin 16s linear infinite;"><g stroke="#fbbf24" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="4" fill="#fbbf24" stroke="none"></circle><line x1="12" y1="2" x2="12" y2="4.5"></line><line x1="12" y1="19.5" x2="12" y2="22"></line><line x1="2" y1="12" x2="4.5" y2="12"></line><line x1="19.5" y1="12" x2="22" y2="12"></line><line x1="4.9" y1="4.9" x2="6.7" y2="6.7"></line><line x1="17.3" y1="17.3" x2="19.1" y2="19.1"></line><line x1="4.9" y1="19.1" x2="6.7" y2="17.3"></line><line x1="17.3" y1="6.7" x2="19.1" y2="4.9"></line></g></svg>
            <div style="position: relative; font-size: 12px; font-weight: 700; color: #fbbf24;">Morning Brief · 6:00 AM</div>
            <div style="position: relative; margin-top: 7px; display: flex; flex-direction: column; gap: 4px; font-size: 10.5px; color: #cbd5e1;">
              <div style="display: flex; gap: 7px; animation: cg-t-ap 0.4s ease 1.1s both;"><span style="color: #f87171;">●</span> 2 due today · 1 overdue</div>
              <div style="display: flex; gap: 7px; animation: cg-t-ap 0.4s ease 1.4s both;"><span style="color: #60a5fa;">●</span> Job update — Stripe → interview</div>
            </div>
          </div>
          <div style="position: relative; overflow: hidden; padding: 11px 13px; border-radius: 12px; border: 1px solid rgba(129,140,248,0.3); background: linear-gradient(135deg, rgba(79,70,229,0.18), rgba(2,6,23,0.25)); animation: cg-t-in 0.45s ease 1.5s both;">
            <svg width="42" height="42" viewBox="0 0 24 24" style="position: absolute; right: 2px; top: 2px; opacity: 0.7; animation: cg-t-pulse 3s ease infinite;"><path d="M20 14.5A8 8 0 1 1 11 4a6.5 6.5 0 0 0 9 10.5z" fill="#c7d2fe"></path></svg>
            <span style="position: absolute; right: 30px; top: 8px; width: 2px; height: 2px; border-radius: 999px; background: #e0e7ff;"></span>
            <span style="position: absolute; right: 46px; top: 16px; width: 2px; height: 2px; border-radius: 999px; background: #e0e7ff;"></span>
            <div style="position: relative; font-size: 12px; font-weight: 700; color: #c7d2fe;">Evening Brief · 6:00 PM</div>
            <div style="position: relative; margin-top: 7px; display: flex; flex-direction: column; gap: 4px; font-size: 10.5px; color: #cbd5e1;">
              <div style="display: flex; gap: 7px; animation: cg-t-ap 0.4s ease 2s both;"><span style="color: #34d399;">●</span> 3 follow-ups awaiting reply</div>
              <div style="display: flex; gap: 7px; animation: cg-t-ap 0.4s ease 2.3s both;"><span style="color: #fbbf24;">●</span> Tomorrow — 2 deadlines</div>
            </div>
          </div>
        </div>
        <div style="position: absolute; inset: 0; pointer-events: none;">
          <span style="position: absolute; top: 50%; width: 7px; height: 7px; border-radius: 999px; background: var(--accent,#3b82f6); box-shadow: 0 0 9px var(--accent,#3b82f6); animation: cg-t-p1 2.6s ease-in-out 0s infinite;"></span>
          <span style="position: absolute; top: 38%; width: 7px; height: 7px; border-radius: 999px; background: #fbbf24; box-shadow: 0 0 9px #fbbf24; animation: cg-t-p2 2.6s ease-in-out 1s infinite;"></span>
          <span style="position: absolute; top: 66%; width: 7px; height: 7px; border-radius: 999px; background: #818cf8; box-shadow: 0 0 9px #818cf8; animation: cg-t-p2 2.6s ease-in-out 1.5s infinite;"></span>
        </div>
      </div>
      <div style="position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; font-size: 12.5px; color: #94a3b8; padding: 0 24px; line-height: 1.5;"><b style="color: var(--accent,#3b82f6);">Step 5 · Daily brief.</b> A morning and an evening brief, auto-generated from your data — not your inbox.</div>
    </div>

    <!-- END CARD -->
    <div data-tend style="position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 26px; text-align: center; background: radial-gradient(ellipse at 50% 42%, rgba(59,130,246,0.12), transparent 66%);">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--accent,#3b82f6)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation: cg-t-in 0.5s ease both;"><circle cx="12" cy="4.5" r="2.5"></circle><path d="m10.2 6.3-3.9 3.9"></path><circle cx="4.5" cy="12" r="2.5"></circle><path d="M7 12h10"></path><circle cx="19.5" cy="12" r="2.5"></circle><circle cx="12" cy="19.5" r="2.5"></circle><path d="m13.8 17.7 3.9-3.9"></path></svg>
      <div style="font-size: 20px; font-weight: 700; animation: cg-t-in 0.5s ease 0.08s both;">That's CommitGraph</div>
      <div style="font-size: 12.5px; color: #94a3b8; max-width: 380px; line-height: 1.55; animation: cg-t-in 0.5s ease 0.16s both;">Sign in, connect your channels, and let the agent turn every message into tracked commitments, jobs and briefs.</div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 4px; animation: cg-t-in 0.5s ease 0.24s both;">
        <button data-treplay style="display: inline-flex; align-items: center; gap: 7px; padding: 10px 18px; font-size: 13px; font-weight: 600; color: #e2e8f0; border-radius: 10px; border: 1px solid rgba(148,163,184,0.28); background: transparent; cursor: pointer;">↻ Replay</button>
        <a href="https://commitgraph-tau.vercel.app" target="_blank" style="padding: 10px 18px; font-size: 13px; font-weight: 600; color: #fff; border-radius: 10px; background: var(--accent,#3b82f6); box-shadow: 0 8px 22px -8px rgba(59,130,246,0.7);">Open the live app →</a>
      </div>
    </div>
  </div>

  <!-- progress -->
  <div style="height: 3px; width: 100%; background: rgba(148,163,184,0.12); border-radius: 999px; margin-top: 10px; overflow: hidden;"><div id="cg-t-fill" style="height: 100%; width: 0; background: var(--accent,#3b82f6);"></div></div>

  <!-- dots -->
  <div style="display: flex; align-items: center; justify-content: center; gap: 7px; margin-top: 12px;">
    <span data-tdot="0" data-tgo="0" title="Sign in" style="width: 24px; height: 7px; border-radius: 999px; background: var(--accent,#3b82f6); cursor: pointer; transition: width 0.3s ease, background 0.3s ease;"></span>
    <span data-tdot="1" data-tgo="1" title="Connect" style="width: 7px; height: 7px; border-radius: 999px; background: rgba(148,163,184,0.3); cursor: pointer; transition: width 0.3s ease, background 0.3s ease;"></span>
    <span data-tdot="2" data-tgo="2" title="Commitments" style="width: 7px; height: 7px; border-radius: 999px; background: rgba(148,163,184,0.3); cursor: pointer; transition: width 0.3s ease, background 0.3s ease;"></span>
    <span data-tdot="3" data-tgo="3" title="Jobs" style="width: 7px; height: 7px; border-radius: 999px; background: rgba(148,163,184,0.3); cursor: pointer; transition: width 0.3s ease, background 0.3s ease;"></span>
    <span data-tdot="4" data-tgo="4" title="Daily brief" style="width: 7px; height: 7px; border-radius: 999px; background: rgba(148,163,184,0.3); cursor: pointer; transition: width 0.3s ease, background 0.3s ease;"></span>
  </div>`;

export default function Tour() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const dur = [3000, 3600, 4400, 3800, 4600];
    let n = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const bar = () => root.querySelector<HTMLDivElement>("#cg-t-fill");

    const startProgress = () => {
      const b = bar();
      const d = dur[n];
      if (b) {
        b.style.transition = "none";
        b.style.width = "0%";
        void b.offsetWidth;
        b.style.transition = "width " + d + "ms linear";
        b.style.width = "100%";
      }
      if (timer) clearTimeout(timer);
      timer = setTimeout(advance, d);
    };

    const showScene = (i: number) => {
      n = i;
      const end = root.querySelector<HTMLElement>("[data-tend]");
      if (end) end.style.display = "none";
      root.querySelectorAll<HTMLElement>("[data-tscene]").forEach((s) => {
        const on = Number(s.getAttribute("data-tscene")) === i;
        if (on) { s.style.display = "none"; void s.offsetWidth; s.style.display = "flex"; }
        else s.style.display = "none";
      });
      root.querySelectorAll<HTMLElement>("[data-tdot]").forEach((d) => {
        const on = Number(d.getAttribute("data-tdot")) === i;
        d.style.background = on ? "var(--accent,#3b82f6)" : "rgba(148,163,184,0.3)";
        d.style.width = on ? "24px" : "7px";
      });
      startProgress();
    };

    const advance = () => { if (n < dur.length - 1) showScene(n + 1); else finish(); };

    const finish = () => {
      if (timer) clearTimeout(timer);
      root.querySelectorAll<HTMLElement>("[data-tscene]").forEach((s) => { s.style.display = "none"; });
      const b = bar();
      if (b) { b.style.transition = "none"; b.style.width = "100%"; }
      const end = root.querySelector<HTMLElement>("[data-tend]");
      if (end) { end.style.display = "none"; void end.offsetWidth; end.style.display = "flex"; }
      timer = setTimeout(() => showScene(0), 5000);
    };

    root.querySelectorAll<HTMLElement>("[data-tgo]").forEach((d) =>
      d.addEventListener("click", () => showScene(Number(d.getAttribute("data-tgo")))));
    root.querySelectorAll<HTMLElement>("[data-treplay]").forEach((b) =>
      b.addEventListener("click", () => showScene(0)));
    const onReplay = () => showScene(0);
    window.addEventListener("cg-tour-replay", onReplay);

    showScene(0);
    return () => { if (timer) clearTimeout(timer); window.removeEventListener("cg-tour-replay", onReplay); };
  }, []);

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: TOUR_CSS }} />
      <div data-tour ref={ref} style={{ width: "100%" }} dangerouslySetInnerHTML={{ __html: TOUR_HTML }} />
    </>
  );
}
