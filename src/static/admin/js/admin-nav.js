/**
 * Admin Navigation Script
 * Handles sidebar navigation and tab switching
 */

// Create sidebar navigation
function createSidebar() {
    const navItems = [
        { id: 'dashboard', icon: 'speedometer2', label: 'Dashboard', url: 'dashboard.html' },
        { id: 'users', icon: 'people', label: 'Users', url: 'users.html' },
        { id: 'companies', icon: 'building', label: 'Companies', url: 'companies.html' },
        { id: 'teams', icon: 'people-fill', label: 'Manage Team', url: 'team.html' },
        { id: 'features', icon: 'toggles', label: 'Company Features', url: 'company_features.html' },
        { id: 'plans', icon: 'credit-card', label: 'Pricing Plans', url: 'plans.html' },
        { id: 'payments', icon: 'cash-coin', label: 'Payments', url: 'payments.html' },
        { id: 'support', icon: 'headset', label: 'Support', url: 'support.html' },
        { id: 'settings', icon: 'gear', label: 'Settings', url: 'settings.html' }
    ];

    const sidebarElement = document.getElementById('sidebar-nav');
    if (!sidebarElement) return;

    const currentPath = window.location.pathname;
    const currentPage = currentPath.substring(currentPath.lastIndexOf('/') + 1);

    let navHtml = '';
    navItems.forEach(item => {
        const isActive = currentPage === item.url;
        navHtml += `
            <li class="nav-item">
                <a class="nav-link ${isActive ? 'active' : ''}" href="${item.url}">
                    <i class="bi bi-${item.icon} me-2"></i>
                    ${item.label}
                </a>
            </li>
        `;
    });

    // Add logout at the bottom
    navHtml += `
        <li class="nav-item mt-5">
            <a class="nav-link" href="#" id="logoutLink">
                <i class="bi bi-box-arrow-right me-2"></i>
                Logout
            </a>
        </li>
    `;

    sidebarElement.innerHTML = navHtml;

    // Add event listener to logout link
    document.getElementById('logoutLink').addEventListener('click', handleLogout);
}

// Handle logout
async function handleLogout(e) {
    e.preventDefault();
    
    try {
        await logout();
        window.location.href = '/admin/login.html';
    } catch (error) {
        console.error('Logout error:', error);
        showAlert('Failed to logout. Please try again.');
    }
}

// Show alert messages
function showAlert(message, type = 'danger') {
    const alertsContainer = document.getElementById('alerts-container');
    if (!alertsContainer) return;

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertsContainer.innerHTML = '';
    alertsContainer.appendChild(alertDiv);
    
    // Auto-dismiss success alerts after 3 seconds
    if (type === 'success') {
        setTimeout(() => {
            alertDiv.classList.remove('show');
            setTimeout(() => alertDiv.remove(), 150);
        }, 3000);
    }
}

// Initialize admin pages
document.addEventListener('DOMContentLoaded', () => {
    createSidebar();
}); 