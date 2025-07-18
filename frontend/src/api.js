// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// API service functions
export const apiService = {
  login: async (userid, password) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ userid, password }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    
    return response.json();
  },
  
  sendQuery: async (query, userid, role) => {
    const response = await fetch(`${API_BASE_URL}/api/chatbot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, userid, role }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Query failed');
    }
    
    return response.json();
  }
};

export { API_BASE_URL };