// Admin Panel Global JavaScript

// Global variables
let userData = null;
let companyData = null;
let chatbotData = [];
let knowledgeBaseData = [];
let supportTicketsData = [];
let chatbotStats = null;
let conversationsChart = null;
let topicsChart = null;

// Toggle sidebar in mobile view
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const mainContent = document.querySelector('.main-content');
  const mainHeader = document.querySelector('.main-header');
  
  sidebar.classList.toggle('active');
  
  // If sidebar is now active (visible)
  if (sidebar.classList.contains('active')) {
    mainContent.style.marginLeft = '0';
    mainHeader.style.left = '0';
  } else {
    // Check if we're in mobile view
    if (window.innerWidth <= 992) {
      mainContent.style.marginLeft = '0';
      mainHeader.style.left = '0';
    } else {
      mainContent.style.marginLeft = 'var(--sidebar-width)';
      mainHeader.style.left = 'var(--sidebar-width)';
    }
  }
}

// Initialize sidebar state based on screen size
function initSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const mainContent = document.querySelector('.main-content');
  const mainHeader = document.querySelector('.main-header');
  
  if (window.innerWidth <= 992) {
    sidebar.classList.remove('active');
    mainContent.style.marginLeft = '0';
    mainHeader.style.left = '0';
  } else {
    sidebar.classList.add('active');
    mainContent.style.marginLeft = 'var(--sidebar-width)';
    mainHeader.style.left = 'var(--sidebar-width)';
  }
}

// Initialize tooltips
function initTooltips() {
  const tooltips = document.querySelectorAll('[data-tooltip]');
  tooltips.forEach(tooltip => {
    tooltip.addEventListener('mouseenter', function() {
      const text = this.getAttribute('data-tooltip');
      const tooltipEl = document.createElement('div');
      tooltipEl.classList.add('tooltip');
      tooltipEl.textContent = text;
      document.body.appendChild(tooltipEl);
      
      const rect = this.getBoundingClientRect();
      tooltipEl.style.top = `${rect.top - tooltipEl.offsetHeight - 5}px`;
      tooltipEl.style.left = `${rect.left + (rect.width / 2) - (tooltipEl.offsetWidth / 2)}px`;
      tooltipEl.style.opacity = '1';
    });
    
    tooltip.addEventListener('mouseleave', function() {
      const tooltipEl = document.querySelector('.tooltip');
      if (tooltipEl) {
        tooltipEl.remove();
      }
    });
  });
}

// Handle sidebar menu active state
function setActiveMenuItem() {
  const currentPath = window.location.pathname;
  const menuItems = document.querySelectorAll('.sidebar-link');
  
  menuItems.forEach(item => {
    const href = item.getAttribute('href');
    if (href && currentPath.includes(href)) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

// Toggle user dropdown menu
function toggleUserDropdown() {
  const dropdown = document.querySelector('.user-dropdown-menu');
  if (dropdown) {
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
  }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
  const dropdown = document.querySelector('.user-dropdown-menu');
  const userInfo = document.querySelector('.user-info');
  
  if (dropdown && dropdown.style.display !== 'none' && 
      !dropdown.contains(event.target) && 
      userInfo && !userInfo.contains(event.target)) {
    dropdown.style.display = 'none';
  }
});

// Initialize theme
function initTheme() {
  const savedTheme = localStorage.getItem('admin-theme');
  if (savedTheme) {
    document.body.setAttribute('data-theme', savedTheme);
  }
}

// Toggle theme
function toggleTheme() {
  const currentTheme = document.body.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  
  document.body.setAttribute('data-theme', newTheme);
  localStorage.setItem('admin-theme', newTheme);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
  // Check if we're on an admin page
  if (document.querySelector('.admin-layout')) {
    initSidebar();
    initTooltips();
    setActiveMenuItem();
    initTheme();
    
    // Add event listeners
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', toggleSidebar);
    }
    
    const headerToggle = document.querySelector('.header-toggle');
    if (headerToggle) {
      headerToggle.addEventListener('click', toggleSidebar);
    }
    
    const userDropdown = document.querySelector('.user-info');
    if (userDropdown) {
      userDropdown.addEventListener('click', toggleUserDropdown);
    }
    
    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Handle window resize
    window.addEventListener('resize', initSidebar);
  }
  
  // Check auth and load data
  try {
    const isAuthenticated = await checkAuth();
    if (isAuthenticated) {
      await loadAllData();
    }
  } catch (error) {
    console.error('Initialization error:', error);
    showAlert('Error initializing admin panel', 'danger');
  }
});

// Check authentication status
async function checkAuth() {
  try {
    const response = await fetch('/api/admin/check-auth', {
      method: 'GET',
      credentials: 'include'
    });
    
    if (!response.ok) {
      window.location.href = '/static/login.html';
      return false;
    }
    
    const data = await response.json();
    if (!data.authenticated) {
      window.location.href = '/static/login.html';
      return false;
    }
    
    // Update user info in header
    updateUserInfo(data.admin);
    return true;
  } catch (err) {
    console.error('Authentication error:', err);
    window.location.href = '/static/login.html';
    return false;
  }
}

// Load all data for the admin panel
async function loadAllData() {
  try {
    await Promise.all([
      loadChatbots(),
      loadKnowledgeBase(),
      loadSupportTickets()
    ]);
  } catch (error) {
    console.error('Error loading data:', error);
    showAlert('Error loading data. Please try again.', 'danger');
  }
}

// Load chatbots data
async function loadChatbots() {
  try {
    const response = await fetch('/api/admin/panel/chatbots', {
      credentials: 'include'
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    updateChatbotsTable(data);
  } catch (error) {
    console.error('Error loading chatbots:', error);
    showAlert('Error loading chatbots. Please try again later.', 'danger');
  }
}

// Load knowledge base data
async function loadKnowledgeBase() {
  try {
    const response = await fetch('/api/admin/panel/knowledge-base', {
      credentials: 'include'
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    updateKnowledgeBaseTable(data);
  } catch (error) {
    console.error('Error loading knowledge base:', error);
    showAlert('Error loading knowledge base. Please try again later.', 'danger');
  }
}

// Load support tickets data
async function loadSupportTickets() {
  try {
    const response = await fetch('/api/admin/panel/support-tickets', {
      credentials: 'include'
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    updateSupportTicketsTable(data);
  } catch (error) {
    console.error('Error loading support tickets:', error);
    showAlert('Error loading support tickets. Please try again later.', 'danger');
  }
}

// Update chatbots table
function updateChatbotsTable(chatbots) {
  const tableBody = document.getElementById('chatbotsTable');
  if (!chatbots || chatbots.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No chatbots found</td></tr>';
    return;
  }

  tableBody.innerHTML = chatbots.map(chatbot => `
    <tr>
      <td>${chatbot.name || 'Untitled'}</td>
      <td>${chatbot.version || '1.0'}</td>
      <td><span class="badge bg-${chatbot.status === 'active' ? 'success' : 'warning'}">${chatbot.status || 'inactive'}</span></td>
      <td>${chatbot.total_messages || 0}</td>
      <td>${chatbot.satisfaction_rate || 0}%</td>
      <td>
        <button class="btn btn-sm btn-info" onclick="editChatbot('${chatbot.id}')">
          <i class="fas fa-edit"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

// Update knowledge base table
function updateKnowledgeBaseTable(items) {
  const tableBody = document.getElementById('knowledgeTable');
  if (!items || items.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center">No knowledge base items found</td></tr>';
    return;
  }

  tableBody.innerHTML = items.map(item => `
    <tr>
      <td>${item.title || 'Untitled'}</td>
      <td>${item.category || 'Uncategorized'}</td>
      <td><span class="badge bg-${item.status === 'published' ? 'success' : 'warning'}">${item.status || 'draft'}</span></td>
      <td>${formatDate(item.updated_at)}</td>
      <td>
        <button class="btn btn-sm btn-info" onclick="editKnowledgeItem('${item.id}')">
          <i class="fas fa-edit"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

// Update support tickets table
function updateSupportTicketsTable(tickets) {
  const tableBody = document.getElementById('ticketsTable');
  if (!tickets || tickets.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No support tickets found</td></tr>';
    return;
  }

  tableBody.innerHTML = tickets.map(ticket => `
    <tr>
      <td>${ticket.ticket_number || 'N/A'}</td>
      <td>${ticket.subject || 'No subject'}</td>
      <td>${ticket.category || 'Uncategorized'}</td>
      <td><span class="badge bg-${getStatusBadgeColor(ticket.status)}">${ticket.status || 'open'}</span></td>
      <td>${formatDate(ticket.created_at)}</td>
      <td>
        <button class="btn btn-sm btn-info" onclick="viewTicket('${ticket.id}')">
          <i class="fas fa-eye"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

// Helper function to get status badge color
function getStatusBadgeColor(status) {
  switch (status?.toLowerCase()) {
    case 'open':
      return 'primary';
    case 'in_progress':
      return 'warning';
    case 'resolved':
      return 'success';
    case 'closed':
      return 'secondary';
    default:
      return 'info';
  }
}

// Helper functions
function formatNumber(num) {
  return new Intl.NumberFormat().format(num);
}

function formatPercentage(num) {
  return `${Math.round(num)}%`;
}

function formatTime(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function generateColors(count) {
  const colors = [
    '#4361ee',
    '#34bfa3',
    '#ffc107',
    '#f64e60',
    '#8950fc',
    '#1bc5bd',
    '#ff9800',
    '#f1416c'
  ];
  
  const result = [];
  for (let i = 0; i < count; i++) {
    result.push(colors[i % colors.length]);
  }
  return result;
}

function updateCompanyInfo() {
  // Implementation of updateCompanyInfo function
}

function updateChatbotsTable() {
  // Implementation of updateChatbotsTable function
}

function updateKnowledgeBaseTable() {
  // Implementation of updateKnowledgeBaseTable function
}

function updateSupportTicketsTable() {
  // Implementation of updateSupportTicketsTable function
}

// Update user info in header
function updateUserInfo(admin) {
  const userNameEl = document.querySelector('.user-name');
  const userRoleEl = document.querySelector('.user-role');
  const userAvatarEl = document.querySelector('.user-avatar');
  
  if (userNameEl) {
    userNameEl.textContent = admin.name || 'Admin';
  }
  
  if (userRoleEl) {
    userRoleEl.textContent = admin.role || 'Administrator';
  }
  
  if (userAvatarEl) {
    userAvatarEl.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(admin.name || 'Admin')}&background=random`;
  }
}

// Format date
function formatDate(dateString) {
  if (!dateString) return 'N/A';
  
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

// Format currency
function formatCurrency(amount, currency = 'USD') {
  if (amount === undefined || amount === null) return 'N/A';
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency
  }).format(amount);
}

// Show alert
function showAlert(message, type = 'info', duration = 3000) {
  const alertContainer = document.querySelector('.alert-container');
  
  if (!alertContainer) {
    const container = document.createElement('div');
    container.classList.add('alert-container');
    document.body.appendChild(container);
  }
  
  const alert = document.createElement('div');
  alert.classList.add('alert', `alert-${type}`, 'fadeIn');
  alert.textContent = message;
  
  document.querySelector('.alert-container').appendChild(alert);
  
  setTimeout(() => {
    alert.classList.remove('fadeIn');
    alert.classList.add('fadeOut');
    
    setTimeout(() => {
      alert.remove();
    }, 300);
  }, duration);
} 