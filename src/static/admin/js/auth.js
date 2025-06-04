// Authentication state
let currentAdmin = null;
let authCheckInProgress = false;

/**
 * Check if the user is authenticated
 * @returns {Promise<Object|null>} The admin user object if authenticated, null otherwise
 */
async function checkAuth() {
    if (authCheckInProgress) {
        // Return a promise that resolves when the current check is done
        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                if (!authCheckInProgress) {
                    clearInterval(checkInterval);
                    resolve(currentAdmin);
                }
            }, 100);
        });
    }

    authCheckInProgress = true;

    try {
        const response = await fetch('/api/admin/check-auth', {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                currentAdmin = data.admin;
                authCheckInProgress = false;
                return currentAdmin;
            }
        }
        
        // If we get here, not authenticated
        currentAdmin = null;
        authCheckInProgress = false;
        return null;
    } catch (error) {
        console.error('Error checking authentication:', error);
        currentAdmin = null;
        authCheckInProgress = false;
        return null;
    }
}

/**
 * Authenticated fetch that handles auth
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} The fetch response
 */
async function authenticatedFetch(url, options = {}) {
    // Check auth first
    await checkAuth();
    
    // Include credentials to send cookies with the request
    options.credentials = 'include';
    
    // Make the fetch request
    const response = await fetch(url, options);
    
    // If unauthorized, redirect to login
    if (response.status === 401) {
        currentAdmin = null;
        
        // Redirect to login
        window.location.href = '/static/login.html';
        throw new Error('Unauthorized access');
    }
    
    return response;
}

/**
 * Login admin user
 * @param {string} email - Admin email
 * @param {string} password - Admin password
 * @returns {Promise<Object|null>} The admin user object if login successful, null otherwise
 */
async function login(email, password) {
    try {
        const response = await fetch('/api/admin/login', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();
        
        if (response.ok) {
            // The backend uses session-based authentication
            // Store the admin user data
            currentAdmin = data.admin;
            return currentAdmin;
        }
        
        console.error('Login failed:', data.error || data.message || 'Unknown error');
        return null;
    } catch (error) {
        console.error('Login error:', error);
        throw error;
    }
}

/**
 * Logout the admin user
 */
async function logout() {
    try {
        await fetch('/api/admin/logout', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // Clear state
        currentAdmin = null;
        window.location.href = '/static/login.html';
    }
}

/**
 * Get the current admin user
 * @returns {Object|null} The admin user object if authenticated, null otherwise
 */
function getCurrentAdmin() {
    return currentAdmin;
}

/**
 * Check if the current admin has a specific permission
 * @param {string} permission - The permission to check
 * @returns {boolean} True if the admin has the permission, false otherwise
 */
function hasPermission(permission) {
    if (!currentAdmin || !currentAdmin.permissions) {
        return false;
    }
    return currentAdmin.permissions.includes(permission);
}

/**
 * Check if the current admin has a specific role
 * @param {string} role - The role to check
 * @returns {boolean} True if the admin has the role, false otherwise
 */
function hasRole(role) {
    if (!currentAdmin || !currentAdmin.roles) {
        return false;
    }
    return currentAdmin.roles.includes(role);
}

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    // If we're not on the login page, check authentication
    if (!window.location.pathname.includes('login.html')) {
        checkAuth().then(admin => {
            if (!admin) {
                // Not authenticated, save the current hash for redirect after login
                if (window.location.hash) {
                    localStorage.setItem('redirectHash', window.location.hash);
                }
                // Only redirect to login if we're not already on the login page
                if (!window.location.pathname.includes('login.html')) {
                    window.location.href = '/static/login.html';
                }
            }
        }).catch(error => {
            console.error('Auth check error:', error);
            // Only redirect to login if we're not already on the login page
            if (!window.location.pathname.includes('login.html')) {
                window.location.href = '/static/login.html';
            }
        });
    }
}); 