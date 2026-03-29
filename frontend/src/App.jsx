import { useState, useEffect } from "react";
import StoreLayout from "./StoreLayout";

const API = "http://localhost:8003";
const SCALE_X = 82, SCALE_Y = 72, OFFSET_X = 50, OFFSET_Y = 110;
const SVG_W = 1160, SVG_H = 600;

function toSVG(x, y) {
  return [x * SCALE_X + OFFSET_X, SVG_H - (y * SCALE_Y + OFFSET_Y)];
}

function shortLabel(id, name) {
  if (id === "entrance") return "Entrance";
  if (id === "exit")     return "Exit";
  if (id === "checkout") return "Checkout";
  // Special named nodes
  if (!isNaN(id)) return `A${id}`;
  return id.charAt(0).toUpperCase() + id.slice(0, 5);
}

function subLabel(id, name) {
  if (["entrance","exit","checkout"].includes(id)) return null;
  if (!isNaN(id)) return name.replace(/^Aisle \d+ - /, "").split(" ").slice(0, 2).join(" ");
  return null;
}

// Color each aisle by department type
function aisleColor(id, name = "") {
  const n = name.toLowerCase();
  if (id === "entrance")              return { fill: "#f59e0b", stroke: "#d97706" }; // amber
  if (id === "exit")                  return { fill: "#ef4444", stroke: "#dc2626" }; // red
  if (id === "checkout")              return { fill: "#8b5cf6", stroke: "#7c3aed" }; // purple
  if (id === "100" || n.includes("dairy"))    return { fill: "#3b82f6", stroke: "#2563eb" }; // blue
  if (id === "101" || n.includes("meat"))     return { fill: "#ef4444", stroke: "#dc2626" }; // red
  if (id === "152" || n.includes("bakery"))   return { fill: "#f97316", stroke: "#ea580c" }; // orange
  if (id === "34"  || n.includes("yogurt"))   return { fill: "#06b6d4", stroke: "#0891b2" }; // cyan
  if (["105","351","352"].includes(id) || n.includes("produce") || n.includes("fruit") || n.includes("veg") || n.includes("green")) return { fill: "#22c55e", stroke: "#16a34a" }; // green
  if (["8","40","42"].includes(id) || n.includes("frozen"))     return { fill: "#67e8f9", stroke: "#06b6d4" }; // light cyan
  if (id === "cleaning")              return { fill: "#94a3b8", stroke: "#64748b" }; // slate
  if (id === "vitamins")              return { fill: "#a78bfa", stroke: "#7c3aed" }; // violet
  if (id === "pharmacy")              return { fill: "#10b981", stroke: "#059669" }; // emerald
  if (id === "447" || n.includes("deli")) return { fill: "#fb923c", stroke: "#ea580c" }; // orange
  if (n.includes("snack") || n.includes("popcorn") || n.includes("chip")) return { fill: "#fbbf24", stroke: "#f59e0b" }; // yellow
  if (n.includes("beverage") || n.includes("water") || n.includes("soda")) return { fill: "#38bdf8", stroke: "#0284c7" }; // sky
  if (n.includes("baking") || n.includes("coffee") || n.includes("flour")) return { fill: "#d97706", stroke: "#b45309" }; // amber-dark
  if (n.includes("breakfast") || n.includes("cereal") || n.includes("oat")) return { fill: "#fde68a", stroke: "#f59e0b" }; // yellow-light
  if (n.includes("canned") || n.includes("sauce") || n.includes("bean"))   return { fill: "#f87171", stroke: "#ef4444" }; // rose
  if (n.includes("international") || n.includes("bread") || n.includes("tortilla")) return { fill: "#c084fc", stroke: "#a855f7" }; // purple-light
  if (n.includes("personal") || n.includes("care") || n.includes("soap"))  return { fill: "#f9a8d4", stroke: "#ec4899" }; // pink
  if (n.includes("oil") || n.includes("condiment"))  return { fill: "#86efac", stroke: "#22c55e" }; // green-light
  if (n.includes("granola") || n.includes("syrup"))  return { fill: "#fcd34d", stroke: "#f59e0b" }; // yellow
  if (n.includes("pasta") || n.includes("dry") || n.includes("rice"))      return { fill: "#fed7aa", stroke: "#f97316" }; // peach
  if (n.includes("front") || n.includes("perimeter")) return { fill: "#64748b", stroke: "#475569" };
  return { fill: "#6366f1", stroke: "#4f46e5" }; // indigo fallback
}

function StoreMap({ nodes, edges, route, currentNode }) {
  const [hovered, setHovered] = useState(null);
  if (!nodes.length) return null;

  const hasRoute     = route.length > 0;
  const routeSet     = new Set(route);
  const routeEdgeSet = new Set();
  for (let i = 0; i < route.length - 1; i++) {
    routeEdgeSet.add(`${route[i]}-${route[i+1]}`);
    routeEdgeSet.add(`${route[i+1]}-${route[i]}`);
  }

  const specialIds = new Set(["entrance", "exit", "checkout"]);

  return (
    <svg width="100%" viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      style={{ background: "#f0f2f5", borderRadius: 12, display: "block", border: "1px solid #d1d5db" }}>

      {/* Edges */}
      {edges.map((e, i) => {
        const from = nodes.find(n => n.id === e.from);
        const to   = nodes.find(n => n.id === e.to);
        if (!from || !to) return null;
        const [x1, y1] = toSVG(from.x, from.y);
        const [x2, y2] = toSVG(to.x,   to.y);
        const isRoute  = routeEdgeSet.has(`${e.from}-${e.to}`);
        return (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke={isRoute ? "#1d4ed8" : "#b0b8c4"}
            strokeWidth={isRoute ? 3 : 1.5}
            opacity={hasRoute && !isRoute ? 0.5 : 1} />
        );
      })}

      {/* Nodes */}
      {nodes.map(n => {
        const [cx, cy] = toSVG(n.x, n.y);
        const isRoute   = hasRoute && routeSet.has(n.id);
        const isCurrent = hasRoute && n.id === currentNode;
        const isDimmed  = hasRoute && !routeSet.has(n.id);
        const isHovered = hovered === n.id;
        const isSpecial = specialIds.has(n.id);
        const r = isCurrent ? 20 : isSpecial ? 18 : 14;
        const label = shortLabel(n.id, n.name);
        const colors = aisleColor(n.id, n.name);
        // Route/current overrides color; otherwise use department color
        const fillColor   = isCurrent ? "#ef4444" : isRoute ? "#1d4ed8" : colors.fill;
        const strokeColor = isCurrent ? "#dc2626" : isRoute ? "#1e40af" : colors.stroke;

        return (
          <g key={n.id}
            onMouseEnter={() => setHovered(n.id)}
            onMouseLeave={() => setHovered(null)}
            style={{ cursor: "default" }}>

            {/* Pulse ring for current */}
            {isCurrent && (
              <circle cx={cx} cy={cy} r={r + 10} fill="none" stroke="#ef4444" strokeWidth={2} opacity={0.25} />
            )}
            {/* Hover ring */}
            {isHovered && (
              <circle cx={cx} cy={cy} r={r + 7} fill="none"
                stroke={strokeColor} strokeWidth={2} opacity={0.35} />
            )}

            <circle cx={cx} cy={cy} r={r}
              fill={fillColor}
              stroke={strokeColor}
              strokeWidth={2}
              opacity={isDimmed ? 0.25 : 1} />

            {/* Aisle code */}
            <text x={cx} y={subLabel(n.id, n.name) ? cy - 3 : cy + 1}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="11" fontWeight="800"
              fill="#fff"
              opacity={isDimmed ? 0.35 : 1}
              style={{ pointerEvents: "none", userSelect: "none" }}>
              {label}
            </text>
            {/* Department name under code */}
            {subLabel(n.id, n.name) && (
              <text x={cx} y={cy + 9} textAnchor="middle" dominantBaseline="middle"
                fontSize="7" fontWeight="400"
                fill="rgba(255,255,255,0.8)"
                opacity={isDimmed ? 0.35 : 1}
                style={{ pointerEvents: "none", userSelect: "none" }}>
                {subLabel(n.id, n.name)}
              </text>
            )}

            {/* Tooltip on hover */}
            {isHovered && (() => {
              const tipW = Math.max(120, n.name.replace(/^Aisle \d+ - /, "").length * 7 + 16);
              const tipX = cx - tipW / 2;
              return (
                <g>
                  <rect x={tipX} y={cy - r - 34} width={tipW} height={24}
                    rx={6} fill="#1e293b" opacity={0.92} />
                  <text x={cx} y={cy - r - 18} textAnchor="middle"
                    fontSize="11" fill="#fff" fontWeight="500"
                    style={{ pointerEvents: "none", userSelect: "none" }}>
                    {n.name.replace(/^Aisle \d+ - /, "")}
                  </text>
                </g>
              );
            })()}
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(16, ${SVG_H - 24})`}>
        <circle cx={8} cy={0} r={7} fill="#ef4444" />
        <text x={20} y={4} fontSize="11" fill="#94a3b8">You</text>
        <circle cx={60} cy={0} r={7} fill="#2563eb" />
        <text x={72} y={4} fontSize="11" fill="#94a3b8">Route</text>
        <circle cx={118} cy={0} r={7} fill="#e8ecf0" stroke="#c8cdd5" strokeWidth={1.5} />
        <text x={130} y={4} fontSize="11" fill="#94a3b8">Aisle</text>
      </g>
    </svg>
  );
}

export default function App() {
  const [tab, setTab]                 = useState("map");
  const [mapData, setMapData]         = useState({ nodes: [], edges: [], store: "", address: "" });
  const [items, setItems]             = useState("");
  const [result, setResult]           = useState(null);
  const [loading, setLoading]         = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    fetch(`${API}/map`).then(r => r.json()).then(setMapData).catch(() => {});
  }, []);

  async function navigate() {
    setLoading(true); setResult(null); setCurrentStep(0);
    const itemList = items.split(",").map(s => s.trim()).filter(Boolean);
    const res = await fetch(`${API}/navigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: itemList }),
    });
    setResult(await res.json());
    setLoading(false);
  }

  const currentNode = result?.route?.[currentStep] ?? "entrance";
  const directions  = result?.directions ?? [];

  return (
    <div style={{ fontFamily: "'Inter', -apple-system, sans-serif", background: "#f1f4f8", minHeight: "100vh", color: "#1e293b" }}>

      {/* ── Header ── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 28px", borderBottom: "1px solid #e2e6ea",
        background: "#fff", boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 1 }}>
          <span style={{ fontSize: 20, fontWeight: 800, color: "#2563eb", letterSpacing: -0.5 }}>Wayfinder</span>
          <span style={{ fontSize: 20, fontWeight: 300, color: "#64748b", letterSpacing: -0.5 }}>AI</span>
        </div>

        {mapData.store && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#22c55e" }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#1e293b", lineHeight: 1.2 }}>{mapData.store}</div>
              {mapData.address && <div style={{ fontSize: 11, color: "#94a3b8" }}>{mapData.address}</div>}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 2, alignItems: "center" }}>
          {[["map", "Store Map"], ["nav", "Navigate"]].map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: "7px 18px", borderRadius: 8, fontSize: 13, cursor: "pointer",
              border: tab === t ? "1px solid #2563eb" : "1px solid transparent",
              background: tab === t ? "#eff6ff" : "transparent",
              color: tab === t ? "#2563eb" : "#94a3b8",
              fontWeight: tab === t ? 600 : 400,
            }}>{label}</button>
          ))}
          <a href="http://localhost:3001" target="_blank" rel="noreferrer" style={{
            padding: "7px 18px", borderRadius: 8, fontSize: 13, cursor: "pointer",
            border: "1px solid #22c55e", background: "#f0fdf4",
            color: "#16a34a", fontWeight: 600, textDecoration: "none",
            display: "inline-flex", alignItems: "center", gap: 5,
          }}>
            Full Pipeline ↗
          </a>
        </div>
      </div>

      {tab === "map" && <StoreLayout />}

      {/* ── Navigate ── */}
      {tab === "nav" && (
        <div style={{ display: "flex", height: "calc(100vh - 57px)" }}>

          {/* Sidebar */}
          <div style={{
            width: 340, borderRight: "1px solid #e2e6ea", background: "#fff",
            display: "flex", flexDirection: "column", flexShrink: 0,
            boxShadow: "2px 0 8px rgba(0,0,0,0.04)",
          }}>

            {/* Search */}
            <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid #f1f4f8" }}>
              <p style={{ color: "#94a3b8", fontSize: 11, margin: "0 0 8px", textTransform: "uppercase", letterSpacing: 0.8, fontWeight: 600 }}>
                Shopping List
              </p>
              <input
                value={items}
                onChange={e => setItems(e.target.value)}
                onKeyDown={e => e.key === "Enter" && navigate()}
                placeholder="milk, pasta, chips..."
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 8,
                  border: "1px solid #e2e6ea", background: "#f8fafc",
                  color: "#1e293b", fontSize: 14, boxSizing: "border-box",
                  outline: "none", fontFamily: "inherit",
                }}
              />
              <button onClick={navigate} disabled={loading} style={{
                width: "100%", marginTop: 8, padding: "10px 0", borderRadius: 8,
                border: "none", background: loading ? "#e2e6ea" : "#2563eb",
                color: loading ? "#94a3b8" : "#fff", fontSize: 14,
                fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
                fontFamily: "inherit",
              }}>
                {loading ? "Finding route..." : "Get Directions"}
              </button>

              {result?.not_found?.length > 0 && (
                <div style={{ marginTop: 8, padding: "8px 12px", background: "#fef2f2", borderRadius: 6, border: "1px solid #fecaca" }}>
                  <p style={{ color: "#dc2626", fontSize: 12, margin: 0 }}>
                    Not found: {result.not_found.join(", ")}
                  </p>
                </div>
              )}
            </div>

            {/* Directions */}
            <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
              {directions.length === 0 && !loading && (
                <p style={{ color: "#cbd5e1", fontSize: 13, marginTop: 32, textAlign: "center", padding: "0 20px" }}>
                  Enter items above to get step-by-step directions
                </p>
              )}

              {directions.map((d, i) => {
                const isActive = result?.route?.indexOf(d.target) === currentStep;
                const dirColor = d.direction === "TL" ? "#d97706" : d.direction === "TR" ? "#2563eb" : "#64748b";
                const dirBg    = d.direction === "TL" ? "#fffbeb" : d.direction === "TR" ? "#eff6ff" : "#f8fafc";

                return (
                  <div key={i} onClick={() => setCurrentStep(result.route.indexOf(d.target))}
                    style={{
                      margin: "0 12px 4px", padding: "12px 14px", borderRadius: 10, cursor: "pointer",
                      background: isActive ? "#eff6ff" : "#fafbfc",
                      border: `1px solid ${isActive ? "#bfdbfe" : "#e2e8f0"}`,
                      transition: "all 0.15s",
                    }}
                  >
                    {/* Step header */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{
                          width: 22, height: 22, borderRadius: "50%", fontSize: 10, fontWeight: 700,
                          background: isActive ? "#2563eb" : "#e2e8f0",
                          color: isActive ? "#fff" : "#94a3b8",
                          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        }}>{d.step}</span>
                        <span style={{ color: isActive ? "#1e40af" : "#334155", fontWeight: 600, fontSize: 13 }}>
                          {d.name}
                        </span>
                      </div>
                      <span style={{ fontSize: 10, color: "#94a3b8" }}>{d.step}/{d.total}</span>
                    </div>

                    {/* Walk path */}
                    {d.walk.length > 0 && (
                      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6, lineHeight: 1.5 }}>
                        <span style={{ color: "#94a3b8", fontWeight: 600 }}>Walk </span>
                        {d.walk.map((s, j) => (
                          <span key={j}>
                            <span style={{ color: isActive ? "#475569" : "#94a3b8" }}>
                              {s.replace(/^Aisle \d+ - /, "")}
                            </span>
                            {j < d.walk.length - 1 && <span style={{ color: "#cbd5e1", margin: "0 3px" }}>→</span>}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Direction badge */}
                    <div style={{ marginBottom: 6 }}>
                      <span style={{
                        display: "inline-flex", alignItems: "center", gap: 4,
                        padding: "2px 8px", borderRadius: 5, fontSize: 11, fontWeight: 600,
                        background: isActive ? dirBg : "#f1f5f9",
                        color: isActive ? dirColor : "#94a3b8",
                        border: `1px solid ${isActive ? dirColor + "40" : "#e2e8f0"}`,
                      }}>
                        {d.direction} · {d.dir_label}
                      </span>
                    </div>

                    {/* Audio */}
                    {d.audio && (
                      <div style={{ fontSize: 11, color: "#94a3b8", fontStyle: "italic", marginBottom: 6 }}>
                        {d.audio.split(".")[0]}.
                      </div>
                    )}

                    {/* Items */}
                    {d.items.map((item, j) => (
                      <div key={j} style={{
                        fontSize: 12, color: isActive ? "#334155" : "#64748b",
                        paddingLeft: 4, lineHeight: 1.7,
                      }}>
                        · {item}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            {/* Prev / Next */}
            {result && (
              <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderTop: "1px solid #e2e6ea" }}>
                <button onClick={() => setCurrentStep(s => Math.max(0, s - 1))}
                  style={{ flex: 1, padding: "9px 0", borderRadius: 8, border: "1px solid #e2e6ea", background: "#f8fafc", color: "#475569", cursor: "pointer", fontSize: 13, fontFamily: "inherit" }}>
                  ← Prev
                </button>
                <button onClick={() => setCurrentStep(s => Math.min(result.route.length - 1, s + 1))}
                  style={{ flex: 1, padding: "9px 0", borderRadius: 8, border: "1px solid #e2e6ea", background: "#f8fafc", color: "#475569", cursor: "pointer", fontSize: 13, fontFamily: "inherit" }}>
                  Next →
                </button>
              </div>
            )}
          </div>

          {/* Map */}
          <div style={{ flex: 1, padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", background: "#f1f4f8" }}>
            <StoreMap
              nodes={mapData.nodes || []}
              edges={mapData.edges || []}
              route={result?.route || []}
              currentNode={currentNode}
            />
          </div>
        </div>
      )}
    </div>
  );
}
