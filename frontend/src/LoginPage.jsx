import { useState } from "react";
import axios from "axios";

export default function LoginPage({ setUser }) {
  const [userid, setUserid] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setError(""); // clear previous error
    try {
      const res = await axios.post("http://localhost:8000/login", {
        userid,
        password,
      });

      if (res.status === 200 && res.data?.userid && res.data?.role) {
        const user = res.data;
        setUser(user);
        localStorage.setItem("user", JSON.stringify(user));
        window.location.href = "/chatbot";  // or use navigate("/chatbot") if using React Router
      } else {
        setError("❌ Invalid response from server");
      }
    } catch (err) {
      setError("❌ Invalid ID or password");
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Login</h2>

      <input
        type="text"
        placeholder="User ID"
        value={userid}
        onChange={(e) => setUserid(e.target.value)}
        style={styles.input}
      />

      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={styles.input}
      />

      <button onClick={handleLogin} style={styles.button}>
        Sign In
      </button>

      {error && <p style={styles.error}>{error}</p>}
    </div>
  );
}

const styles = {
  container: {
    maxWidth: 400,
    margin: "5rem auto",
    padding: "2rem",
    border: "1px solid #ddd",
    borderRadius: "8px",
    textAlign: "center",
    fontFamily: "Arial, sans-serif",
  },
  title: {
    marginBottom: "2rem",
  },
  input: {
    display: "block",
    width: "100%",
    padding: "0.5rem",
    marginBottom: "1rem",
    borderRadius: "4px",
    border: "1px solid #ccc",
    fontSize: "1rem",
  },
  button: {
    width: "100%",
    padding: "0.75rem",
    fontSize: "1rem",
    backgroundColor: "#007bff",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
  },
  error: {
    color: "red",
    marginTop: "1rem",
  },
};
