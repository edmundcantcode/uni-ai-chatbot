import { useState } from "react";
import axios from "axios";

export default function Chatbot() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const askQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
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

  return (
    <div style={{ padding: "2rem", fontFamily: "Arial, sans-serif" }}>
      <h2>🎓 University AI Chatbot</h2>
      <input
        type="text"
        placeholder="Ask something like: will 9897587 get honors?"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ width: "70%", padding: "0.5rem", marginRight: "1rem" }}
      />
      <button onClick={askQuery} disabled={loading}>
        {loading ? "Loading..." : "Ask"}
      </button>

      <div style={{ marginTop: "2rem" }}>
        {response && (
          <pre style={{ background: "#f0f0f0", padding: "1rem" }}>
            {JSON.stringify(response, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
