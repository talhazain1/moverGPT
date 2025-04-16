// Authentication state
let currentAdmin = null;

// Check if user is authenticated
async function checkAuth() {
    try {
        const response = await fetch('/api/admin/check-auth', {
            method: 'GET',
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                currentAdmin = data.admin;
                return true;
            }
        }
        return false;
    } catch (error) {
        console.error('Auth check failed:', error);
        return false;
    }
}

// Login function
async function login(email, password) {
    try {
        // Get the current URL to handle redirects
        const currentUrl = window.location.href;
        const nextUrl = new URLSearchParams(window.location.search).get('next');
        
        const response = await fetch('/api/admin/login' + (nextUrl ? `?next=${encodeURIComponent(nextUrl)}` : ''), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ email, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            currentAdmin = data.admin;
            
            // Handle redirect if provided
            if (data.redirect) {
                window.location.href = data.redirect;
            } else {
                window.location.href = '/admin/dashboard';
            }
            
            return { success: true, data };
        } else {
            const error = await response.json();
            return { success: false, error: error.error };
        }
    } catch (error) {
        return { success: false, error: 'Login failed' };
    }
}

// Logout function
async function logout() {
    try {
        const response = await fetch('/api/admin/logout', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            currentAdmin = null;
            window.location.href = '/admin/login';
        }
    } catch (error) {
        console.error('Logout failed:', error);
    }
}

// Get current admin
function getCurrentAdmin() {
    return currentAdmin;
}

// Check if admin has specific permission
function hasPermission(permission) {
    if (!currentAdmin) return false;
    return currentAdmin.permissions.includes(permission);
}

// Check if admin has specific role
function hasRole(role) {
    if (!currentAdmin) return false;
    return currentAdmin.role === role;
}

// Initialize auth state on page load
document.addEventListener('DOMContentLoaded', async () => {
    const isLoginPage = window.location.pathname.includes('/admin/login');
    
    if (!isLoginPage) {
        const isAuthenticated = await checkAuth();
        if (!isAuthenticated) {
            // Store the current URL to redirect back after login
            const currentUrl = window.location.pathname + window.location.search;
            window.location.href = `/admin/login?next=${encodeURIComponent(currentUrl)}`;
        }
    }
}); 