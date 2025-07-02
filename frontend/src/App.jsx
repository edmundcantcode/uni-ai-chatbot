import { useEffect, useState } from "react";
import axios from "axios";
import Chatbot from "./Chatbot";
import LoginPage from "./LoginPage";

function App() {
  const [user, setUser] = useState(null);

  // Restore session on page load
  useEffect(() => {
    const saved = localStorage.getItem("user");
    if (saved) {
      setUser(JSON.parse(saved));
    }
  }, []);

  return user ? <Chatbot user={user} /> : <LoginPage setUser={setUser} />;
}

export default App;
