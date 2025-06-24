import { useState } from "react";
import axios from "axios";

export default function Chatbot() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const askQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResponse(null);
    try {
      const res = await axios.post("http://localhost:8000/chatbot", {
        query: query.trim(),
      });
      setResponse(res.data);
    } catch (err) {
      console.error("❌ Error:", err);
      setResponse({ error: "Failed to fetch response." });
    }
    setLoading(false);
  };

  const downloadCSV = (data, filename) => {
    const keys = Object.keys(data[0]);
    const csv = [keys.join(",")].concat(
      data.map((row) => keys.map((k) => JSON.stringify(row[k] || "")).join(","))
    ).join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  };

  const renderTable = (data) => {
    if (!Array.isArray(data) || data.length === 0) {
      return <p>No results found.</p>;
    }

    const columns = Object.keys(data[0]);
    return (
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "1rem" }}>
        <thead>
          <tr>
            {columns.map((header) => (
              <th key={header} style={{ borderBottom: "1px solid #ccc", textAlign: "left", padding: "0.5rem" }}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {columns.map((col, colIdx) => (
                <td key={colIdx} style={{ padding: "0.5rem", borderBottom: "1px solid #eee" }}>{row[col]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "'Segoe UI', sans-serif", maxWidth: "900px", margin: "auto" }}>
      <h2 style={{ fontSize: "1.8rem", marginBottom: "1rem" }}>🎓 University AI Chatbot</h2>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
        <input
          type="text"
          placeholder="Ask something like: show subjects for Bob Johnson"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && askQuery()}
          style={{ flex: 1, padding: "0.75rem 1rem", fontSize: "1rem", border: "1px solid #ccc", borderRadius: "8px" }}
        />
        <button
          onClick={askQuery}
          disabled={loading}
          style={{ padding: "0.75rem 1.5rem", fontSize: "1rem", background: "#007bff", color: "white", border: "none", borderRadius: "8px", cursor: "pointer" }}
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {response?.error && (
        <div style={{ background: "#ffe0e0", padding: "1rem", borderRadius: "6px", color: "#900" }}>
          ❌ {response.error}
        </div>
      )}

      {response?.result && (
        <div style={{ background: "#f9f9f9", padding: "1.5rem", marginBottom: "1rem", border: "1px solid #ddd", borderRadius: "10px", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
          <p><strong>Original query:</strong> {response.query}</p>
          <p><strong>Processed query:</strong> {response.processed_query}</p>
          <p><strong>Generated CQL:</strong> <code>{response.cql}</code></p>

          {renderTable(response.result)}

          <button
            onClick={() => downloadCSV(response.result, `result.csv`)}
            style={{ marginTop: "1rem", background: "#28a745", color: "white", padding: "0.5rem 1rem", border: "none", borderRadius: "6px", cursor: "pointer" }}
          >
            📥 Export CSV
          </button>
        </div>
      )}
    </div>
  );
}
