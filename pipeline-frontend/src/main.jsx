import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Pipeline from "@src/Pipeline";

function App() {
  return (
    <div style={{ fontFamily: "'Inter', -apple-system, sans-serif", minHeight: "100vh", background: "#f1f4f8" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 28px", borderBottom: "1px solid #e2e6ea",
        background: "#fff", boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 1 }}>
          <span style={{ fontSize: 20, fontWeight: 800, color: "#2563eb", letterSpacing: -0.5 }}>Wayfinder</span>
          <span style={{ fontSize: 20, fontWeight: 300, color: "#64748b", letterSpacing: -0.5 }}>AI</span>
        </div>
        <span style={{ fontSize: 12, color: "#2563eb", padding: "4px 12px", background: "#eff6ff", borderRadius: 20, fontWeight: 600, border: "1px solid #bfdbfe" }}>Full Pipeline</span>
      </div>
      <Pipeline />
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><App /></StrictMode>
);
