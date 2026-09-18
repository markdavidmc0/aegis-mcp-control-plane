# Aegis Cloud Edge Guard & Web Ingress Management: UX & Interaction Specification

- **Target Persona:** Cloud Platform Engineers, Security Administrators, and AI Operations Engineers.
- **Upstream Author:** `@ux-designer`
- **Downstream Implementer:** `@frontend-dev` (`apps/web/`)
- **Compliance Standard:** WCAG 2.2 Level AA
- **Status:** Baseline Approved Specification

---

## 1. Executive Layout Topology & Component Hierarchy

The Edge Guard & Ingress interface provides real-time visibility, telemetry streaming, and enforcement policy administration across edge proxies, gVisor sandboxes, and Open Policy Agent (OPA) gates.

```
+----------------------------------------------------------------------------------------------------+
| Global Ingress Header (Live Gateway Status, Active Region, Auth Profile, Global Telemetry Link)    |
+------------------------------------+---------------------------------------------------------------+
| Nav / Workload Context Selector    | Control Action Bar (Deploy Policy, Refresh Tokens, Cascade)  |
| - Edge Ingress Clusters            +---------------------------------------------------------------+
| - Sandbox Fleet (gVisor)           | Active Session Telemetry Ribbon                               |
| - Token & WIF Status               | [PKCE: Valid] [Token Exp: 12m] [WIF: Synchronized] [Logfire] |
+------------------------------------+---------------------------------------------------------------+
| Main Stage: Multi-Panel Grid                                                                       |
| +---------------------------------------------------+--------------------------------------------+ |
| | Panel A: Edge Stream & Tool Execution Console     | Panel B: Ingress Security & Policy Guard   | |
| | - Virtualized Span & Event Stream                 | - Dynamic OPA Gate Verdicts                | |
| | - Standard Out / Telemetry Buffers                | - Active Rule Inspector                    | |
| | - Logfire Trace Correlation Anchors               | - Violation Override Drawer Triggers       | |
| +---------------------------------------------------+--------------------------------------------+ |
| | Panel C: Failover Cascades & Health Topology      | Panel D: Ingress Audit & Remediation Log   | |
| | - gVisor Sandboxes (Primary / Secondary Nodes)    | - Structured JSON-RPC Diagnostics          | |
| | - Regional Upstream Latency Gauges                | - One-Click Error Reproduction Action      | |
| +---------------------------------------------------+--------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
| Global Status Footer (Live Stream Polling/SSE Status, WebSocket Heartbeat, Accessibility Mode)     |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Interaction State Matrices

### 2.1 State Transition Matrix

| Interaction State | Visual Indicator & Blueprint | Trigger / Event | Action Buttons & Interactivity | Recovery / Next Transition |
| :--- | :--- | :--- | :--- | :--- |
| **1. Idle / Pristine** | Stable neutral surfaces. Muted border dividers (`border-slate-800`). Telemetry status badge: Solid Green dot `Operational`. | Route mount or post-synchronization quiescence. | All control inputs enabled (Run Tool, Rotate WIF, Re-evaluate Policy). | Waits for user trigger, scheduled background heartbeat, or incoming stream. |
| **2. Authenticating / PKCE Redirect** | High-contrast indeterminate progress rail at top viewport (`h-1 bg-cyan-500 animate-pulse`). Main viewport displays skeleton cards with shimmer effect (`motion-reduce:none`). | Unauthenticated session or manual "Re-authenticate with OAuth/OIDC" trigger. | All interactive inputs disabled (`disabled`, `aria-busy="true"`). An explicit "Cancel Redirect" secondary button is accessible via Tab. | Automatically redirects browser to OAuth Identity Provider or opens PKCE callback pop-up window. |
| **3. Token Refresh (Silent Background)** | Micro-badge indicator adjacent to user profile: Spinning circular indicator (`w-3 h-3 text-cyan-400`). Main UI remains responsive without layout shift. | Token TTL <= 120s or 401 Unauthorized interceptor. | Unobtrusive: No interaction lock. Action triggers queue optimistic mutations with a 3-second timeout buffer. | Transitions to `Idle` on success (`200 OK`) or `Error: JWT Expired` on failure (`401/403`). |
| **4. Tool Execution Streaming** | Console panel shows live monospace terminal feed. Active step glows cyan; completed spans show checkmarks (`text-emerald-400`). Logfire trace chip dynamically updates with duration counter (e.g., `+342ms`). | User triggers tool execution (JSON-RPC `tools/call`) or agent pipeline step. | Main action toggles to "Halt Execution" (`variant="destructive"`). Secondary actions disabled. Terminal scroll auto-locks to bottom; user scrolling pauses lock. | Reaches `Completed` (status 200), `Policy Rejection -32000`, or `gVisor Timeout`. |
| **5. Policy Rejection (`-32000`)** | Border transitions to solid Amber-Red (`border-rose-500/80 bg-rose-950/20`). Flash alert banner appears with rule tag (e.g., `opa:deny_untrusted_egress`). | Tool invocation blocked by OPA/Rego gate emitting JSON-RPC error `-32000`. | "View Audit Decision", "Request Security Override", and "Dismiss Banner" buttons enabled. Primary execution button returns to enabled. | User alters parameters, requests elevation, or dismisses notification. |
| **6. Failover Cascade** | Warning banner across ingress header (`bg-amber-500/15 border-amber-500 text-amber-200`). Visual route topology diagram animates fallback path: `Primary (Stalled) -> Secondary (Routing)`. | Primary edge node/gVisor sandbox ping failure > 3 consecutive intervals (or HTTP 502/504). | "Force Switchover", "Isolate Sandbox Node", and "Pause Ingress Traffic" available. | Auto-resolves once secondary node health check confirms nominal throughput. |

---

## 3. Human-Centered UX Copy & Error States

All error interfaces must follow constructive communication: state what happened without technical blame, declare current system/data status, and provide an unambiguous next step.

```
+----------------------------------------------------------------------------------------------------+
| [ICON: Alert Circle]  [Headline: Clear, Affirmative Tone]                                          |
| Description: Exactly what occurred, state of pending operations or uncommitted changes.             |
| Technical Fingerprint: [Code: ERR_CODE] [Trace ID: 019c337...] [Timestamp: 2026-09-18T14:22:01Z]  |
|                                                                                                    |
| [Primary Action (Immediate Resolution)]      [Secondary Action (Investigate / Fallback)]           |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Error Copy Inventory

#### State A: JWT Expired / OAuth Session Terminated
- **Banner Headline:** "Authentication session expired"
- **Body Content:** "Your edge management session timed out to safeguard cloud infrastructure credentials. Any unsubmitted policy configurations have been preserved locally in draft storage."
- **Metadata String:** `Code: AUTH_SESSION_EXPIRED (HTTP 401)` • `Target: Aegis Edge Gateway`
- **Primary CTA:** `Log In with Identity Provider`
- **Secondary CTA:** `Save Draft Configuration Locally`

#### State B: OPA Policy Violation (`JSON-RPC -32000`)
- **Banner Headline:** "Operation blocked by edge policy guard"
- **Body Content:** "The requested tool invocation violated security rule `rego/ingress_sandbox_strict`. Outbound socket communication to unsanctioned CIDR ranges (`10.240.0.0/16`) is prohibited from gVisor execution units."
- **Metadata String:** `JSON-RPC Code: -32000 (Policy Denial)` • `Engine: OPA v0.68.0` • `Evaluated Rule: sandbox.network.egress`
- **Primary CTA:** `Inspect Policy Decision in Rego Console`
- **Secondary CTA:** `Request Single-Execution Waiver`

#### State C: gVisor Sandbox Execution Timeout
- **Banner Headline:** "Sandbox execution timed out"
- **Body Content:** "The gVisor runsc sandbox did not return execution telemetry within the configured 30,000ms deadline. The isolation container was gracefully terminated to prevent resource starvation. No edge memory leaks detected."
- **Metadata String:** `Sandbox ID: gvisor-worker-08b` • `Signal: SIGKILL (TimeoutExceeded)` • `Duration: 30,001ms`
- **Primary CTA:** `Retry in Clean Sandbox`
- **Secondary CTA:** `Examine Core Dump Spans`

#### State D: Workload Identity Federation (WIF) Rotation Error
- **Banner Headline:** "Cloud credential synchronization failed"
- **Body Content:** "The Edge Guard could not exchange the local workload token with the cloud Security Token Service (STS). External cloud provider calls are temporarily routed through cached fallback credentials (valid for 8 minutes)."
- **Metadata String:** `Provider: GCP/AWS STS Federation` • `Error: STS_TOKEN_EXCHANGE_REFUSED` • `HTTP: 503 Service Unavailable`
- **Primary CTA:** `Force WIF Re-handshake`
- **Secondary CTA:** `Switch to Static Backup Vault`

---

## 4. Accessibility Specification (WCAG 2.2 AA Compliance)

### 4.1 Focus Topology & Focus Trapping

1. **Focus Ring Geometry:**
   - Every interactive element (buttons, tabs, inputs, accordion toggles, trace links) must present an unambiguous visual focus indicator.
   - Styling: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950`.
   - Contrast: The cyan indicator (`#22d3ee`) against the dark background (`#020617`) delivers a contrast ratio of **11.4:1**, exceeding the WCAG 2.2 AA non-text contrast minimum of 3:1.

2. **Modal & Drawer Focus Trapping:**
   - When the "Security Override Drawer" or "Policy Evaluation Modal" opens:
     - Initial focus moves immediately to the first actionable element (or Close button).
     - Standard `Tab` and `Shift+Tab` cycling is trapped strictly within the container boundary (`aria-modal="true"`, `role="dialog"`).
     - Background content receives `aria-hidden="true"`.
     - Pressing `Escape` closes the overlay and returns focus deterministically to the triggering button.

3. **Console Terminal Focus & Scroll Management:**
   - The streaming execution console possesses `tabindex="0"`, `role="region"`, and `aria-label="Real-time tool execution output"`.
   - Keyboard users can enter the console via `Tab`, use `Up`/`Down` arrows or `PageUp`/`PageDown` to review virtualized lines without triggering whole-page scroll jumpiness.

### 4.2 Keyboard Navigation Contract

| Component Context | Keystroke | Deterministic Action |
| :--- | :--- | :--- |
| **Global Page** | `?` | Opens Keyboard Shortcuts Cheat Sheet modal. |
| **Global Page** | `Alt + E` / `Option + E` | Jumps focus directly to the Active Tool Execution stream. |
| **Global Page** | `Alt + P` / `Option + P` | Jumps focus directly to the Ingress Policy Guard panel. |
| **Tab Navigation Rails** | `ArrowRight` / `ArrowLeft` | Moves active tab selection horizontally; wraps around. |
| **Tab Navigation Rails** | `Home` / `End` | Jumps to the first or last tab immediately. |
| **Streaming Console** | `Spacebar` (while focused) | Toggles autoscroll pin/unpin lock. |
| **Trace Correlation Link** | `Enter` / `Space` | Activates external handoff to Logfire UI in a new tab. |
| **Drawer / Modal Overlays** | `Escape` | Closes overlay, dismisses pending confirmation, resets focus. |

### 4.3 Screen-Reader & ARIA Live Region Architecture

To prevent screen-reader churn during rapid event streaming, live announcements are decoupled into dedicated polite and assertive channels.

```html
<!-- Live Tool Execution Stream Announcer -->
<!-- Only announces phase completions or major status milestones, NOT raw stdout chunks -->
<div 
  id="aegis-stream-status"
  class="sr-only" 
  role="status" 
  aria-live="polite" 
  aria-atomic="true">
  <!-- Dynamic Injection Example: "Tool execution step 2 of 4 started: Sandboxed container warmup" -->
</div>

<!-- Critical Guard Alerts & Policy Rejections -->
<div 
  id="aegis-critical-alerts"
  class="sr-only" 
  role="alert" 
  aria-live="assertive" 
  aria-atomic="true">
  <!-- Dynamic Injection Example: "Critical error: OPA Policy violation. Tool execution blocked under rule deny_untrusted_egress." -->
</div>
```

### 4.4 Logfire Trace Handoff Link Specification

Telemetry traces link directly out to Pydantic Logfire. Screen readers must understand external destination, new-window behavior, and correlation IDs without visual ambiguity.

```html
<a 
  href="https://logfire.pydantic.dev/org/project/traces?trace_id=019c337145729a1f848bfb66cb1c5ad3" 
  target="_blank" 
  rel="noopener noreferrer"
  class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-medium rounded-md bg-slate-900 text-cyan-300 border border-cyan-800/60 hover:bg-slate-800 hover:border-cyan-500 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 transition-colors"
  aria-label="View Logfire trace 019c3371 in new window">
  <span aria-hidden="true" class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
  <span>trace:019c3371</span>
  <!-- Accessible External Link Icon -->
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    class="w-3.5 h-3.5 text-slate-400" 
    fill="none" 
    viewBox="0 0 24 24" 
    stroke="currentColor" 
    aria-hidden="true">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
  </svg>
  <span class="sr-only">(opens in new window)</span>
</a>
```

---

## 5. Edge-Case Matrix & Defensive Usability Policies

1. **Rapid Re-Clicking / Debounce Policy:**
   - All mutation buttons (e.g., "Rotate WIF Credentials", "Trigger Tool Execution", "Force Node Switchover") enforce a strict **600ms client-side debounce** and immediate transition to `aria-busy="true"`.
   - Secondary clicks during transit are suppressed with zero sound/layout churn.

2. **Ultra-Long Diagnostic Strings & JSON Payloads:**
   - Stack traces, OPA Rego AST outputs, and JSON-RPC payloads must not cause horizontal layout blowout.
   - Text containers implement `font-mono text-xs break-all max-h-64 overflow-y-auto`.
   - Tooltips for truncated IDs (e.g., 64-character SHA or 32-character trace IDs) must be accessible via keyboard focus (`role="tooltip"` triggered on `focus-visible`).

3. **Intermittent Network Disconnect (Offline / Reconnect):**
   - If SSE or WebSocket stream drops, the interface displays an ambient sticky status chip:
     `"Telemetry stream paused. Attempting reconnection (attempt 2 of 5)..."`
   - UI controls retain their last verified state; mutation actions are disabled with the tooltip: "Action disabled while offline".

4. **Reduced Motion Adaptation (`prefers-reduced-motion: reduce`):**
   - Pulse animations on trace badges and progress bars are immediately replaced with high-contrast static colors (`animate-none`).
   - Drawers and dialog transitions switch from slide/spring transforms to instantaneous alpha cut-ins (`transition-none`).

---

## 6. Implementation Checklist for `@frontend-dev`

- [ ] Implement focus ring tokens: `focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950`.
- [ ] Implement dual screen-reader announcers (`#aegis-stream-status` with `aria-live="polite"` and `#aegis-critical-alerts` with `aria-live="assertive"`).
- [ ] Connect Logfire trace chip using the exact markup structure and `(opens in new window)` sr-only announcement.
- [ ] Implement 600ms debounce on execution and credential rotation CTA triggers.
- [ ] Embed the exact human-centered error copy strings in the JSON-RPC error boundary handlers.
- [ ] Verify keyboard trap in OPA Policy Override Drawer via `Tab` / `Shift+Tab` and `Escape`.
- [ ] Validate color contrast ratios with axe-core / Lighthouse targeting WCAG 2.2 AA (>= 4.5:1 text, >= 3:1 non-text).
