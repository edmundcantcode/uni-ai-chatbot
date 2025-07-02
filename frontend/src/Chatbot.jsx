import { useState } from "react";
import axios from "axios";

export default function Chatbot({ user }) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCQL, setShowCQL] = useState(false);
  const [showDebug, setShowDebug] = useState(false);

  const askQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResponse(null);

    try {
      const res = await axios.post("http://localhost:8000/chatbot", {
        query: query.trim(),
        userid: user.userid,
        role: user.role
      });
      setResponse(res.data);
    } catch (err) {
      console.error("❌ Request failed:", err);
      if (err.response?.data?.error) {
        setResponse({ error: err.response.data.error });
      } else {
        setResponse({ error: "❌ Unexpected error occurred." });
      }
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

  const logout = () => {
    localStorage.removeItem("user");
    window.location.reload();
  };

  const renderTable = (data) => {
    if (!Array.isArray(data) || data.length === 0) {
      return <p>No results found.</p>;
    }

    const columns = Object.keys(data[0]);

    return (
      <div style={{ maxHeight: "400px", overflowY: "auto", border: "1px solid #ccc", borderRadius: "6px" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ position: "sticky", top: 0, background: "#fff", zIndex: 1 }}>
            <tr>
              {columns.map((header) => (
                <th
                  key={header}
                  style={{ borderBottom: "1px solid #ccc", textAlign: "left", padding: "0.5rem", background: "#f0f0f0" }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {columns.map((col, colIdx) => (
                  <td key={colIdx} style={{ padding: "0.5rem", borderBottom: "1px solid #eee" }}>
                    {row[col]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "'Segoe UI', sans-serif", maxWidth: "900px", margin: "auto" }}>
      <h2 style={{ fontSize: "1.8rem", marginBottom: "0.5rem" }}>
        🎓 University AI Chatbot
      </h2>
      <h3 style={{ fontSize: "1.5rem", marginBottom: "1.5rem", color: "#444" }}>
        {user.role === "admin"
          ? "👋 Hi admin"
          : `👋 Hi student ${user.userid}`}
      </h3>
      <p style={{ marginBottom: "0.5rem" }}>
        Logged in as: <strong>{user.role}</strong> ({user.userid})
      </p>
      <button onClick={logout} style={{
        marginBottom: "1.5rem",
        background: "#dc3545",
        color: "white",
        border: "none",
        padding: "0.4rem 0.8rem",
        borderRadius: "6px",
        cursor: "pointer"
      }}>
        Logout
      </button>

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

      {response?.message && (
        <div style={{
          background: "#e6f4ea",
          border: "1px solid #b6dfc2",
          borderRadius: "8px",
          padding: "1.5rem",
          marginBottom: "1rem",
          fontSize: "1.1rem",
          color: "#245f36"
        }}>
          <p><strong>Original query:</strong> {response.query}</p>
          <p><strong>Processed query:</strong> {response.processed_query}</p>
          <p style={{ marginTop: "1rem" }}>{response.message}</p>
        </div>
      )}

      {response?.clarification && response?.choices?.length > 0 && (
        <div style={{
          background: "#fff3cd",
          border: "1px solid #ffeeba",
          padding: "1rem",
          borderRadius: "8px",
          marginBottom: "1rem"
        }}>
          <p><strong>{response.message}</strong></p>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {response.choices.map((choice) => (
              <li key={choice.id} style={{ margin: "0.5rem 0" }}>
                <button
                  onClick={() => {
                    const modifiedQuery = query.replace(/([A-Z][a-z]+ [A-Z][a-z]+)/, choice.id);
                    setQuery(modifiedQuery);
                    setTimeout(() => askQuery(), 0);
                  }}
                  style={{
                    padding: "0.5rem 1rem",
                    background: "#ffc107",
                    color: "#000",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "left"
                  }}
                >
                  {choice.id} — {choice.programme} (Cohort {choice.cohort})
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {response?.result && (
        <div style={{ background: "#f9f9f9", padding: "1.5rem", marginBottom: "1rem", border: "1px solid #ddd", borderRadius: "10px", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
          <p><strong>Original query:</strong> {response.query}</p>
          <p><strong>Processed query:</strong> {response.processed_query}</p>

          <button
            onClick={() => setShowCQL(!showCQL)}
            style={{ margin: "0.5rem 0", background: "#6c757d", color: "white", padding: "0.4rem 0.8rem", border: "none", borderRadius: "6px", cursor: "pointer" }}
          >
            {showCQL ? "Hide CQL" : "Show CQL"}
          </button>

          {showCQL && (
            <p style={{ marginTop: "0.5rem", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
              <strong>Generated CQL:</strong><br />
              <code>{response.cql}</code>
            </p>
          )}

          {renderTable(response.result)}

          {response?.verification && (
            <div style={{ marginTop: "1rem", fontStyle: "italic", color: "#1a5d1a" }}>
              ✅ LLM Check: {response.verification}
            </div>
          )}

          <button
            onClick={() => downloadCSV(response.result, `result.csv`)}
            style={{ marginTop: "1rem", background: "#28a745", color: "white", padding: "0.5rem 1rem", border: "none", borderRadius: "6px", cursor: "pointer" }}
          >
            📥 Export CSV
          </button>
        </div>
      )}

      <button
        onClick={() => setShowDebug(!showDebug)}
        style={{ marginTop: "1rem", background: "#888", color: "white", padding: "0.4rem 0.8rem", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem" }}
      >
        {showDebug ? "Hide JSON Debug" : "Show JSON Debug"}
      </button>

      {showDebug && (
        <pre style={{ fontSize: "0.8rem", color: "#555", marginTop: "1rem", background: "#f5f5f5", padding: "1rem", borderRadius: "8px", overflowX: "auto" }}>
          {JSON.stringify(response, null, 2)}
        </pre>
      )}
    </div>
  );
}
