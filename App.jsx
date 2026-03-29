import { useState, useEffect, useRef } from "react";

function SensorPanel() {
  const [data, setData] = useState(null);

  useEffect(() => {
    const id = setInterval(() => {
      fetch(`${API}/sensors`)
        .then(r => r.json())
        .then(setData)
        .catch(() => {});
    }, 300);
    return () => clearInterval(id);
  }, []);

  if (!data) return null;

  const stableColor = data.stable ? "#00ff88" : "#ff4757";
  const walkColor   = data.walking ? "#00ff88" : "#aaa";
  const barW        = `${Math.round((data.stability_score || 0) * 100)}%`;

  return (
    <div style={{ background:"#1a1a2e", borderRadius:10, padding:14,
                  marginBottom:20, border:"1px solid #333" }}>
      <div style={{ display:"flex", justifyContent:"space-between",
                    alignItems:"center", marginBottom:10 }}>
        <span style={{ color:"#00ff88", fontWeight:"bold", fontSize:14 }}>
          Live Sensors
        </span>
        <span style={{ fontSize:11, color: data.connected ? "#00ff88" : "#ff4757" }}>
          {data.connected ? "● Phone connected" : "○ No phone — connect via Sensor Server app"}
        </span>
      </div>

      <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>

        {/* Stability */}
        <div style={{ flex:1, minWidth:140 }}>
          <div style={{ fontSize:11, color:"#aaa", marginBottom:4 }}>Gyroscope — Stability</div>
          <div style={{ background:"#333", borderRadius:4, height:10 }}>
            <div style={{ width:barW, background:stableColor, borderRadius:4,
                          height:10, transition:"width 0.3s" }} />
          </div>
          <div style={{ fontSize:11, color:stableColor, marginTop:3 }}>
            {data.stable ? "Steady — OCR active" : "Shaking — OCR paused"}
          </div>
          {data.turn !== "none" && (
            <div style={{ marginTop:5, fontSize:12, color:"#fdcb6e", fontWeight:"bold" }}>
              ↻ Turn {data.turn} detected
            </div>
          )}
        </div>

        {/* Pedometer */}
        <div style={{ flex:1, minWidth:110 }}>
          <div style={{ fontSize:11, color:"#aaa", marginBottom:4 }}>Pedometer</div>
          <div style={{ fontSize:26, fontWeight:"bold", color:"#fff", lineHeight:1 }}>
            {data.steps}
            <span style={{ fontSize:12, color:"#aaa", marginLeft:5 }}>steps</span>
          </div>
          <div style={{ fontSize:11, color:walkColor, marginTop:3 }}>
            {(data.distance_m || 0).toFixed(1)} m
            &nbsp;·&nbsp;{data.walking ? "walking" : "standing"}
          </div>
          <div style={{ fontSize:11, color:"#aaa", marginTop:2 }}>
            Heading: {(data.heading_deg || 0).toFixed(0)}°
          </div>
        </div>

        {/* Accelerometer bars */}
        <div style={{ flex:1, minWidth:140 }}>
          <div style={{ fontSize:11, color:"#aaa", marginBottom:4 }}>Accelerometer (m/s²)</div>
          {["x","y","z"].map(ax => (
            <div key={ax} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:4 }}>
              <span style={{ color:"#aaa", fontSize:11, width:10 }}>{ax}</span>
              <div style={{ background:"#333", borderRadius:2, height:6, flex:1 }}>
                <div style={{
                  width:`${Math.min(100, Math.abs((data.accelerometer||{})[ax]||0) / 20 * 100)}%`,
                  background:"#4ecdc4", borderRadius:2, height:6
                }} />
              </div>
              <span style={{ fontSize:10, color:"#ccc", width:38, textAlign:"right" }}>
                {((data.accelerometer||{})[ax]||0).toFixed(1)}
              </span>
            </div>
          ))}
        </div>

        {/* Gyroscope bars */}
        <div style={{ flex:1, minWidth:140 }}>
          <div style={{ fontSize:11, color:"#aaa", marginBottom:4 }}>Gyroscope (rad/s)</div>
          {["x","y","z"].map(ax => (
            <div key={ax} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:4 }}>
              <span style={{ color:"#aaa", fontSize:11, width:10 }}>{ax}</span>
              <div style={{ background:"#333", borderRadius:2, height:6, flex:1 }}>
                <div style={{
                  width:`${Math.min(100, Math.abs((data.gyroscope||{})[ax]||0) / 3 * 100)}%`,
                  background:"#a29bfe", borderRadius:2, height:6
                }} />
              </div>
              <span style={{ fontSize:10, color:"#ccc", width:38, textAlign:"right" }}>
                {((data.gyroscope||{})[ax]||0).toFixed(2)}
              </span>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}

const API = "http://localhost:8000";
const SCALE_X = 80, SCALE_Y = 60, OFFSET_X = 40, OFFSET_Y = 40;

function toSVG(x, y) {
  return [x * SCALE_X + OFFSET_X, 420 - (y * SCALE_Y + OFFSET_Y)];
}

function StoreMap({ nodes, edges, route, currentNode }) {
  if (!nodes.length) return <p style={{ color: "#aaa" }}>Loading map...</p>;
  const routeSet = new Set(route);
  return (
    <svg width="100%" viewBox="0 0 1000 500" style={{ background: "#1a1a2e", borderRadius: 12 }}>
      {edges.map((e, i) => {
        const from = nodes.find(n => n.id === e.from);
        const to   = nodes.find(n => n.id === e.to);
        if (!from || !to) return null;
        const [x1, y1] = toSVG(from.x, from.y);
        const [x2, y2] = toSVG(to.x, to.y);
        const isRoute = routeSet.has(e.from) && routeSet.has(e.to);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={isRoute ? "#00ff88" : "#333"} strokeWidth={isRoute ? 3 : 1} />;
      })}
      {nodes.map(n => {
        const [cx, cy] = toSVG(n.x, n.y);
        const isRoute   = routeSet.has(n.id);
        const isCurrent = n.id === currentNode;
        return (
          <g key={n.id}>
            <circle cx={cx} cy={cy} r={isCurrent ? 14 : 10}
              fill={isCurrent ? "#ff4757" : isRoute ? "#00ff88" : "#2f3542"}
              stroke={isRoute ? "#00ff88" : "#555"} strokeWidth={2} />
            <text x={cx} y={cy + 22} textAnchor="middle" fontSize="8"
              fill={isRoute ? "#fff" : "#888"}>
              {n.name.split(" ").slice(0, 2).join(" ")}
            </text>
          </g>
        );
      })}
      <circle cx={20} cy={486} r={6} fill="#ff4757" />
      <text x={30} y={490} fontSize="9" fill="#aaa">You</text>
      <circle cx={70} cy={486} r={6} fill="#00ff88" />
      <text x={80} y={490} fontSize="9" fill="#aaa">Route</text>
    </svg>
  );
}

export default function App() {
  const [tab, setTab]         = useState("nav");
  const [mapData, setMapData] = useState({ nodes: [], edges: [] });
  const [items, setItems]     = useState("");
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [product, setProduct] = useState("");
  const [scanResult, setScanResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/map`).then(r => r.json()).then(d => setMapData(d)).catch(() => {});
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

  async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    videoRef.current.srcObject = stream;
    videoRef.current.play();
    setScanning(true);
  }

  function captureAndScan() {
    const canvas = canvasRef.current, video = videoRef.current;
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(async blob => {
      const form = new FormData();
      form.append("product", product);
      form.append("file", blob, "frame.jpg");
      const res = await fetch(`${API}/scan`, { method: "POST", body: form });
      setScanResult(await res.json());
    }, "image/jpeg");
  }

  const currentNode = result?.route?.[currentStep] || "entrance_left";

  return (
    <div style={{ fontFamily: "sans-serif", background: "#0f0f1a", minHeight: "100vh", color: "#fff", padding: 20 }}>
      <h1 style={{ color: "#00ff88", marginBottom: 4 }}>WayfinderAI</h1>
      <p style={{ color: "#aaa", marginBottom: 20 }}>{mapData.store || "Connecting to store..."}</p>
      <SensorPanel />

      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        {["nav", "scan"].map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer",
              background: tab === t ? "#00ff88" : "#2f3542", color: tab === t ? "#000" : "#fff" }}>
            {t === "nav" ? "Navigate" : "Shelf Scanner"}
          </button>
        ))}
      </div>

      {tab === "nav" && (
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 280 }}>
            <input value={items} onChange={e => setItems(e.target.value)}
              placeholder="milk, pasta, chips"
              onKeyDown={e => e.key === "Enter" && navigate()}
              style={{ width: "100%", padding: 12, borderRadius: 8, border: "1px solid #333",
                background: "#1a1a2e", color: "#fff", fontSize: 16, marginBottom: 10 }} />
            <button onClick={navigate} disabled={loading}
              style={{ width: "100%", padding: 12, borderRadius: 8, border: "none",
                background: "#00ff88", color: "#000", fontSize: 16, cursor: "pointer", marginBottom: 20 }}>
              {loading ? "Finding route..." : "Get Directions"}
            </button>

            {result?.not_found?.length > 0 && (
              <p style={{ color: "#ff4757" }}>Not found: {result.not_found.join(", ")}</p>
            )}

            {result?.directions?.map((d, i) => (
              <div key={i} onClick={() => setCurrentStep(result.route.indexOf(d.target))}
                style={{ padding: 12, marginBottom: 8, borderRadius: 8, cursor: "pointer",
                  background: i === currentStep ? "#00ff8822" : "#1a1a2e",
                  border: `1px solid ${i === currentStep ? "#00ff88" : "#333"}` }}>
                <div style={{ color: "#00ff88", fontWeight: "bold" }}>{i + 1}. {d.name}</div>
                {d.walk.length > 0 && <div style={{ color: "#aaa", fontSize: 12 }}>Walk: {d.walk.join(" → ")}</div>}
                {d.items.map((item, j) => <div key={j} style={{ color: "#fff", fontSize: 13, marginTop: 4 }}>• {item}</div>)}
              </div>
            ))}
          </div>

          <div style={{ flex: 2, minWidth: 400 }}>
            <StoreMap nodes={mapData.nodes || []} edges={mapData.edges || []}
              route={result?.route || []} currentNode={currentNode} />
            {result && (
              <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
                <button onClick={() => setCurrentStep(s => Math.max(0, s - 1))}
                  style={{ flex: 1, padding: 10, borderRadius: 8, border: "none", background: "#2f3542", color: "#fff", cursor: "pointer" }}>← Prev</button>
                <button onClick={() => setCurrentStep(s => Math.min(result.route.length - 1, s + 1))}
                  style={{ flex: 1, padding: 10, borderRadius: 8, border: "none", background: "#2f3542", color: "#fff", cursor: "pointer" }}>Next →</button>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "scan" && (
        <div style={{ maxWidth: 500 }}>
          <input value={product} onChange={e => setProduct(e.target.value)}
            placeholder="Product name (e.g. milk)"
            style={{ width: "100%", padding: 12, borderRadius: 8, border: "1px solid #333",
              background: "#1a1a2e", color: "#fff", fontSize: 16, marginBottom: 10 }} />
          <button onClick={startCamera}
            style={{ width: "100%", padding: 12, borderRadius: 8, border: "none",
              background: "#2f3542", color: "#fff", fontSize: 16, cursor: "pointer", marginBottom: 10 }}>
            Start Camera
          </button>
          <video ref={videoRef} style={{ width: "100%", borderRadius: 8, display: scanning ? "block" : "none" }} />
          <canvas ref={canvasRef} style={{ display: "none" }} />
          {scanning && (
            <button onClick={captureAndScan}
              style={{ width: "100%", padding: 12, borderRadius: 8, border: "none",
                background: "#00ff88", color: "#000", fontSize: 16, cursor: "pointer", marginTop: 10 }}>
              Scan Shelf
            </button>
          )}
          {scanResult && (
            <div style={{ marginTop: 16, padding: 16, borderRadius: 8,
              background: scanResult.found ? "#00ff8822" : "#ff475722",
              border: `1px solid ${scanResult.found ? "#00ff88" : "#ff4757"}` }}>
              <p style={{ fontSize: 18, color: scanResult.found ? "#00ff88" : "#ff4757" }}>{scanResult.spoken}</p>
              {scanResult.found && <p style={{ color: "#aaa", fontSize: 13 }}>Confidence: {(scanResult.confidence * 100).toFixed(0)}%</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
