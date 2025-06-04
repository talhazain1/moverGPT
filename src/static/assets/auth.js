// Company user authentication state
let currentUser = null;
let authCheckInProgress = false;
let redirectOnAuthFailure = true; // New flag to control redirect behavior

/**
 * CRITICAL FIX: Token management system
 * This separates Flask session tokens from JWT tokens to prevent conflicts
 */
const TokenManager = {
    // Keys for different storage types
    JWT_TOKEN_KEY: 'jwt_access_token',
    
    // Get the JWT token from various sources
    getJwtToken: function() {
        // Check localStorage first (our preferred storage)
        const localToken = localStorage.getItem(this.JWT_TOKEN_KEY);
        if (localToken && localToken.startsWith('eyJhbGciOiJ')) {
            console.log('Found JWT in localStorage');
            return localToken;
        }
        
        // Then check sessionStorage
        const sessionToken = sessionStorage.getItem(this.JWT_TOKEN_KEY);
        if (sessionToken && sessionToken.startsWith('eyJhbGciOiJ')) {
            console.log('Found JWT in sessionStorage');
            return sessionToken;
        }
        
        // Finally check cookies specifically for JWT format
        const cookieToken = getCookie('access_token');
        if (cookieToken && cookieToken.startsWith('eyJhbGciOiJ')) {
            console.log('Found JWT in cookies');
            return cookieToken;
        }
        
        return null;
    },
    
    // Save a JWT token to all storage mechanisms
    saveJwtToken: function(token) {
        if (!token || !token.startsWith('eyJhbGciOiJ')) {
            console.warn('Attempted to save invalid JWT token');
            return false;
        }
        
        try {
            // Save to localStorage and sessionStorage (for redundancy)
            localStorage.setItem(this.JWT_TOKEN_KEY, token);
            sessionStorage.setItem(this.JWT_TOKEN_KEY, token);
            
            // Also set as a cookie for API requests
            document.cookie = `access_token=${token}; path=/; max-age=${30 * 24 * 60 * 60}; SameSite=Lax`;
            
            return true;
        } catch (e) {
            console.error('Error saving JWT token:', e);
            return false;
        }
    },
    
    // Clear all tokens (for logout)
    clearAllTokens: function() {
        try {
            localStorage.removeItem(this.JWT_TOKEN_KEY);
            sessionStorage.removeItem(this.JWT_TOKEN_KEY);
            document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
            return true;
        } catch (e) {
            console.error('Error clearing tokens:', e);
            return false;
        }
    },
    
    // Initialize token management
    initialize: function() {
        // Always attempt to restore a JWT token at startup
        const token = this.getJwtToken();
        if (token) {
            console.log('TokenManager: Initialized with valid JWT token');
            this.saveJwtToken(token);
            return true;
        }
        return false;
    }
};

// Initialize token management immediately
TokenManager.initialize();

// Original auth code adapted to use TokenManager
/**
 * Check if the user is authenticated
 * @param {boolean} shouldRedirect - Whether to redirect on auth failure
 * @returns {Promise<Object|null>} The user object if authenticated, null otherwise
 */
async function checkAuth(shouldRedirect = true) {
    console.log('checkAuth called');
    
    // Use our TokenManager to get a valid JWT
    const jwtToken = TokenManager.getJwtToken();
    if (jwtToken) {
        console.log('Got JWT token from TokenManager');
    }
    
    console.log('Current session state:', {
        hasUser: !!currentUser,
        authInProgress: authCheckInProgress,
        hasJwtToken: !!jwtToken,
        cookies: document.cookie
    });
    
    // Don't redirect if we're already on the login page
    const isLoginPage = window.location.pathname.includes('login.html');
    if (isLoginPage) {
        shouldRedirect = false;
    }
    
    // Set the redirect flag for this check
    redirectOnAuthFailure = shouldRedirect;
    
    if (authCheckInProgress) {
        console.log('Auth check already in progress, waiting...');
        // Return a promise that resolves when the current check is done
        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                if (!authCheckInProgress) {
                    clearInterval(checkInterval);
                    console.log('Previous auth check completed, returning user:', currentUser);
                    resolve(currentUser);
                }
            }, 100);
        });
    }

    authCheckInProgress = true;
    console.log('Starting new auth check');

    try {
        // Always use JWT token from TokenManager
        let token = jwtToken;
        
        // Ensure we have a valid JWT token for the API call
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        console.log('Fetching user profile from /api/users/profile');
        const response = await fetch('/api/users/profile', {
            method: 'GET',
            credentials: 'include',
            headers: headers
        });

        console.log('Profile response status:', response.status);

        if (response.ok) {
            const data = await response.json();
            console.log('Profile response data:', data);
            
            if (data.user) {
                console.log('User data found:', data.user);
                currentUser = data.user;
                
                // Save new token if it's in the response
                const authHeader = response.headers.get('Authorization');
                if (authHeader && authHeader.startsWith('Bearer ')) {
                    token = authHeader.split(' ')[1];
                    if (token && token.startsWith('eyJhbGciOiJ')) {
                        console.log('Saving new token from Authorization header');
                        TokenManager.saveJwtToken(token);
                    }
                }
                
                // Also check for token in response data
                if (data.token && data.token.startsWith('eyJhbGciOiJ')) {
                    console.log('Saving new token from response data');
                    TokenManager.saveJwtToken(data.token);
                }
                
                authCheckInProgress = false;
                return currentUser;
            } else {
                console.log('No user data in response');
            }
        } else {
            console.log('Profile request failed:', response.status, response.statusText);
            
            // Don't immediately redirect on 401, respect the redirectOnAuthFailure flag
            if (response.status === 401 && !redirectOnAuthFailure) {
                console.warn('Auth check failed with 401, but not redirecting');
            }
        }
        
        // If we get here, not authenticated
        console.log('Setting currentUser to null');
        currentUser = null;
        authCheckInProgress = false;
        
        // Only redirect if we're supposed to and we're not already on the login page
        if (response && response.status === 401 && redirectOnAuthFailure && !isLoginPage) {
            console.log('Unauthorized, redirecting to login');
            window.location.href = '/static/login.html?redirect=' + encodeURIComponent(window.location.pathname);
        }
        
        return null;
    } catch (error) {
        console.error('Error checking authentication:', error);
        console.error('Error stack:', error.stack);
        currentUser = null;
        authCheckInProgress = false;
        return null;
    } finally {
        // Ensure we always reset the flag
        authCheckInProgress = false;
        console.log('Auth check completed, final state:', {
            hasUser: !!currentUser,
            authInProgress: authCheckInProgress,
            cookies: document.cookie
        });
    }
}

/**
 * Authenticated fetch that handles auth
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @param {boolean} shouldRedirect - Whether to redirect on auth failure
 * @returns {Promise<Response>} The fetch response
 */
async function authenticatedFetch(url, options = {}, shouldRedirect = true) {
    console.log('authenticatedFetch called for', url);
    
    // Get JWT token from TokenManager
    const jwtToken = TokenManager.getJwtToken();
    
    // Always include credentials to send cookies
    options.credentials = 'include';
    
    // Initialize headers if not present
    if (!options.headers) {
        options.headers = {};
    }
    
    // If headers is an object (not Headers instance), add Content-Type
    if (options.headers.constructor === Object) {
        options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
    }
    
    // Add JWT token to headers if available
    if (jwtToken) {
        options.headers['Authorization'] = `Bearer ${jwtToken}`;
    }
    
    console.log('Request options:', {
        url,
        method: options.method || 'GET',
        credentials: options.credentials,
        hasAuthHeader: !!options.headers['Authorization']
    });
    
    // Make the fetch request
    try {
        const response = await fetch(url, options);
        console.log('Response status:', response.status);
        
        // If the call was successful and returned a new token, save it
        if (response.ok) {
            const authHeader = response.headers.get('Authorization');
            if (authHeader && authHeader.startsWith('Bearer ')) {
                const newToken = authHeader.split(' ')[1];
                if (newToken && newToken.startsWith('eyJhbGciOiJ')) {
                    console.log('Received new token in response header, saving it');
                    TokenManager.saveJwtToken(newToken);
                }
            }
            
            // Try to parse response as JSON to check for token
            try {
                // Clone the response so we can still return the original later
                const clonedResponse = response.clone();
                const contentType = response.headers.get('Content-Type');
                if (contentType && contentType.includes('application/json')) {
                    const data = await clonedResponse.json();
                    if (data && data.token && data.token.startsWith('eyJhbGciOiJ')) {
                        console.log('Received new token in response body, saving it');
                        TokenManager.saveJwtToken(data.token);
                    }
                }
            } catch (parseError) {
                // Ignore JSON parsing errors - not all responses are JSON
            }
        }
        
        // Check if we need to handle authentication errors
        if (response.status === 401 && shouldRedirect) {
            console.log('Authentication failed, attempting token refresh...');
            
            // Try to refresh the token before giving up
            try {
                const refreshResponse = await fetch('/api/users/refresh_token', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'}
                });
                
                if (refreshResponse.ok) {
                    const refreshData = await refreshResponse.json();
                    if (refreshData.token && refreshData.token.startsWith('eyJhbGciOiJ')) {
                        console.log('Successfully refreshed token, retrying original request');
                        // Save the new token
                        TokenManager.saveJwtToken(refreshData.token);
                        
                        // Retry the original request with the new token
                        options.headers['Authorization'] = `Bearer ${refreshData.token}`;
                        return fetch(url, options);
                    }
                }
                
                // If we couldn't refresh, redirect to login
                console.log('Authentication failed and token refresh failed, redirecting to login');
                currentUser = null;
                setTimeout(() => {
                    window.location.href = '/static/login.html?redirect=' + encodeURIComponent(window.location.pathname);
                }, 500);
                throw new Error('Authentication failed and token refresh failed');
            } catch (refreshError) {
                console.error('Error during token refresh:', refreshError);
                if (shouldRedirect) {
                    window.location.href = '/static/login.html?redirect=' + encodeURIComponent(window.location.pathname);
                }
                throw new Error('Authentication failed');
            }
        }
        
        return response;
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

/**
 * Get a cookie value by name
 * @param {string} name - Cookie name
 * @returns {string|null} Cookie value or null if not found
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

/**
 * Login user
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object|null>} The user object if login successful, null otherwise
 */
async function login(email, password) {
    try {
        const response = await fetch('/api/users/login', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ user_email: email, password: password })
        });

        const data = await response.json();
        
        if (response.ok) {
            // Store the user data
            currentUser = data.user;
            
            // Save JWT token if provided
            if (data.token && data.token.startsWith('eyJhbGciOiJ')) {
                TokenManager.saveJwtToken(data.token);
            }
            
            return currentUser;
        }
        
        console.error('Login failed:', data.error || data.message || 'Unknown error');
        return null;
    } catch (error) {
        console.error('Login error:', error);
        throw error;
    }
}

/**
 * Logout the user
 */
async function logout() {
    try {
        await fetch('/api/users/logout', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // Clear state
        currentUser = null;
        TokenManager.clearAllTokens();
        window.location.href = '/static/login.html';
    }
}

/**
 * Get the current user
 * @returns {Object|null} The user object if authenticated, null otherwise
 */
function getCurrentUser() {
    return currentUser;
}

/**
 * Check if user is authenticated without making API calls
 * @returns {boolean} True if user is authenticated
 */
function isAuthenticated() {
    return !!currentUser && !!TokenManager.getJwtToken();
}

/**
 * Update user info in the UI
 * @param {Object} user - The user object
 */
function updateUserInfo(user) {
    if (!user) return;

    // Update user name in header
    const userNameElements = document.querySelectorAll('.user-name');
    userNameElements.forEach(el => {
        if (el) el.textContent = user.user_name || 'User';
    });

    // Update user role
    const userRoleElements = document.querySelectorAll('.user-role');
    userRoleElements.forEach(el => {
        if (el) el.textContent = user.role || 'Member';
    });

    // Update user avatar
    const userAvatarElements = document.querySelectorAll('.user-avatar');
    userAvatarElements.forEach(el => {
        if (el) {
            if (user.company_logo) {
                el.src = user.company_logo;
            } else {
                el.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.user_name || 'User')}&background=random`;
            }
        }
    });
    
    // Update sidebar logo
    const sidebarLogo = document.getElementById('sidebarLogo');
    if (sidebarLogo) {
        if (user.company_logo) {
            sidebarLogo.src = user.company_logo;
        } else {
            sidebarLogo.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.company_name || 'Company')}&background=random`;
        }
    }
    
    // Update sidebar company name
    const sidebarCompanyName = document.getElementById('sidebarCompanyName');
    if (sidebarCompanyName) {
        sidebarCompanyName.textContent = user.company_name || 'Company Admin';
    }

    // Update company info fields if they exist
    const companyNameField = document.getElementById('company_name');
    if (companyNameField && user.company_name) {
        companyNameField.value = user.company_name;
    }

    const userNameField = document.getElementById('user_name');
    if (userNameField && user.user_name) {
        userNameField.value = user.user_name;
    }

    const userEmailField = document.getElementById('user_email');
    if (userEmailField && user.user_email) {
        userEmailField.value = user.user_email;
    }

    // Update subscription info if elements exist
    const subscriptionPlanElements = document.querySelectorAll('.subscription-plan');
    subscriptionPlanElements.forEach(el => {
        if (el) el.textContent = user.subscription_plan || 'Free Plan';
    });

    const subscriptionExpiryElements = document.querySelectorAll('.subscription-expiry');
    subscriptionExpiryElements.forEach(el => {
        if (el && user.subscription_expires_at) {
            const expiryDate = new Date(user.subscription_expires_at);
            el.textContent = `Expires on ${expiryDate.toLocaleDateString()}`;
        } else if (el) {
            el.textContent = 'No active subscription';
        }
    });

    return user;
}

// Initialize page with token check
document.addEventListener('DOMContentLoaded', () => {
    // Initialize token manager on page load
    TokenManager.initialize();
    
    // Only check auth on login page
    if (window.location.pathname.includes('login.html')) {
        // Clear any existing user data
        currentUser = null;
    }
    // For all other pages, let the page's own initialization handle auth
}); 