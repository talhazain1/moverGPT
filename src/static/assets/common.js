/**
 * Common JavaScript functions for the moving company chatbot platform
 */

// API endpoints
const API_BASE_URL = '';  // Empty for relative URLs
const API_ENDPOINTS = {
    USER_PROFILE: '/api/users/profile',
    MOVING_PARAMETERS: '/api/companies/moving-parameters',
    SAVE_PARAMETERS: '/api/companies/save-moving-parameters',
    BOOKINGS: '/api/bookings/moving',
};

// Utility functions
const utils = {
    /**
     * Make an API call with proper authentication
     * @param {string} url - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise} - Promise resolving to JSON response
     */
    apiCall: async function(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        };
        
        const mergedOptions = {...defaultOptions, ...options};
        
        try {
            const response = await fetch(url, mergedOptions);
            
            // Handle 401 Unauthorized specifically
            if (response.status === 401) {
                console.warn('Authentication error detected in API call');
                // Don't automatically redirect or clear token here
                // Let the calling code handle this
                throw new Error('Authentication failed');
            }
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    },
    
    /**
     * Get the current user's profile
     * @returns {Promise} - Promise resolving to user data
     */
    getUserProfile: async function() {
        try {
            return await this.apiCall(API_ENDPOINTS.USER_PROFILE);
        } catch (error) {
            // Don't throw error for auth failures during profile fetch
            // This prevents automatic logout when profile fetch fails
            if (error.message === 'Authentication failed') {
                console.warn('Authentication failed when fetching profile, but continuing');
                return { name: 'Guest User', isAuthenticated: false };
            }
            throw error;
        }
    },
    
    /**
     * Format currency values
     * @param {number} value - Value to format
     * @returns {string} - Formatted currency string
     */
    formatCurrency: function(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
        }).format(value);
    },
    
    /**
     * Format date values
     * @param {string} dateString - Date string to format
     * @returns {string} - Formatted date string
     */
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        }).format(date);
    },
    
    /**
     * Show an error message to the user
     * @param {string} message - Error message to display
     */
    showError: function(message) {
        const errorElement = document.getElementById('error-message');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
            
            // Hide after 5 seconds
            setTimeout(() => {
                errorElement.style.display = 'none';
            }, 5000);
        } else {
            alert(`Error: ${message}`);
        }
    },
    
    /**
     * Check if user is authenticated
     * @returns {boolean} - True if authenticated
     */
    isAuthenticated: function() {
        return !!localStorage.getItem('token');
    }
};

// Initialize the page
document.addEventListener('DOMContentLoaded', async function() {
    try {
        // Check authentication
        if (utils.isAuthenticated()) {
            try {
                // Load user data
                const userData = await utils.getUserProfile();
                
                // Update user info in the UI if needed
                const userNameElement = document.getElementById('user-name');
                if (userNameElement && userData.name) {
                    userNameElement.textContent = userData.name;
                }
            } catch (error) {
                console.error('Error loading user profile:', error);
                // Don't show error to user or redirect to login
                // Just continue with the page load
            }
        }
    } catch (error) {
        console.error('Error initializing page:', error);
        // Don't show error to user
    }
});

// Common utility functions shared across pages

// Global variable for development mode
const DEVELOPMENT_MODE = true;

// Function to ensure token consistency across pages
function ensureAuthTokenConsistency() {
  try {
    // Check for token in cookie
    let token = document.cookie.split('; ').find(row => row.startsWith('access_token='));
    if (token) {
      token = token.split('=')[1];
      
      // Skip if it's a Flask session token
      if (token.startsWith('eyJfZnJlc2g')) {
        token = null;
      }
    }
    
    // If no valid JWT token found in cookie, try to find in storage
    if (!token || !token.startsWith('eyJhbGciOiJ')) {
      // Try sessionStorage first
      let storedToken = sessionStorage.getItem('access_token');
      
      // Try localStorage if not in sessionStorage
      if (!storedToken || !storedToken.startsWith('eyJhbGciOiJ')) {
        storedToken = localStorage.getItem('access_token');
      }
      
      // Try permanent cookie
      if (!storedToken || !storedToken.startsWith('eyJhbGciOiJ')) {
        const permToken = document.cookie.split('; ').find(row => row.startsWith('permanent_token='));
        if (permToken) {
          storedToken = permToken.split('=')[1];
        }
      }
      
      // If found a valid token in storage, set it to cookie
      if (storedToken && storedToken.startsWith('eyJhbGciOiJ')) {
        console.log('Found valid token in storage, setting to cookie');
        document.cookie = `access_token=${storedToken}; path=/; max-age=${30 * 24 * 60 * 60}; SameSite=Lax`;
        token = storedToken;
      }
    }
    
    // If found a valid token, ensure it's stored in all locations
    if (token && token.startsWith('eyJhbGciOiJ')) {
      console.log('Ensuring token consistency across storage mechanisms');
      sessionStorage.setItem('access_token', token);
      localStorage.setItem('access_token', token);
      document.cookie = `permanent_token=${token}; path=/; max-age=${90 * 24 * 60 * 60}; SameSite=Lax`;
      return true;
    }
    
    return false;
  } catch (e) {
    console.error('Error ensuring token consistency:', e);
    return false;
  }
}

// Call this function on page load
document.addEventListener('DOMContentLoaded', function() {
  ensureAuthTokenConsistency();
});

// Mock moving parameters accessor
function getMockMovingParameters() {
  try {
    // Try to load the parameters from localStorage
    const savedParamsString = localStorage.getItem('mock_moving_parameters');
    if (savedParamsString) {
      return JSON.parse(savedParamsString);
    }
  } catch (e) {
    console.error("Error loading mock moving parameters from localStorage:", e);
  }
  
  // Return default parameters if none found in localStorage
  return {
    base_rate_per_mile: 1.50,
    move_size_rates: {
      "studio": 320,
      "1-bedroom": 640, 
      "2-bedroom": 960,
      "3-bedroom": 1280,
      "4-bedroom": 1600,
      "office": 2000,
      "car": 120
    },
    additional_service_costs: {
      "packing": {
        "studio": 100,
        "1-bedroom": 150,
        "2-bedroom": 200,
        "3-bedroom": 250,
        "4-bedroom": 300,
        "office": 350,
        "car": 50
      },
      "storage": {
        "studio": 80,
        "1-bedroom": 130,
        "2-bedroom": 180,
        "3-bedroom": 230,
        "4-bedroom": 280,
        "office": 300,
        "car": 50
      }
    },
    rate_adjustments: {
      "seasonality_rate": 0.10,
      "rural_location_rate": 0.10,
      "min_cost_multiplier": 1.1,
      "max_cost_multiplier": 1.4
    }
  };
}

// Make the function available globally
window.getMockMovingParameters = getMockMovingParameters;

// If there's window.MOCK_MOVING_PARAMETERS already set (from another page),
// use that value, otherwise try to load it
if (!window.MOCK_MOVING_PARAMETERS) {
  window.MOCK_MOVING_PARAMETERS = getMockMovingParameters();
  console.log("Initialized MOCK_MOVING_PARAMETERS from common.js:", window.MOCK_MOVING_PARAMETERS);
}
