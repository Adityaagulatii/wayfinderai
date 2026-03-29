import { useState, useRef, useEffect } from "react";

const API = "http://localhost:8002";

// ── Shared helpers ─────────────────────────────────────────────────────────────
const SCALE_X = 82, SCALE_Y = 72, OFFSET_X = 50, OFFSET_Y = 110;
const SVG_W = 1160, SVG_H = 600;
function toSVG(x, y) { return [x * SCALE_X + OFFSET_X, SVG_H - (y * SCALE_Y + OFFSET_Y)]; }

function nodeColor(id, name = "") {
  const n = name.toLowerCase();
  if (id === "entrance")  return "#f59e0b";
  if (id === "exit")      return "#ef4444";
  if (id === "checkout" || id.startsWith("checkout")) return "#8b5cf6";
  if (id === "100" || n.includes("dairy"))   return "#3b82f6";
  if (id === "101" || n.includes("meat"))    return "#ef4444";
  if (id === "152" || n.includes("bakery"))  return "#f97316";
  if (id === "34"  || n.includes("yogurt"))  return "#06b6d4";
  if (["105","351","352"].includes(id) || n.includes("produce") || n.includes("fruit") || n.includes("veg")) return "#22c55e";
  if (["8","40","42"].includes(id) || n.includes("frozen")) return "#67e8f9";
  if (id === "pharmacy")  return "#10b981";
  if (id === "cleaning")  return "#94a3b8";
  if (id === "vitamins")  return "#a78bfa";
  if (id === "447" || n.includes("deli")) return "#fb923c";
  if (n.includes("snack") || n.includes("popcorn")) return "#fbbf24";
  if (n.includes("beverage") || n.includes("water")) return "#38bdf8";
  if (n.includes("baking") || n.includes("coffee"))  return "#d97706";
  if (n.includes("canned") || n.includes("sauce"))   return "#f87171";
  if (n.includes("personal") || n.includes("care"))  return "#f9a8d4";
  if (n.includes("front") || n.includes("perimeter")) return "#64748b";
  return "#6366f1";
}

// ── Mini route map ─────────────────────────────────────────────────────────────
function RouteMap({ nodes, edges, route, currentNode }) {
  const [hovered, setHovered] = useState(null);
  if (!nodes.length) return null;
  const routeSet = new Set(route);
  const routeEdgeSet = new Set();
  for (let i = 0; i < route.length - 1; i++) {
    routeEdgeSet.add(`${route[i]}-${route[i+1]}`);
    routeEdgeSet.add(`${route[i+1]}-${route[i]}`);
  }
  return (
    <svg width="100%" viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      style={{ background: "#f0f2f5", borderRadius: 10, border: "1px solid #d1d5db", display: "block" }}>
      {edges.map((e, i) => {
        const f = nodes.find(n => n.id === e.from), t = nodes.find(n => n.id === e.to);
        if (!f || !t) return null;
        const [x1,y1] = toSVG(f.x,f.y), [x2,y2] = toSVG(t.x,t.y);
        const isR = routeEdgeSet.has(`${e.from}-${e.to}`);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={isR ? "#1d4ed8" : "#b0b8c4"} strokeWidth={isR ? 3 : 1.5} opacity={!isR ? 0.4 : 1} />;
      })}
      {nodes.map(n => {
        const [cx,cy] = toSVG(n.x,n.y);
        const isR = routeSet.has(n.id), isCurr = n.id === currentNode, isDim = !routeSet.has(n.id);
        const r = isCurr ? 18 : 13;
        const fill = isCurr ? "#ef4444" : isR ? "#1d4ed8" : nodeColor(n.id, n.name);
        const label = !isNaN(n.id) ? `A${n.id}` : n.id === "entrance" ? "ENT" : n.id === "exit" ? "EXIT" : n.id === "checkout" ? "CHK" : n.id.slice(0,4).toUpperCase();
        return (
          <g key={n.id} onMouseEnter={() => setHovered(n.id)} onMouseLeave={() => setHovered(null)}>
            {isCurr && <circle cx={cx} cy={cy} r={r+8} fill="none" stroke="#ef4444" strokeWidth={2} opacity={0.25}/>}
            {hovered===n.id && <circle cx={cx} cy={cy} r={r+6} fill="none" stroke={fill} strokeWidth={2} opacity={0.3}/>}
            <circle cx={cx} cy={cy} r={r} fill={fill} stroke={fill} strokeWidth={1.5} opacity={isDim ? 0.25 : 1}/>
            <text x={cx} y={cy+1} textAnchor="middle" dominantBaseline="middle" fontSize="10" fontWeight="800" fill="#fff" opacity={isDim ? 0.35 : 1} style={{pointerEvents:"none",userSelect:"none"}}>{label}</text>
            {hovered===n.id && (
              <g>
                <rect x={cx-55} y={cy-r-28} width={110} height={20} rx={4} fill="#1e293b" opacity={0.9}/>
                <text x={cx} y={cy-r-14} textAnchor="middle" fontSize="10" fill="#fff" style={{pointerEvents:"none",userSelect:"none"}}>{n.name.replace(/^Aisle \d+ - /,"")}</text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ── Step indicator ─────────────────────────────────────────────────────────────
const STEPS = [
  { id: 0, label: "Agent 0", desc: "Extract Ingredients" },
  { id: 1, label: "Agent 2", desc: "Navigate" },
  { id: 2, label: "Agent 3", desc: "Scan Aisle Sign" },
  { id: 3, label: "Agent 4", desc: "Find on Shelf" },
];

function StepBar({ current }) {
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "20px 32px", background: "#fff", borderBottom: "1px solid #e2e6ea" }}>
      {STEPS.map((s, i) => (
        <div key={s.id} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : 0 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
              fontWeight: 700, fontSize: 13,
              background: current > s.id ? "#22c55e" : current === s.id ? "#2563eb" : "#e2e8f0",
              color: current >= s.id ? "#fff" : "#94a3b8",
              border: current === s.id ? "2px solid #1d4ed8" : "2px solid transparent",
              transition: "all 0.3s",
            }}>
              {current > s.id ? "✓" : s.id + 1}
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: current === s.id ? "#2563eb" : current > s.id ? "#22c55e" : "#94a3b8" }}>{s.label}</div>
              <div style={{ fontSize: 10, color: "#94a3b8" }}>{s.desc}</div>
            </div>
          </div>
          {i < STEPS.length - 1 && (
            <div style={{ flex: 1, height: 2, margin: "0 12px", marginBottom: 24, background: current > s.id ? "#22c55e" : "#e2e8f0", transition: "background 0.3s" }} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Agent 0 — Extract ──────────────────────────────────────────────────────────
function Agent0({ onDone }) {
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [result, setResult]         = useState(null);
  const [listening, setListening]   = useState(false);
  const [listenError, setListenError] = useState("");
  const recognitionRef              = useRef(null);

  function startListen() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setListenError("Use Chrome for voice input."); return; }

    if (recognitionRef.current) { recognitionRef.current.stop(); return; }

    const r = new SR();
    r.lang = "en-US";
    r.interimResults = true;
    r.continuous = false;

    r.onresult = e => {
      const transcript = Array.from(e.results).map(res => res[0].transcript).join("");
      setInput(transcript);
      setListenError("");
    };

    r.onerror = e => {
      const msg = {
        "not-allowed":  "Microphone permission denied.",
        "no-speech":    "No speech detected — try again.",
        "network":      "Network error — use Chrome browser.",
        "audio-capture":"No microphone found.",
      }[e.error] || `Error: ${e.error}`;
      setListenError(msg);
      setListening(false);
      recognitionRef.current = null;
    };

    r.onend = () => { setListening(false); recognitionRef.current = null; };

    recognitionRef.current = r;
    r.start();
    setListening(true);
    setListenError("");
  }

  async function extract() {
    if (!input.trim()) return;
    setLoading(true); setResult(null);
    const res = await fetch(`${API}/extract`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input }),
    });
    const data = await res.json();
    setResult(data); setLoading(false);
  }

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: "40px 24px" }}>
      <h2 style={{ color: "#1e293b", fontSize: 22, fontWeight: 700, margin: "0 0 6px" }}>What would you like to make?</h2>
      <p style={{ color: "#94a3b8", fontSize: 14, margin: "0 0 24px" }}>
        Tell us a recipe, meal plan, occasion, or just list items — Agent 0 will build your grocery list.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && extract()}
          placeholder="e.g. carbonara for 4, vegan dinner, game day snacks..."
          style={{ flex: 1, padding: "12px 16px", borderRadius: 10, border: "1px solid #e2e6ea", background: "#f8fafc", color: "#1e293b", fontSize: 14, outline: "none", fontFamily: "inherit" }} />
        <button onClick={startListen} title={listening ? "Stop" : "Speak"} style={{
          padding: "0 14px", borderRadius: 10,
          border: `1px solid ${listening ? "#2563eb" : "#e2e6ea"}`,
          background: listening ? "#eff6ff" : "#f8fafc",
          color: listening ? "#2563eb" : "#94a3b8",
          cursor: "pointer", fontSize: 18,
        }}>{listening ? "⏹" : "🎤"}</button>
      </div>
      {listening && (
        <p style={{ color: "#2563eb", fontSize: 13, margin: "0 0 12px" }}>
          🔴 Listening — speak now, click ⏹ to stop
        </p>
      )}
      {listenError && <p style={{ color: "#dc2626", fontSize: 13, margin: "0 0 12px" }}>{listenError}</p>}

      <button onClick={extract} disabled={loading || !input.trim()} style={{
        width: "100%", padding: "12px 0", borderRadius: 10, border: "none",
        background: loading || !input.trim() ? "#e2e6ea" : "#2563eb",
        color: loading || !input.trim() ? "#94a3b8" : "#fff",
        fontSize: 15, fontWeight: 600, cursor: loading || !input.trim() ? "not-allowed" : "pointer", fontFamily: "inherit",
      }}>
        {loading ? "Extracting ingredients..." : "Extract Ingredients"}
      </button>

      {result && !result.error && (
        <div style={{ marginTop: 24 }}>
          {result.intro && (
            <div style={{ padding: "14px 16px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10, marginBottom: 16 }}>
              <p style={{ color: "#166534", fontSize: 14, margin: 0, fontStyle: "italic" }}>"{result.intro}"</p>
            </div>
          )}
          <div style={{ padding: "16px", background: "#fff", border: "1px solid #e2e6ea", borderRadius: 10 }}>
            <p style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, margin: "0 0 12px" }}>
              Found {result.ingredients.length} ingredients
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
              {result.ingredients.map((ing, i) => (
                <span key={i} style={{ padding: "4px 12px", background: "#eff6ff", color: "#2563eb", borderRadius: 20, fontSize: 13, fontWeight: 500, border: "1px solid #bfdbfe" }}>
                  {ing}
                </span>
              ))}
            </div>
            <button onClick={() => onDone(result.ingredients)} style={{
              width: "100%", padding: "11px 0", borderRadius: 10, border: "none",
              background: "#2563eb", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
            }}>
              Navigate with these items →
            </button>
          </div>
        </div>
      )}
      {result?.error && (
        <div style={{ marginTop: 16, padding: 14, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10 }}>
          <p style={{ color: "#dc2626", fontSize: 13, margin: 0 }}>Error: {result.error}</p>
        </div>
      )}
    </div>
  );
}

// ── Agent 2 — Navigate ─────────────────────────────────────────────────────────
function Agent2({ ingredients, mapData, onStepReady }) {
  const [result, setResult]           = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const activeStepRef                 = useRef(null);

  useEffect(() => {
    if (ingredients.length) doNavigate();
  }, []);

  useEffect(() => {
    if (activeStepRef.current) {
      activeStepRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [currentStep]);

  async function doNavigate() {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API}/navigate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: ingredients }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const currentNode = result?.route?.[Math.min(currentStep, (result?.route?.length ?? 1) - 1)] ?? "entrance";
  const directions  = result?.directions ?? [];

  return (
    <div style={{ display: "flex", height: "calc(100vh - 180px)" }}>
      {/* Sidebar */}
      <div style={{ width: 320, borderRight: "1px solid #e2e6ea", background: "#fff", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid #f1f5f9" }}>
          <p style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, margin: "0 0 8px" }}>Shopping List</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {ingredients.map((ing, i) => (
              <span key={i} style={{ padding: "3px 10px", background: "#eff6ff", color: "#2563eb", borderRadius: 20, fontSize: 12, border: "1px solid #bfdbfe" }}>{ing}</span>
            ))}
          </div>
          {result?.not_found?.length > 0 && (
            <p style={{ color: "#dc2626", fontSize: 12, margin: "8px 0 0" }}>Not found: {result.not_found.join(", ")}</p>
          )}
        </div>

        {loading && <p style={{ color: "#94a3b8", padding: 20, fontSize: 13 }}>Finding best route...</p>}
        {error && (
          <div style={{ margin: 16, padding: 14, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10 }}>
            <p style={{ color: "#dc2626", fontSize: 13, margin: "0 0 10px" }}>Failed: {error}</p>
            <button onClick={doNavigate} style={{ padding: "7px 16px", borderRadius: 8, border: "none", background: "#dc2626", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
              Retry
            </button>
          </div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
          {directions.map((d, i) => {
            const isActive = result?.route?.indexOf(d.target) === currentStep;
            const dirColor = d.direction === "TL" ? "#d97706" : d.direction === "TR" ? "#2563eb" : "#64748b";
            return (
              <div key={i} ref={isActive ? activeStepRef : null}
                onClick={() => setCurrentStep(result.route.indexOf(d.target))}
                style={{ margin: "0 12px 4px", padding: "10px 12px", borderRadius: 10, cursor: "pointer", background: isActive ? "#eff6ff" : "#fafbfc", border: `1px solid ${isActive ? "#bfdbfe" : "#e2e8f0"}` }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 20, height: 20, borderRadius: "50%", fontSize: 10, fontWeight: 700, background: isActive ? "#2563eb" : "#e2e8f0", color: isActive ? "#fff" : "#94a3b8", display: "flex", alignItems: "center", justifyContent: "center" }}>{d.step}</span>
                    <span style={{ color: isActive ? "#1e40af" : "#334155", fontWeight: 600, fontSize: 13 }}>{d.name}</span>
                  </div>
                  <span style={{ fontSize: 10, color: "#94a3b8" }}>{d.step}/{d.total}</span>
                </div>
                {d.walk.length > 0 && (
                  <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 5 }}>
                    {d.walk.map((s,j) => <span key={j}><span style={{ color: isActive ? "#475569" : "#cbd5e1" }}>{s.replace(/^Aisle \d+ - /,"")}</span>{j < d.walk.length-1 && <span style={{ color: "#e2e8f0", margin: "0 3px" }}>→</span>}</span>)}
                  </div>
                )}
                <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: 5, fontSize: 11, fontWeight: 600, background: isActive ? "#eff6ff" : "#f1f5f9", color: isActive ? dirColor : "#94a3b8", border: `1px solid ${isActive ? dirColor+"40" : "#e2e8f0"}` }}>
                  {d.direction} · {d.dir_label}
                </span>
                {d.items.map((item,j) => <div key={j} style={{ fontSize: 11, color: isActive ? "#334155" : "#64748b", paddingLeft: 4, lineHeight: 1.7, marginTop: 4 }}>· {item}</div>)}
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "12px 16px", borderTop: "1px solid #e2e6ea" }}>
          {result && (
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setCurrentStep(s => Math.max(0, s-1))} style={{ flex: 1, padding: "8px 0", borderRadius: 8, border: "1px solid #e2e6ea", background: "#f8fafc", color: "#475569", cursor: "pointer", fontSize: 13, fontFamily: "inherit" }}>← Prev</button>
              <button onClick={() => setCurrentStep(s => Math.min(result.route.length-1, s+1))} style={{ flex: 1, padding: "8px 0", borderRadius: 8, border: "1px solid #e2e6ea", background: "#f8fafc", color: "#475569", cursor: "pointer", fontSize: 13, fontFamily: "inherit" }}>Next →</button>
            </div>
          )}
          {result && (
            <button onClick={() => onStepReady(result)} style={{ padding: "10px 0", borderRadius: 8, border: "none", background: "#2563eb", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
              Start Walking → Scan Aisle Signs
            </button>
          )}
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1, padding: 20, background: "#f1f4f8", overflowY: "auto" }}>
        <RouteMap nodes={mapData.nodes||[]} edges={mapData.edges||[]} route={result?.route||[]} currentNode={currentNode} />
      </div>
    </div>
  );
}

// ── Agent 3 — Scan Aisle Sign ──────────────────────────────────────────────────
function Agent3({ navResult, onConfirmed }) {
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const [scanning, setScanning]   = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [loading, setLoading]     = useState(false);

  async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    videoRef.current.srcObject = stream; videoRef.current.play(); setScanning(true);
  }

  function capture() {
    const canvas = canvasRef.current, video = videoRef.current;
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(async blob => {
      setLoading(true); setScanResult(null);
      const form = new FormData();
      form.append("file", blob, "sign.jpg");
      const res = await fetch(`${API}/ocr`, { method: "POST", body: form });
      setScanResult(await res.json()); setLoading(false);
    }, "image/jpeg");
  }

  const matched = scanResult?.matched;

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "32px 24px" }}>
      <h2 style={{ color: "#1e293b", fontSize: 20, fontWeight: 700, margin: "0 0 6px" }}>Scan Aisle Sign</h2>
      <p style={{ color: "#94a3b8", fontSize: 13, margin: "0 0 20px" }}>Point your camera at the aisle sign to confirm your current location on the map.</p>

      {!scanning ? (
        <button onClick={startCamera} style={{ width: "100%", padding: "12px 0", borderRadius: 10, border: "none", background: "#2563eb", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
          📷 Start Camera
        </button>
      ) : (
        <>
          <video ref={videoRef} style={{ width: "100%", borderRadius: 10, marginBottom: 10 }} autoPlay playsInline muted />
          <button onClick={capture} disabled={loading} style={{ width: "100%", padding: "12px 0", borderRadius: 10, border: "none", background: loading ? "#e2e6ea" : "#0284c7", color: loading ? "#94a3b8" : "#fff", fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
            {loading ? "Reading sign..." : "📸 Read Aisle Sign"}
          </button>
        </>
      )}
      <canvas ref={canvasRef} style={{ display: "none" }} />

      {scanResult && (
        <div style={{ marginTop: 16, padding: 16, borderRadius: 10, background: matched ? "#f0fdf4" : "#fff7ed", border: `1px solid ${matched ? "#bbf7d0" : "#fed7aa"}` }}>
          {matched ? (
            <>
              <p style={{ color: "#166534", fontSize: 15, fontWeight: 700, margin: "0 0 4px" }}>✓ Confirmed: {matched.aisle}</p>
              <p style={{ color: "#94a3b8", fontSize: 12, margin: "0 0 12px" }}>Aisle code: {matched.code}</p>
              <button onClick={() => onConfirmed(matched)} style={{ width: "100%", padding: "10px 0", borderRadius: 8, border: "none", background: "#22c55e", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                Confirmed — Find product on shelf →
              </button>
            </>
          ) : (
            <p style={{ color: "#92400e", fontSize: 13, margin: 0 }}>No aisle sign detected. Try again or move closer.</p>
          )}
        </div>
      )}

      <button onClick={() => onConfirmed(null)} style={{ width: "100%", marginTop: 10, padding: "9px 0", borderRadius: 10, border: "1px solid #e2e6ea", background: "transparent", color: "#94a3b8", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}>
        Skip → Go to shelf scanner
      </button>
    </div>
  );
}

// ── Agent 4 — Shelf Scanner ────────────────────────────────────────────────────
function Agent4({ ingredients }) {
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const [product, setProduct]     = useState(ingredients[0] || "");
  const [scanning, setScanning]   = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [loading, setLoading]     = useState(false);
  const [done, setDone]           = useState([]);

  async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    videoRef.current.srcObject = stream; videoRef.current.play(); setScanning(true);
  }

  function capture() {
    const canvas = canvasRef.current, video = videoRef.current;
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(async blob => {
      setLoading(true); setScanResult(null);
      const form = new FormData();
      form.append("product", product); form.append("file", blob, "shelf.jpg");
      const res = await fetch(`${API}/scan`, { method: "POST", body: form });
      setScanResult(await res.json()); setLoading(false);
    }, "image/jpeg");
  }

  function markFound() {
    setDone(d => [...d, product]);
    const remaining = ingredients.filter(i => ![...done, product].includes(i));
    if (remaining.length) setProduct(remaining[0]);
    setScanResult(null);
  }

  const remaining = ingredients.filter(i => !done.includes(i));

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "32px 24px" }}>
      <h2 style={{ color: "#1e293b", fontSize: 20, fontWeight: 700, margin: "0 0 6px" }}>Find on Shelf</h2>

      {/* Progress */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 20 }}>
        {ingredients.map((ing, i) => (
          <span key={i} style={{ padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 500, background: done.includes(ing) ? "#f0fdf4" : ing === product ? "#eff6ff" : "#f8fafc", color: done.includes(ing) ? "#166534" : ing === product ? "#1d4ed8" : "#94a3b8", border: `1px solid ${done.includes(ing) ? "#bbf7d0" : ing === product ? "#bfdbfe" : "#e2e8f0"}` }}>
            {done.includes(ing) ? "✓ " : ""}{ing}
          </span>
        ))}
      </div>

      {remaining.length === 0 ? (
        <div style={{ padding: 24, background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 12, textAlign: "center" }}>
          <p style={{ fontSize: 24, margin: "0 0 8px" }}>🎉</p>
          <p style={{ color: "#166534", fontSize: 16, fontWeight: 700, margin: 0 }}>All items found! Head to checkout.</p>
        </div>
      ) : (
        <>
          <div style={{ marginBottom: 12 }}>
            <p style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, margin: "0 0 8px" }}>Looking for</p>
            <select value={product} onChange={e => { setProduct(e.target.value); setScanResult(null); }}
              style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e6ea", background: "#f8fafc", color: "#1e293b", fontSize: 14, fontFamily: "inherit", outline: "none" }}>
              {remaining.map((ing, i) => <option key={i} value={ing}>{ing}</option>)}
            </select>
          </div>

          {!scanning ? (
            <button onClick={startCamera} style={{ width: "100%", padding: "12px 0", borderRadius: 10, border: "none", background: "#2563eb", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
              📷 Start Camera
            </button>
          ) : (
            <>
              <video ref={videoRef} style={{ width: "100%", borderRadius: 10, marginBottom: 10 }} autoPlay playsInline muted />
              <button onClick={capture} disabled={loading} style={{ width: "100%", padding: "12px 0", borderRadius: 10, border: "none", background: loading ? "#e2e6ea" : "#0284c7", color: loading ? "#94a3b8" : "#fff", fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
                {loading ? "Scanning..." : "🔍 Scan Shelf"}
              </button>
            </>
          )}
          <canvas ref={canvasRef} style={{ display: "none" }} />

          {scanResult && (
            <div style={{ marginTop: 14, padding: 16, borderRadius: 10, background: scanResult.found ? "#f0fdf4" : "#fff7ed", border: `1px solid ${scanResult.found ? "#bbf7d0" : "#fed7aa"}` }}>
              <p style={{ fontSize: 15, fontWeight: 600, color: scanResult.found ? "#166534" : "#92400e", margin: "0 0 8px" }}>{scanResult.spoken}</p>
              {scanResult.found && <p style={{ color: "#94a3b8", fontSize: 12, margin: "0 0 12px" }}>Confidence: {(scanResult.confidence * 100).toFixed(0)}%</p>}
              {scanResult.found && (
                <button onClick={markFound} style={{ width: "100%", padding: "9px 0", borderRadius: 8, border: "none", background: "#22c55e", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                  ✓ Got it — next item
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Root pipeline ──────────────────────────────────────────────────────────────
export default function Pipeline() {
  const [step, setStep]               = useState(0);
  const [ingredients, setIngredients] = useState([]);
  const [navResult, setNavResult]     = useState(null);
  const [mapData, setMapData]         = useState({ nodes: [], edges: [] });

  useEffect(() => {
    fetch(`${API}/map`).then(r => r.json()).then(setMapData).catch(() => {});
  }, []);

  return (
    <div style={{ minHeight: "calc(100vh - 57px)", background: "#f1f4f8", fontFamily: "'Inter', sans-serif" }}>
      <StepBar current={step} />

      {step === 0 && (
        <Agent0 onDone={ings => { setIngredients(ings); setStep(1); }} />
      )}
      {step === 1 && (
        <Agent2 ingredients={ingredients} mapData={mapData}
          onStepReady={result => { setNavResult(result); setStep(2); }} />
      )}
      {step === 2 && (
        <Agent3 navResult={navResult}
          onConfirmed={() => setStep(3)} />
      )}
      {step === 3 && (
        <Agent4 ingredients={ingredients} />
      )}
    </div>
  );
}
