import { useState, useRef, useEffect } from "react";
import { apiService, API_BASE_URL } from "./api";

export default function Chatbot({ user, onLogout }) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      content: `Hello ${user.role === 'admin' ? 'Admin' : user.userid}! 👋 I'm your University AI assistant. How can I help you today?`,
      timestamp: new Date()
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const [connectionError, setConnectionError] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const askQuery = async () => {
    if (!query.trim()) return;
    
    // Add user message
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: query.trim(),
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    const currentQuery = query.trim();
    setQuery("");
    setLoading(true);
    setConnectionError(false);

    try {
      const response = await apiService.sendQuery(currentQuery, user.userid, user.role);
      
      // Add bot response
      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: response.message || "I've processed your query.",
        data: response,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      console.error("❌ Request failed:", err);
      setConnectionError(true);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: `❌ ${err.message.includes('fetch') ? 'Unable to connect to server. Please check if the backend is running.' : err.message}`,
        isError: true,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    }

    setLoading(false);
    setTimeout(() => inputRef.current?.focus(), 100);
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
    if (window.confirm("Are you sure you want to logout?")) {
      onLogout();
    }
  };

  const renderTable = (data) => {
    if (!Array.isArray(data) || data.length === 0) {
      return <p style={{ color: '#666', fontStyle: 'italic' }}>No results found.</p>;
    }

    const columns = Object.keys(data[0]);

    return (
      <div style={{ 
        maxHeight: "300px", 
        overflowY: "auto", 
        border: "1px solid #e0e0e0", 
        borderRadius: "8px",
        marginTop: "12px",
        backgroundColor: "#fafafa"
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
          <thead style={{ position: "sticky", top: 0, background: "#f5f5f5", zIndex: 1 }}>
            <tr>
              {columns.map((header) => (
                <th
                  key={header}
                  style={{ 
                    borderBottom: "2px solid #ddd", 
                    textAlign: "left", 
                    padding: "8px 12px", 
                    fontWeight: "600",
                    color: "#333"
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => (
              <tr key={rowIdx} style={{ 
                borderBottom: "1px solid #eee",
                backgroundColor: rowIdx % 2 === 0 ? "#fff" : "#f9f9f9"
              }}>
                {columns.map((col, colIdx) => (
                  <td key={colIdx} style={{ 
                    padding: "8px 12px", 
                    color: "#555"
                  }}>
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

  const handleChoiceClick = (choice, originalQuery) => {
    let modifiedQuery;
    
    if (originalQuery.toLowerCase().includes('subject')) {
      modifiedQuery = `show subjects for student ID ${choice.id}`;
    } else if (originalQuery.toLowerCase().includes('grade')) {
      modifiedQuery = `show grades for student ID ${choice.id}`;
    } else if (originalQuery.toLowerCase().includes('cgpa') || originalQuery.toLowerCase().includes('gpa')) {
      modifiedQuery = `show CGPA for student ID ${choice.id}`;
    } else {
      // Generic fallback - replace the name with "student ID X"
      modifiedQuery = originalQuery.replace(/([A-Z][a-z]+ [A-Z][a-z]+)/i, `student ID ${choice.id}`);
    }
    
    setQuery(modifiedQuery);
    setTimeout(() => askQuery(), 0);
  };

  const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const styles = {
    container: {
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#f8f9fa',
      fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif"
    },
    header: {
      backgroundColor: '#fff',
      padding: '16px 24px',
      borderBottom: '1px solid #e9ecef',
      boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    },
    headerTitle: {
      margin: 0,
      fontSize: '20px',
      fontWeight: '600',
      color: '#2c3e50',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    headerInfo: {
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      fontSize: '14px',
      color: '#6c757d'
    },
    userBadge: {
      backgroundColor: user.role === 'admin' ? '#dc3545' : '#007bff',
      color: 'white',
      padding: '4px 12px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: '500'
    },
    connectionStatus: {
      backgroundColor: connectionError ? '#dc3545' : '#28a745',
      color: 'white',
      padding: '4px 8px',
      borderRadius: '8px',
      fontSize: '11px',
      fontWeight: '500'
    },
    logoutBtn: {
      backgroundColor: '#6c757d',
      color: 'white',
      border: 'none',
      padding: '8px 16px',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      transition: 'background-color 0.2s'
    },
    chatContainer: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    },
    messagesContainer: {
      flex: 1,
      overflowY: 'auto',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    },
    messageWrapper: {
      display: 'flex',
      flexDirection: 'column',
      maxWidth: '70%'
    },
    userMessageWrapper: {
      alignSelf: 'flex-end',
      alignItems: 'flex-end'
    },
    botMessageWrapper: {
      alignSelf: 'flex-start',
      alignItems: 'flex-start'
    },
    message: {
      padding: '12px 16px',
      borderRadius: '18px',
      wordWrap: 'break-word',
      fontSize: '15px',
      lineHeight: '1.4'
    },
    userMessage: {
      backgroundColor: '#007bff',
      color: 'white',
      borderBottomRightRadius: '4px'
    },
    botMessage: {
      backgroundColor: '#fff',
      color: '#333',
      border: '1px solid #e9ecef',
      borderBottomLeftRadius: '4px'
    },
    errorMessage: {
      backgroundColor: '#f8d7da',
      color: '#721c24',
      border: '1px solid #f5c6cb'
    },
    timestamp: {
      fontSize: '11px',
      color: '#6c757d',
      marginTop: '4px'
    },
    dataContainer: {
      marginTop: '12px',
      padding: '16px',
      backgroundColor: '#f8f9fa',
      borderRadius: '12px',
      border: '1px solid #e9ecef'
    },
    queryInfo: {
      fontSize: '13px',
      color: '#6c757d',
      marginBottom: '8px'
    },
    choicesContainer: {
      marginTop: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    },
    choiceButton: {
      padding: '10px 14px',
      backgroundColor: '#fff3cd',
      color: '#856404',
      border: '1px solid #ffeeba',
      borderRadius: '8px',
      cursor: 'pointer',
      textAlign: 'left',
      fontSize: '14px',
      transition: 'all 0.2s'
    },
    actionButtons: {
      display: 'flex',
      gap: '8px',
      marginTop: '12px',
      flexWrap: 'wrap'
    },
    actionButton: {
      padding: '6px 12px',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '12px',
      fontWeight: '500',
      transition: 'all 0.2s'
    },
    exportButton: {
      backgroundColor: '#28a745',
      color: 'white'
    },
    debugButton: {
      backgroundColor: '#6c757d',
      color: 'white'
    },
    cqlButton: {
      backgroundColor: '#17a2b8',
      color: 'white'
    },
    inputContainer: {
      backgroundColor: '#fff',
      padding: '20px',
      borderTop: '1px solid #e9ecef'
    },
    inputWrapper: {
      display: 'flex',
      gap: '12px',
      alignItems: 'flex-end',
      maxWidth: '1200px',
      margin: '0 auto'
    },
    input: {
      flex: 1,
      padding: '12px 16px',
      fontSize: '15px',
      border: '1px solid #ced4da',
      borderRadius: '24px',
      outline: 'none',
      resize: 'none',
      fontFamily: 'inherit'
    },
    sendButton: {
      backgroundColor: '#007bff',
      color: 'white',
      border: 'none',
      padding: '12px 24px',
      borderRadius: '24px',
      cursor: 'pointer',
      fontSize: '15px',
      fontWeight: '500',
      transition: 'all 0.2s',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    sendButtonDisabled: {
      backgroundColor: '#6c757d',
      cursor: 'not-allowed'
    },
    typingIndicator: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '12px 16px',
      backgroundColor: '#f8f9fa',
      borderRadius: '18px',
      border: '1px solid #e9ecef',
      color: '#6c757d',
      fontSize: '14px'
    },
    debugContainer: {
      marginTop: '12px',
      padding: '12px',
      backgroundColor: '#f8f9fa',
      border: '1px solid #e9ecef',
      borderRadius: '8px',
      fontSize: '12px',
      fontFamily: 'monospace',
      whiteSpace: 'pre-wrap',
      maxHeight: '200px',
      overflowY: 'auto'
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.headerTitle}>
          🤖 University AI Assistant
        </h1>
        <div style={styles.headerInfo}>
          <div style={styles.connectionStatus}>
            {connectionError ? '🔴 Disconnected' : '🟢 Connected'}
          </div>
          <span style={styles.userBadge}>
            {user.role === 'admin' ? '👨‍💼 Admin' : '🎓 Student'} - {user.userid}
          </span>
          <button 
            style={styles.logoutBtn}
            onClick={logout}
            onMouseOver={(e) => e.target.style.backgroundColor = '#5a6268'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#6c757d'}
          >
            Logout
          </button>
        </div>
      </div>

      {/* Chat Container */}
      <div style={styles.chatContainer}>
        {/* Messages */}
        <div style={styles.messagesContainer}>
          {messages.map((message) => (
            <div
              key={message.id}
              style={{
                ...styles.messageWrapper,
                ...(message.type === 'user' ? styles.userMessageWrapper : styles.botMessageWrapper)
              }}
            >
              <div
                style={{
                  ...styles.message,
                  ...(message.type === 'user' ? styles.userMessage : styles.botMessage),
                  ...(message.isError ? styles.errorMessage : {})
                }}
              >
                {message.content}
                
                {/* Data display for bot messages */}
                {message.data && (
                  <div style={styles.dataContainer}>
                    {message.data.query && (
                      <div style={styles.queryInfo}>
                        <strong>Query:</strong> {message.data.processed_query || message.data.query}
                      </div>
                    )}
                    
                    {/* Clarification choices */}
                    {message.data.clarification && message.data.choices?.length > 0 && (
                      <div style={styles.choicesContainer}>
                        <strong style={{ fontSize: '14px', color: '#495057' }}>Please select:</strong>
                        {message.data.choices.map((choice, index) => (
                          <button
                            key={index}
                            style={styles.choiceButton}
                            onClick={() => handleChoiceClick(choice, message.data.query)}
                            onMouseOver={(e) => e.target.style.backgroundColor = '#ffeaa7'}
                            onMouseOut={(e) => e.target.style.backgroundColor = '#fff3cd'}
                          >
                            {choice.id} — {choice.programme} (Cohort {choice.cohort})
                          </button>
                        ))}
                      </div>
                    )}
                    
                    {/* Results table */}
                    {message.data.result && renderTable(message.data.result)}
                    
                    {/* Verification */}
                    {message.data.verification && (
                      <div style={{ 
                        marginTop: '12px', 
                        padding: '8px 12px', 
                        backgroundColor: '#d4edda', 
                        color: '#155724',
                        borderRadius: '6px',
                        fontSize: '13px'
                      }}>
                        ✅ {message.data.verification}
                      </div>
                    )}
                    
                    {/* Action buttons */}
                    <div style={styles.actionButtons}>
                      {message.data.result && (
                        <button
                          style={{...styles.actionButton, ...styles.exportButton}}
                          onClick={() => downloadCSV(message.data.result, 'results.csv')}
                          onMouseOver={(e) => e.target.style.backgroundColor = '#218838'}
                          onMouseOut={(e) => e.target.style.backgroundColor = '#28a745'}
                        >
                          📥 Export CSV
                        </button>
                      )}
                      
                      {message.data.cql && (
                        <button
                          style={{...styles.actionButton, ...styles.cqlButton}}
                          onClick={() => {
                            const debugDiv = document.getElementById(`debug-${message.id}`);
                            if (debugDiv) {
                              debugDiv.style.display = debugDiv.style.display === 'none' ? 'block' : 'none';
                            }
                          }}
                          onMouseOver={(e) => e.target.style.backgroundColor = '#138496'}
                          onMouseOut={(e) => e.target.style.backgroundColor = '#17a2b8'}
                        >
                          🔍 Show CQL
                        </button>
                      )}
                    </div>
                    
                    {/* Debug info */}
                    {message.data.cql && (
                      <div id={`debug-${message.id}`} style={{...styles.debugContainer, display: 'none'}}>
                        <strong>Generated CQL:</strong><br/>
                        {message.data.cql}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div style={{
                ...styles.timestamp,
                ...(message.type === 'user' ? { textAlign: 'right' } : { textAlign: 'left' })
              }}>
                {formatTime(message.timestamp)}
              </div>
            </div>
          ))}
          
          {/* Typing indicator */}
          {loading && (
            <div style={styles.botMessageWrapper}>
              <div style={styles.typingIndicator}>
                <div style={{
                  display: 'flex',
                  gap: '4px'
                }}>
                  <div style={{
                    width: '6px',
                    height: '6px',
                    backgroundColor: '#007bff',
                    borderRadius: '50%',
                    animation: 'typing 1.4s infinite ease-in-out'
                  }}></div>
                  <div style={{
                    width: '6px',
                    height: '6px',
                    backgroundColor: '#007bff',
                    borderRadius: '50%',
                    animation: 'typing 1.4s infinite ease-in-out',
                    animationDelay: '0.2s'
                  }}></div>
                  <div style={{
                    width: '6px',
                    height: '6px',
                    backgroundColor: '#007bff',
                    borderRadius: '50%',
                    animation: 'typing 1.4s infinite ease-in-out',
                    animationDelay: '0.4s'
                  }}></div>
                </div>
                AI is thinking...
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input */}
        <div style={styles.inputContainer}>
          <div style={styles.inputWrapper}>
            <textarea
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  askQuery();
                }
              }}
              placeholder="Ask me anything about university data... (Press Enter to send)"
              style={styles.input}
              rows={1}
              disabled={loading}
            />
            <button
              onClick={askQuery}
              disabled={loading || !query.trim()}
              style={{
                ...styles.sendButton,
                ...(loading || !query.trim() ? styles.sendButtonDisabled : {})
              }}
              onMouseOver={(e) => {
                if (!loading && query.trim()) {
                  e.target.style.backgroundColor = '#0056b3';
                }
              }}
              onMouseOut={(e) => {
                if (!loading && query.trim()) {
                  e.target.style.backgroundColor = '#007bff';
                }
              }}
            >
              {loading ? '⏳' : '📤'} {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
      
      {/* Debug toggle */}
      <button
        onClick={() => setShowDebug(!showDebug)}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          ...styles.actionButton,
          ...styles.debugButton,
          borderRadius: '50%',
          width: '50px',
          height: '50px',
          fontSize: '16px'
        }}
        onMouseOver={(e) => e.target.style.backgroundColor = '#5a6268'}
        onMouseOut={(e) => e.target.style.backgroundColor = '#6c757d'}
      >
        🐛
      </button>
      
      {/* Debug panel */}
      {showDebug && (
        <div style={{
          position: 'fixed',
          bottom: '80px',
          right: '20px',
          width: '300px',
          maxHeight: '400px',
          backgroundColor: '#fff',
          border: '1px solid #ccc',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          zIndex: 1000
        }}>
          <div style={{
            padding: '12px',
            borderBottom: '1px solid #eee',
            fontWeight: '600',
            fontSize: '14px'
          }}>
            Debug Info
          </div>
          <div style={{
            padding: '12px',
            fontSize: '12px',
            fontFamily: 'monospace',
            maxHeight: '300px',
            overflowY: 'auto'
          }}>
            <strong>Backend URL:</strong><br/>
            {API_BASE_URL}<br/><br/>
            <strong>Connection Status:</strong><br/>
            {connectionError ? 'Disconnected' : 'Connected'}<br/><br/>
            <strong>Last Response:</strong><br/>
            {JSON.stringify(messages[messages.length - 1]?.data || {}, null, 2)}
          </div>
        </div>
      )}
      
      <style>{`
        @keyframes typing {
          0%, 60%, 100% {
            transform: translateY(0);
          }
          30% {
            transform: translateY(-10px);
          }
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
          width: 6px;
        }
        
        ::-webkit-scrollbar-track {
          background: #f1f1f1;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #c1c1c1;
          border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #a1a1a1;
        }
      `}</style>
    </div>
  );
}