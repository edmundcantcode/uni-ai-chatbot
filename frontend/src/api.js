// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// API service functions
export const apiService = {
  login: async (userid, password) => {
    const response = await fetch(`${API_BASE_URL}/api/login`, {
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
    console.log('🚀 Sending semantic query:', { query, userid, role });
    
    const response = await fetch(`${API_BASE_URL}/api/chatbot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, userid, role }),
    });
   
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      
      try {
        const error = await response.json();
        errorMessage = error.error || error.message || error.detail || errorMessage;
      } catch (parseError) {
        console.error('Could not parse error response:', parseError);
      }
      
      throw new Error(errorMessage);
    }
   
    const data = await response.json();
    console.log('📥 Semantic processor response:', data);
    
    // Handle semantic processor response format
    if (data.status === 'success' && data.data) {
      // Return the semantic processor data format
      return data;
    } else if (data.status === 'error') {
      // Handle error response
      throw new Error(data.message || 'Query processing failed');
    } else {
      // Handle direct response (legacy compatibility)
      return {
        status: 'success',
        data: data
      };
    }
  },

  // Optional: Health check for debugging
  checkHealth: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return { healthy: true, data };
      } else {
        return { healthy: false, status: response.status };
      }
    } catch (error) {
      console.error('Health check failed:', error);
      return { healthy: false, error: error.message };
    }
  }
};

export { API_BASE_URL };