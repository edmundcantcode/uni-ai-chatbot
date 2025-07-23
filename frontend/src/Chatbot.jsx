import React, { useState, useRef, useEffect } from "react";

// Real API service - no mock data
const apiService = {
  async sendQuery(query, userid, role, clarification = null) {
    const url = "http://localhost:8000/api/chatbot";  // Fixed endpoint
    
    const requestBody = {
      query: query,
      userid: userid,
      role: role
    };
    
    // Add clarification if provided
    if (clarification) {
      requestBody.clarification = clarification;  // Backend expects 'clarification' field
    }
    
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const data = await response.json();
      console.log("RAW_FROM_SERVER 👉", data);
      
      return data; // <-- now askQuery gets {success:true, message:'...', data:[...], ...}
    } catch (error) {
      console.error('API call failed:', error);
      return {
        success: false,
        message: error.message,
        data: [],
        error: true
      };
    }
  }
};

// Helper function to build human-readable text from response data
function buildBotText(d) {
  if (!d) return "Query processed.";
  if (d.message) return d.message;
  
  // nested count: d.data => [ [ {count:2129} ], {…meta…} ]
  const nestedCount = Array.isArray(d.data) && Array.isArray(d.data[0]) && d.data[0][0]?.count;
  const count = typeof d.count === "number" ? d.count : nestedCount;
  
  if (typeof count === "number") {
    const noun = /active|enrolled|current/i.test(d.intent || "") ? "currently enrolled students" : "students";
    return `📊 **${count.toLocaleString()}** ${noun}.`;
  }
  
  if (Array.isArray(d.data)) {
    // if it is the [rows, meta] pattern, show rows length
    const rows = Array.isArray(d.data[0]) ? d.data[0] : d.data;
    if (Array.isArray(rows)) {
      return `📋 Returned ${rows.length.toLocaleString()} rows.`;
    }
  }
  
  return "Query processed.";
}

export default function EnhancedChatbot({ user = { userid: "demo", role: "student" }, onLogout = () => {} }) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      content: `Hello ${user.role === 'admin' ? 'Admin' : user.userid}! 👋 I'm your University AI assistant with semantic understanding. How can I help you today?`,
      timestamp: new Date()
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const [connectionError, setConnectionError] = useState(false);
  
  // State for handling clarifications
  const [pendingClarification, setPendingClarification] = useState(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    console.log("MESSAGES STATE ▶", messages);
    scrollToBottom();
  }, [messages]);

  // Unwrapping helper for backend responses
  const unwrapBackend = (r) => {
    // r is whatever apiService.sendQuery returned
    if (!r) return null;
    if (r.success !== undefined) return r; // already real payload
    if (r.data && r.data.success !== undefined) return r.data; // unwrap {status:'success', data:{…}}
    return r.data || r; // last resort
  };

  const buildBotText = (d) => {
    if (!d) return "Query processed.";
    if (d.message) return d.message;
    
    // nested count: d.data => [ [ {count:2129} ], {…meta…} ]
    const nestedCount = Array.isArray(d.data) && Array.isArray(d.data[0]) && d.data[0][0]?.count;
    const count = typeof d.count === "number" ? d.count : nestedCount;
    
    if (typeof count === "number") {
      const noun = /active|enrolled|current/i.test(d.intent || "") ? "currently enrolled students" : "students";
      return `📊 **${count.toLocaleString()}** ${noun}.`;
    }
    
    if (Array.isArray(d.data)) {
      // if it is the [rows, meta] pattern, show rows length
      const rows = Array.isArray(d.data[0]) ? d.data[0] : d.data;
      if (Array.isArray(rows)) {
        return `📋 Returned ${rows.length.toLocaleString()} rows.`;
      }
    }
    
    return "Query processed.";
  };

  const askQuery = async (queryText = null, clarification = null) => {
    const currentQuery = queryText || query.trim();
    if (!currentQuery && !clarification) return;
    
    // Add user message (only if not a clarification)
    if (!clarification) {
      const userMessage = {
        id: Date.now(),
        type: 'user',
        content: currentQuery,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, userMessage]);
      setQuery("");
    }
    
    setLoading(true);
    setConnectionError(false);
    setPendingClarification(null);

    try {
      // Call the API service
      const raw = await apiService.sendQuery(currentQuery, user.userid, user.role, clarification);
      console.log("RAW_FROM_SERVER 👉", raw);
      
      const payload = unwrapBackend(raw);
      console.log("UNWRAPPED_PAYLOAD 👉", payload);
      
      const needsClarification = payload?.intent === "clarify_column" && payload?.options;
      const botText = needsClarification
        ? (payload.message || "I need clarification to process your query.")
        : buildBotText(payload);
      
      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: botText,
        data: payload,
        needsClarification,
        success: payload?.success,
        isError: raw?.status === 'error' || payload?.error,
        timestamp: new Date()
      };
      
      console.log("BOT_MESSAGE_BEFORE_SET ▶", botMessage);
      
      // Handle clarification
      if (needsClarification && payload?.options) {
        setPendingClarification({
          query: currentQuery,
          options: payload.options,
          ambiguous_terms: payload.ambiguous_terms || [],
          message: payload.message
        });
      }
      
      setMessages(prev => [...prev, botMessage]);
      
    } catch (err) {
      console.error("❌ Request failed:", err);
      setConnectionError(true);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: `❌ ${err.message.includes('fetch') ? 'Unable to connect to server. Please check if the backend is running on port 8000.' : err.message}`,
        isError: true,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    }

    setLoading(false);
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  // Handle clarification choice
  const handleClarification = async (choice) => {
    if (!pendingClarification) return;
    
    // Add user's choice as a message
    const choiceMessage = {
      id: Date.now(),
      type: 'user', 
      content: `I meant: ${choice.description} (${choice.value})`,
      timestamp: new Date(),
      isClarification: true
    };
    setMessages(prev => [...prev, choiceMessage]);
    
    // Send clarification back to backend
    const clarificationPayload = {
      column: choice.column,
      value: choice.value
    };
    
    await askQuery(pendingClarification.query, clarificationPayload);
  };

  const downloadCSV = (data, filename) => {
    if (!Array.isArray(data) || data.length === 0) {
      alert("No data to export");
      return;
    }

    const keys = Object.keys(data[0]);
    const csv = [keys.join(",")].concat(
      data.map((row) => keys.map((k) => {
        const value = row[k];
        if (value === null || value === undefined) return '""';
        const stringValue = String(value);
        if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
          return `"${stringValue.replace(/"/g, '""')}"`;
        }
        return stringValue;
      }).join(","))
    ).join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    if (navigator.msSaveBlob) {
      navigator.msSaveBlob(blob, filename);
    } else {
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  const logout = () => {
    if (window.confirm("Are you sure you want to logout?")) {
      onLogout();
    }
  };

  const parseMessage = (content, data) => {
    if (!content) return { text: "", hasIntent: false, hasStats: false };
    
    const hasSemanticData = data && (data.intent || data.semantic_entities);
    const sections = content.split('\n\n');
    let mainText = content;
    
    const importantSections = sections.filter(section => 
      section.match(/^[📊🎓💰🌍👥🚻📈📚🎯✅❌🔒👨‍💼]/));
    
    return { 
      text: mainText, 
      hasIntent: hasSemanticData,
      hasStats: data && (data.count > 0 || data.execution_time),
      importantSections
    };
  };

  // Render clarification options
  const renderClarificationOptions = (options) => {
    return (
      <div style={styles.clarificationContainer}>
        <div style={styles.clarificationHeader}>
          🤔 Please clarify what you meant:
        </div>
        <div style={styles.clarificationOptions}>
          {options.map((option, index) => (
            <button
              key={index}
              style={styles.clarificationButton}
              onClick={() => handleClarification(option)}
              onMouseOver={(e) => e.target.style.backgroundColor = '#e3f2fd'}
              onMouseOut={(e) => e.target.style.backgroundColor = '#f8f9fa'}
            >
              <div style={styles.clarificationButtonIcon}>
                {option.column === 'programme' ? '🎓' : '📚'}
              </div>
              <div style={styles.clarificationButtonContent}>
                <div style={styles.clarificationButtonTitle}>
                  {option.column === 'programme' ? 'Programme' : 'Subject'}
                </div>
                <div style={styles.clarificationButtonValue}>
                  {option.value}
                </div>
                <div style={styles.clarificationButtonDesc}>
                  {option.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  };

  const renderFormattedMessage = (content, data, needsClarification) => {
    const parsed = parseMessage(content, data);
    
    return (
      <div>
        {/* Semantic Intent & Entity Info */}
        {data && data.intent && (
          <div style={styles.semanticHeader}>
            <span style={styles.intentBadge}>
              🧠 {data.intent.replace(/_/g, ' ').toUpperCase()}
            </span>
            {data.semantic_entities && Object.keys(data.semantic_entities).length > 0 && (
              <span style={styles.entityBadge}>
                🎯 Entities Detected
              </span>
            )}
            {data.execution_time && (
              <span style={styles.timeBadge}>
                ⚡ {(data.execution_time * 1000).toFixed(0)}ms
              </span>
            )}
          </div>
        )}
        
        {/* Main Message Content */}
        <div style={styles.messageContent}>
          {content.split('\n').map((line, i) => {
            if (!line.trim()) return <br key={i} />;
            
            if (line.match(/^\*\*.*\*\*$/)) {
              return (
                <div key={i} style={styles.messageHeader}>
                  {line.replace(/\*\*/g, '')}
                </div>
              );
            }
            
            if (line.match(/^[📊🎓💰🌍👥🚻📈📚🎯✅❌🔒👨‍💼]/)) {
              return (
                <div key={i} style={styles.highlightedLine}>
                  {line}
                </div>
              );
            }
            
            return (
              <div key={i} style={styles.regularLine}>
                {line}
              </div>
            );
          })}
        </div>
        
        {/* Clarification Options */}
        {needsClarification && data && data.options && (
          renderClarificationOptions(data.options)
        )}
        
        {/* Stats Footer */}
        {data && (data.count !== undefined || data.execution_time) && (
          <div style={styles.statsFooter}>
            {data.count !== undefined && (
              <span>📋 <strong>{data.count.toLocaleString()}</strong> records</span>
            )}
            {data.execution_time && (
              <span>⚡ <strong>{(data.execution_time * 1000).toFixed(0)}ms</strong></span>
            )}
            {data.security_level && (
              <span>🔐 <strong>{data.security_level}</strong> access</span>
            )}
          </div>
        )}
        
        {/* Semantic Entities Debug */}
        {data && data.semantic_entities && Object.keys(data.semantic_entities).length > 0 && (
          <div style={styles.entitiesContainer}>
            <details style={styles.entitiesDetails}>
              <summary style={styles.entitiesSummary}>🧠 Detected Entities</summary>
              <div style={styles.entitiesList}>
                {Object.entries(data.semantic_entities).map(([key, value]) => (
                  <div key={key} style={styles.entityItem}>
                    <strong>{key}:</strong> {JSON.stringify(value)}
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </div>
    );
  };

  const renderTable = (data) => {
    if (!Array.isArray(data) || data.length === 0) {
      return (
        <div style={styles.noResults}>
          <div style={styles.noResultsIcon}>📄</div>
          <div style={styles.noResultsText}>No results found</div>
        </div>
      );
    }

    const allKeys = new Set();
    data.forEach(row => {
      Object.keys(row).forEach(key => allKeys.add(key));
    });
    const columns = Array.from(allKeys);

    columns.sort((a, b) => {
      if (a === 'id') return -1;
      if (b === 'id') return 1;
      if (a === 'name') return -1;
      if (b === 'name') return 1;
      return a.localeCompare(b);
    });

    return (
      <div style={styles.tableContainer}>
        <div style={styles.tableHeader}>
          <div>
            📊 <strong>{data.length.toLocaleString()}</strong> results found
          </div>
          <button
            style={styles.exportButton}
            onClick={() => downloadCSV(data, `results_${new Date().toISOString().slice(0,10)}.csv`)}
            title="Export all data to CSV file"
          >
            📥 Export CSV
          </button>
        </div>
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead style={styles.tableHead}>
              <tr>
                {columns.map((header) => (
                  <th key={header} style={styles.tableHeaderCell}>
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 100).map((row, rowIdx) => (
                <tr 
                  key={rowIdx} 
                  style={{
                    ...styles.tableRow,
                    backgroundColor: rowIdx % 2 === 0 ? '#fff' : '#f8f9fa'
                  }}
                >
                  {columns.map((col, colIdx) => (
                    <td key={`${rowIdx}-${colIdx}`} style={styles.tableCell}>
                      {row[col] !== null && row[col] !== undefined ? String(row[col]) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > 100 && (
            <div style={styles.tableFooter}>
              Showing first 100 of {data.length.toLocaleString()} results. Export CSV to see all data.
            </div>
          )}
        </div>
      </div>
    );
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
      gap: '20px'
    },
    messageWrapper: {
      display: 'flex',
      flexDirection: 'column',
      maxWidth: '85%'
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
      padding: '16px 20px',
      borderRadius: '16px',
      wordWrap: 'break-word',
      fontSize: '15px',
      lineHeight: '1.5',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
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
    
    // Semantic processor styles
    semanticHeader: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginBottom: '12px',
      flexWrap: 'wrap'
    },
    intentBadge: {
      backgroundColor: '#6f42c1',
      color: 'white',
      padding: '4px 12px',
      borderRadius: '20px',
      fontSize: '12px',
      fontWeight: '600',
      textTransform: 'uppercase',
      letterSpacing: '0.5px'
    },
    entityBadge: {
      backgroundColor: '#17a2b8',
      color: 'white',
      padding: '4px 12px',
      borderRadius: '20px',
      fontSize: '12px',
      fontWeight: '600'
    },
    timeBadge: {
      backgroundColor: '#28a745',
      color: 'white',
      padding: '4px 12px',
      borderRadius: '20px',
      fontSize: '12px',
      fontWeight: '600'
    },
    messageContent: {
      fontSize: '15px',
      lineHeight: '1.6'
    },
    messageHeader: {
      fontSize: '18px',
      fontWeight: '700',
      color: '#2c3e50',
      margin: '12px 0 8px 0',
      paddingBottom: '8px',
      borderBottom: '2px solid #e9ecef'
    },
    highlightedLine: {
      fontSize: '16px',
      fontWeight: '600',
      margin: '8px 0',
      padding: '12px 16px',
      backgroundColor: '#f8f9fa',
      borderRadius: '8px',
      borderLeft: '4px solid #007bff',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
    },
    regularLine: {
      margin: '4px 0',
      color: '#495057'
    },
    
    // Clarification styles
    clarificationContainer: {
      marginTop: '16px',
      padding: '16px',
      backgroundColor: '#fff3cd',
      border: '1px solid #ffeaa7',
      borderRadius: '12px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    },
    clarificationHeader: {
      fontSize: '16px',
      fontWeight: '600',
      color: '#856404',
      marginBottom: '12px',
      textAlign: 'center'
    },
    clarificationOptions: {
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    },
    clarificationButton: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '12px 16px',
      backgroundColor: '#f8f9fa',
      border: '2px solid #dee2e6',
      borderRadius: '8px',
      cursor: 'pointer',
      transition: 'all 0.2s',
      fontSize: '14px',
      textAlign: 'left'
    },
    clarificationButtonIcon: {
      fontSize: '24px',
      minWidth: '32px',
      textAlign: 'center'
    },
    clarificationButtonContent: {
      flex: 1
    },
    clarificationButtonTitle: {
      fontWeight: '600',
      color: '#495057',
      marginBottom: '4px'
    },
    clarificationButtonValue: {
      fontWeight: '700',
      color: '#2c3e50',
      marginBottom: '4px'
    },
    clarificationButtonDesc: {
      fontSize: '12px',
      color: '#6c757d',
      fontStyle: 'italic'
    },
    
    statsFooter: {
      marginTop: '16px',
      padding: '12px 16px',
      backgroundColor: '#e9ecef',
      borderRadius: '8px',
      fontSize: '13px',
      color: '#495057',
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      flexWrap: 'wrap'
    },
    entitiesContainer: {
      marginTop: '12px'
    },
    entitiesDetails: {
      backgroundColor: '#f8f9fa',
      border: '1px solid #dee2e6',
      borderRadius: '6px',
      padding: '8px'
    },
    entitiesSummary: {
      cursor: 'pointer',
      fontSize: '13px',
      fontWeight: '600',
      color: '#495057',
      padding: '4px 8px',
      borderRadius: '4px',
      transition: 'background-color 0.2s'
    },
    entitiesList: {
      marginTop: '8px',
      fontSize: '12px',
      fontFamily: 'monospace'
    },
    entityItem: {
      padding: '4px 8px',
      margin: '2px 0',
      backgroundColor: '#fff',
      borderRadius: '4px',
      color: '#495057'
    },
    noResults: {
      textAlign: 'center',
      padding: '40px 20px',
      color: '#6c757d'
    },
    noResultsIcon: {
      fontSize: '48px',
      marginBottom: '16px'
    },
    noResultsText: {
      fontSize: '16px',
      fontWeight: '500'
    },
    tableContainer: {
      marginTop: '16px',
      border: '1px solid #e9ecef',
      borderRadius: '12px',
      overflow: 'hidden',
      backgroundColor: '#fff',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    },
    tableHeader: {
      backgroundColor: '#f8f9fa',
      padding: '12px 16px',
      borderBottom: '1px solid #e9ecef',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      fontSize: '14px',
      fontWeight: '600',
      color: '#495057'
    },
    exportButton: {
      backgroundColor: '#28a745',
      color: 'white',
      border: 'none',
      padding: '8px 16px',
      borderRadius: '6px',
      fontSize: '12px',
      cursor: 'pointer',
      fontWeight: '500',
      transition: 'all 0.2s',
      display: 'flex',
      alignItems: 'center',
      gap: '6px'
    },
    tableWrapper: {
      maxHeight: '500px',
      overflowY: 'auto',
      overflowX: 'auto'
    },
    table: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: '14px'
    },
    tableHead: {
      position: 'sticky',
      top: 0,
      backgroundColor: '#fff',
      zIndex: 1
    },
    tableHeaderCell: {
      borderBottom: '2px solid #e9ecef',
      textAlign: 'left',
      padding: '12px 16px',
      fontWeight: '600',
      color: '#495057',
      backgroundColor: '#fff',
      whiteSpace: 'nowrap',
      minWidth: '100px'
    },
    tableRow: {
      borderBottom: '1px solid #e9ecef',
      transition: 'background-color 0.1s'
    },
    tableCell: {
      padding: '12px 16px',
      color: '#495057',
      borderBottom: '1px solid #f8f9fa',
      maxWidth: '200px',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    },
    tableFooter: {
      padding: '12px 16px',
      backgroundColor: '#f8f9fa',
      borderTop: '1px solid #e9ecef',
      fontSize: '13px',
      color: '#6c757d',
      textAlign: 'center',
      fontWeight: '500'
    },
    timestamp: {
      fontSize: '11px',
      color: '#6c757d',
      marginTop: '4px'
    },
    dataContainer: {
      marginTop: '16px'
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
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.headerTitle}>
          🧠 Semantic AI Assistant
          <span style={{ fontSize: '12px', color: '#6c757d', fontWeight: 'normal' }}>
            (Enhanced Query Processing)
          </span>
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
                  ...(message.isError ? styles.errorMessage : {}),
                  ...(message.isClarification ? { backgroundColor: '#e3f2fd', border: '1px solid #90caf9' } : {})
                }}
              >
                {message.type === 'user' ? (
                  <div>
                    {message.isClarification && (
                      <div style={{ fontSize: '12px', color: '#1976d2', marginBottom: '8px', fontWeight: '600' }}>
                        🎯 Clarification provided:
                      </div>
                    )}
                    {message.content}
                  </div>
                ) : (
                  renderFormattedMessage(message.content, message.data, message.needsClarification)
                )}
                
                {/* Data display for bot messages - improved table data detection */}
                {message.data && (() => {
                  const tableCandidate = message.data?.data;
                  const tableData = Array.isArray(tableCandidate) && Array.isArray(tableCandidate[0]) 
                    ? tableCandidate[0] // first element is the rows array
                    : Array.isArray(tableCandidate) 
                    ? tableCandidate 
                    : null;
                  
                  return tableData && (
                    <div style={styles.dataContainer}>
                      {renderTable(tableData)}
                    </div>
                  );
                })()}
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
                🧠 AI is processing with semantic understanding...
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input - Disabled during clarification */}
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
              placeholder={
                pendingClarification 
                  ? "Please select an option above to clarify your query..."
                  : "Ask me anything about university data... Try 'my CGPA', 'count students', or 'my math grade'"
              }
              style={{
                ...styles.input,
                ...(pendingClarification ? { 
                  backgroundColor: '#f8f9fa', 
                  color: '#6c757d',
                  cursor: 'not-allowed'
                } : {})
              }}
              rows={1}
              disabled={loading || pendingClarification}
            />
            <button
              onClick={() => askQuery()}
              disabled={loading || !query.trim() || pendingClarification}
              style={{
                ...styles.sendButton,
                ...(loading || !query.trim() || pendingClarification ? styles.sendButtonDisabled : {})
              }}
              onMouseOver={(e) => {
                if (!loading && query.trim() && !pendingClarification) {
                  e.target.style.backgroundColor = '#0056b3';
                }
              }}
              onMouseOut={(e) => {
                if (!loading && query.trim() && !pendingClarification) {
                  e.target.style.backgroundColor = '#007bff';
                }
              }}
            >
              {loading ? '⏳' : '🧠'} {loading ? 'Processing...' : 'Send'}
            </button>
          </div>
          
          {/* Clarification hint */}
          {pendingClarification && (
            <div style={{
              marginTop: '12px',
              textAlign: 'center',
              fontSize: '14px',
              color: '#856404',
              backgroundColor: '#fff3cd',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid #ffeaa7'
            }}>
              💡 Please select one of the options above to continue with your query
            </div>
          )}
        </div>
      </div>
      
      {/* Debug toggle */}
      <button
        onClick={() => setShowDebug(!showDebug)}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          backgroundColor: '#6c757d',
          color: 'white',
          border: 'none',
          borderRadius: '50%',
          width: '50px',
          height: '50px',
          fontSize: '16px',
          cursor: 'pointer'
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
          width: '350px',
          maxHeight: '500px',
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
            fontSize: '14px',
            backgroundColor: '#f8f9fa'
          }}>
            🧠 Semantic Processor Debug
          </div>
          <div style={{
            padding: '12px',
            fontSize: '12px',
            fontFamily: 'monospace',
            maxHeight: '400px',
            overflowY: 'auto'
          }}>
            <strong>System Type:</strong><br/>
            Semantic Query Processor with Disambiguation<br/><br/>
            
            <strong>User Info:</strong><br/>
            Role: {user.role}<br/>
            ID: {user.userid}<br/><br/>
            
            <strong>Pending Clarification:</strong><br/>
            {pendingClarification ? 'Yes - awaiting user choice' : 'None'}<br/><br/>
            
            <strong>Last Response Data:</strong><br/>
            {(() => {
              const lastMessage = messages[messages.length - 1];
              if (!lastMessage || !lastMessage.data) return 'No data';
              
              const data = lastMessage.data;
              return (
                <div style={{ fontSize: '11px', maxHeight: '200px', overflowY: 'auto' }}>
                  {data.intent && <div><strong>Intent:</strong> {data.intent}</div>}
                  {data.semantic_entities && <div><strong>Entities:</strong> {JSON.stringify(data.semantic_entities, null, 2)}</div>}
                  {data.ambiguous_terms && <div><strong>Ambiguous:</strong> {JSON.stringify(data.ambiguous_terms, null, 2)}</div>}
                  {data.count !== undefined && <div><strong>Count:</strong> {data.count}</div>}
                  {data.execution_time && <div><strong>Time:</strong> {(data.execution_time * 1000).toFixed(0)}ms</div>}
                  {data.success !== undefined && <div><strong>Success:</strong> {data.success ? '✅' : '❌'}</div>}
                </div>
              );
            })()}
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
          width: 8px;
        }
        
        ::-webkit-scrollbar-track {
          background: #f1f1f1;
          border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #c1c1c1;
          border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #a1a1a1;
        }
        
        /* Table hover effects */
        table tbody tr:hover {
          background-color: #e3f2fd !important;
          transition: background-color 0.2s;
        }
        
        /* Button hover effects */
        button:hover {
          transform: translateY(-1px);
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Clarification button hover effects */
        .clarification-button:hover {
          border-color: #007bff !important;
          box-shadow: 0 2px 8px rgba(0,123,255,0.2) !important;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
          .clarification-options {
            flex-direction: column;
          }
          
          .clarification-button {
            text-align: center;
          }
          
          .message-wrapper {
            max-width: 95% !important;
          }
          
          .semantic-header {
            flex-direction: column;
            align-items: flex-start;
          }
        }
        
        /* Animation for clarification appearance */
        .clarification-container {
          animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}