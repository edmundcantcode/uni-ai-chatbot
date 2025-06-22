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

  // Extract only the final explanation after </think>
  const getCleanExplanation = (text) => {
    if (!text) return "";
    const split = text.split("</think>");
    return split.length > 1 ? split[1].trim() : text.trim();
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "'Segoe UI', sans-serif", maxWidth: "900px", margin: "auto" }}>
      <h2 style={{ fontSize: "1.8rem", marginBottom: "1rem" }}>🎓 University AI Chatbot</h2>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
        <input
          type="text"
          placeholder="Ask something like: will Diana Brown get Class I honors?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && askQuery()}
          style={{
            flex: 1,
            padding: "0.75rem 1rem",
            fontSize: "1rem",
            border: "1px solid #ccc",
            borderRadius: "8px",
          }}
        />
        <button
          onClick={askQuery}
          disabled={loading}
          style={{
            padding: "0.75rem 1.5rem",
            fontSize: "1rem",
            background: "#007bff",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
          }}
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {response?.error && (
        <div style={{ background: "#ffe0e0", padding: "1rem", borderRadius: "6px", color: "#900" }}>
          ❌ {response.error}
        </div>
      )}

      {response?.results && response.results.map((res, idx) => (
        <div key={idx} style={{
          background: "#f9f9f9",
          padding: "1.5rem",
          marginBottom: "1rem",
          border: "1px solid #ddd",
          borderRadius: "10px",
          boxShadow: "0 2px 4px rgba(0,0,0,0.05)"
        }}>
          {res.error ? (
            <p style={{ color: "#c00" }}>⚠️ {res.error}</p>
          ) : (
            <>
              <p><strong>📌 Student ID:</strong> {res.student_id}</p>
              <p><strong>📊 CGPA:</strong> {res.cgpa}</p>
              <p><strong>🎓 Honors Class:</strong> {res.honors_class}</p>

              {res.explanation && (
                <details style={{ marginTop: "1rem", cursor: "pointer" }}>
                  <summary style={{ fontWeight: "bold" }}>📝 Show Explanation</summary>
                  <p style={{ marginTop: "0.75rem" }}>
                    {getCleanExplanation(res.explanation)}
                  </p>
                </details>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
