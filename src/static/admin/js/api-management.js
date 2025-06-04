// API Management JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize API management
    initializeApiManagement();
});

function initializeApiManagement() {
    console.log('Initializing API Management...');
    
    // Add event listener to the Generate API Key button
    const generateApiBtn = document.getElementById('generate-api-btn');
    if (generateApiBtn) {
        generateApiBtn.addEventListener('click', function() {
            // Show the generate API key modal
            const modal = new bootstrap.Modal(document.getElementById('generateApiKeyModal'));
            
            // Populate companies dropdown before showing the modal
            if (typeof populateCompanyDropdown === 'function') {
                populateCompanyDropdown();
            } else {
                // Fallback to our local function if the global one is not available
                loadCompaniesForApiKey();
            }
            
            // Show the modal
            modal.show();
        });
    }

    // Add event listener for company select dropdown to fetch subscription plan
    const apiCompanySelect = document.getElementById('apiCompanySelect');
    if (apiCompanySelect) {
        apiCompanySelect.addEventListener('change', function() {
            const companyId = this.value;
            if (companyId) {
                // Find the selected company's subscription plan
                const option = this.options[this.selectedIndex];
                const subscriptionPlan = option.getAttribute('data-subscription-plan');
                
                // Display the subscription plan
                document.getElementById('apiSubscriptionPlan').value = subscriptionPlan || 'basic';
                
                // Reset any previously displayed API keys when company changes
                resetApiKeyDisplay();
            } else {
                document.getElementById('apiSubscriptionPlan').value = '';
            }
        });
    }

    // Add event listener for the Copy API Key button
    const copyApiKeyBtn = document.getElementById('copyApiKeyBtn');
    if (copyApiKeyBtn) {
        copyApiKeyBtn.addEventListener('click', function() {
            copyToClipboard();
        });
    }

    // Listen for modal close event to reset the form
    const apiKeyModal = document.getElementById('generateApiKeyModal');
    if (apiKeyModal) {
        apiKeyModal.addEventListener('hidden.bs.modal', function() {
            resetApiKeyDisplay();
        });
    }

    // Load existing API keys when the APIs section is shown
    document.addEventListener('section-changed', function(e) {
        if (e.detail.section === 'apis') {
            console.log('APIs section shown, loading API keys...');
            loadApiKeys();
        }
    });
    
    // Also check if we're already on the APIs section when the page loads
    setTimeout(() => {
        const apisSection = document.getElementById('apis-section');
        if (apisSection && window.getComputedStyle(apisSection).display !== 'none') {
            console.log('APIs section is visible on page load, loading API keys...');
            loadApiKeys();
        }
    }, 500);
    
    // Add a global event listener for API key generation success
    window.addEventListener('apiKeyGenerated', function(e) {
        console.log('API key generation event received:', e.detail);
        // Reload API keys to ensure the new key is displayed
        loadApiKeys();
    });
}

// Reset API key display
function resetApiKeyDisplay() {
    // Hide result section
    const resultDiv = document.getElementById('apiKeyResultDiv');
    if (resultDiv) {
        resultDiv.style.display = 'none';
    }
    
    // Clear previous API key
    const apiKeyElement = document.getElementById('generatedApiKey');
    if (apiKeyElement) {
        if (apiKeyElement.tagName === 'INPUT') {
            apiKeyElement.value = '';
        } else {
            apiKeyElement.textContent = '';
        }
    }
    
    // Re-enable the generate button
    const generateBtn = document.getElementById('generateApiKeyBtn');
    if (generateBtn) {
        generateBtn.disabled = false;
    }
}

// Load companies for the API key dropdown
function loadCompaniesForApiKey() {
    fetch('/api/admin/companies/list')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('apiCompanySelect');
            // Clear previous options except the first one
            while (select.options.length > 1) {
                select.remove(1);
            }
            
            // Add companies to the dropdown
            data.companies.forEach(company => {
                const option = document.createElement('option');
                option.value = company.id;
                option.textContent = company.name;
                option.setAttribute('data-subscription-plan', company.subscription_plan);
                select.appendChild(option);
            });
        })
        .catch(error => console.error('Error loading companies:', error));
}

// Generate a new API key
function generateApiKey(companyId, companyName) {
    console.log('API Management: generateApiKey called with', { companyId, companyName });
    
    // If called without parameters, get them from the form
    if (!companyId) {
        // Try different possible element IDs for company select
        const possibleSelectors = ['apiCompanySelect', 'companySelect'];
        let selectElement = null;
        
        for (const selector of possibleSelectors) {
            const element = document.getElementById(selector);
            if (element && element.value) {
                selectElement = element;
                companyId = element.value;
                companyName = element.options[element.selectedIndex].text;
                console.log(`Found company select with ID ${selector}:`, { companyId, companyName });
                break;
            }
        }
        
        if (!companyId) {
            console.error('No company selected. Please select a company.');
            alert('Please select a company');
            return;
        }
    }

    // Confirm API key generation
    if (!confirm(`Are you sure you want to generate a new API key for ${companyName}? This will invalidate any existing API keys.`)) {
        return;
    }

    // Reset any previously displayed API keys
    resetApiKeyDisplay();
    
    // Show loading indicator
    const generateBtn = document.getElementById('generateApiKeyBtn');
    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
    }
    
    fetch(`/api/admin/apis`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({ company_id: companyId })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Failed to generate API key: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('API key generated successfully:', data);
        
        // Display the generated API key in the form
        const apiKeyElement = document.getElementById('generatedApiKey');
        if (apiKeyElement) {
            apiKeyElement.value = data.key;
        }
        
        const resultDiv = document.getElementById('apiKeyResultDiv');
        if (resultDiv) {
            resultDiv.style.display = 'block';
        }
        
        const companyNameElement = document.getElementById('apiKeyCompanyName');
        if (companyNameElement) {
            companyNameElement.textContent = companyName;
        }
        
        // Reset the generate button
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate API Key';
        }
        
        // Show success message
        if (resultDiv) {
            const successMsg = document.createElement('div');
            successMsg.className = 'alert alert-success mt-3';
            successMsg.innerHTML = `<i class="bi bi-check-circle me-2"></i>API key for <strong>${companyName}</strong> generated successfully!`;
            resultDiv.appendChild(successMsg);
        }
        
        // Show the API key modal to make it more visible
        if (typeof bootstrap !== 'undefined') {
            const apiKeyModal = document.getElementById('apiKeyModal');
            if (apiKeyModal) {
                document.getElementById('modalApiKeyCompanyName').textContent = companyName;
                document.getElementById('modalGeneratedApiKey').value = data.key;
                const modal = new bootstrap.Modal(apiKeyModal);
                modal.show();
            }
        }
        
        // Create masked version of API key for display
        const maskedKey = data.key.substring(0, 8) + '...' + data.key.substring(data.key.length - 4);
        
        // Store the newly generated key in localStorage to persist across page refreshes
        try {
            let savedApiKeys = JSON.parse(localStorage.getItem('newlyGeneratedApiKeys') || '[]');
            
            // Check if this key already exists in localStorage
            const existingKeyIndex = savedApiKeys.findIndex(k => k.companyId === companyId);
            if (existingKeyIndex !== -1) {
                // Update the existing key
                savedApiKeys[existingKeyIndex] = {
                    key: data.key,
                    maskedKey: maskedKey,
                    companyId: companyId,
                    companyName: companyName,
                    createdAt: new Date().toISOString()
                };
            } else {
                // Add a new key
                savedApiKeys.push({
                    key: data.key,
                    maskedKey: maskedKey,
                    companyId: companyId,
                    companyName: companyName,
                    createdAt: new Date().toISOString()
                });
            }
            
            localStorage.setItem('newlyGeneratedApiKeys', JSON.stringify(savedApiKeys));
            console.log('Saved API key to localStorage for persistence across page refreshes');
        } catch (e) {
            console.error('Error saving API key to localStorage:', e);
        }
        
        // Dispatch an event to notify that an API key was generated
        window.dispatchEvent(new CustomEvent('apiKeyGenerated', {
            detail: {
                key: data.key,
                maskedKey: maskedKey,
                companyId: companyId,
                companyName: companyName
            }
        }));
        
        // Add the new API key directly to the table
        const table = document.getElementById('apis-table');
        if (table) {
            // Create a new row with the 'new-api-key-row' class
            const row = document.createElement('tr');
            row.className = 'new-api-key-row';
            row.dataset.apiKey = data.key; // Store the full key for reference
            row.dataset.companyId = companyId;
            
            // Add the row content
            row.innerHTML = `
                <td><span class="font-monospace">${maskedKey}</span></td>
                <td>${companyName}</td>
                <td>${new Date().toLocaleString()}</td>
                <td><span class="badge bg-success">active</span></td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="revokeLocalApiKey('${data.key}')">
                        <i class="bi bi-trash"></i> Revoke
                    </button>
                </td>
            `;
            
            // Add the row to the beginning of the table
            if (table.children.length > 0) {
                table.insertBefore(row, table.firstChild);
            } else {
                table.appendChild(row);
            }
            
            // Remove any "No API keys found" rows
            const emptyRows = table.querySelectorAll('tr td[colspan="5"]');
            emptyRows.forEach(cell => {
                if (cell.textContent.includes('No API keys found')) {
                    cell.parentElement.remove();
                }
            });
        }
        
        // If we're in the APIs section, make sure it's visible
        const apisSection = document.getElementById('apis-section');
        if (apisSection) {
            apisSection.style.display = 'block';
            
            // Scroll to the API keys table
            const apisTable = document.getElementById('apis-table');
            if (apisTable) {
                apisTable.scrollIntoView({ behavior: 'smooth' });
            }
        }
    })
    .catch(error => {
        console.error('Error generating API key:', error);
        alert('Failed to generate API key: ' + (error.message || 'Unknown error'));
        
        // Reset the generate button
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate API Key';
        }
    });
}

// Copy API key to clipboard
function copyToClipboard() {
    const apiKey = document.getElementById('generatedApiKey').textContent;
    
    navigator.clipboard.writeText(apiKey)
        .then(() => {
            const copyBtn = document.getElementById('copyApiKeyBtn');
            const originalText = copyBtn.innerHTML;
            
            // Show copied confirmation
            copyBtn.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
            setTimeout(() => {
                copyBtn.innerHTML = originalText;
            }, 2000);
        })
        .catch(err => {
            console.error('Failed to copy API key:', err);
            alert('Failed to copy API key. Please select and copy it manually.');
        });
}

// Load existing API keys
function loadApiKeys() {
    // Get the table
    const table = document.getElementById('apis-table');
    if (!table) {
        console.error('API keys table not found');
        return;
    }
    
    // Save any newly added rows (with class 'new-api-key-row')
    const newRows = [];
    const existingNewRows = table.querySelectorAll('.new-api-key-row');
    existingNewRows.forEach(row => {
        newRows.push(row.cloneNode(true));
    });
    
    // Get saved API keys from localStorage
    let savedApiKeys = [];
    try {
        savedApiKeys = JSON.parse(localStorage.getItem('newlyGeneratedApiKeys') || '[]');
        console.log(`Found ${savedApiKeys.length} saved API keys in localStorage`);
    } catch (e) {
        console.error('Error loading API keys from localStorage:', e);
        // Reset localStorage if it's corrupted
        localStorage.setItem('newlyGeneratedApiKeys', '[]');
    }
    
    // Show loading indicator
    table.innerHTML = '<tr><td colspan="5" class="text-center"><div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div> Loading API keys...</td></tr>';
    
    // Fetch API keys from the server
    fetch('/api/admin/apis', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache' // Prevent caching to ensure fresh data
        },
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Failed to load API keys: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('API keys loaded from server:', data);
        table.innerHTML = '';
        
        // Track all keys we add to the table to avoid duplicates
        const addedKeys = new Set();
        
        // First add any keys from localStorage
        if (savedApiKeys.length > 0) {
            console.log(`Adding ${savedApiKeys.length} saved API keys from localStorage`);
            savedApiKeys.forEach(savedKey => {
                // Create a new row for the saved key
                const row = document.createElement('tr');
                row.className = 'new-api-key-row';
                row.dataset.apiKey = savedKey.key;
                row.dataset.companyId = savedKey.companyId;
                
                // Add the row content
                row.innerHTML = `
                    <td><span class="font-monospace">${savedKey.maskedKey}</span></td>
                    <td>${savedKey.companyName}</td>
                    <td>${new Date(savedKey.createdAt).toLocaleString()}</td>
                    <td><span class="badge bg-success">active</span></td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="revokeLocalApiKey('${savedKey.key}')">
                            <i class="bi bi-trash"></i> Revoke
                        </button>
                    </td>
                `;
                
                // Add the row to the table
                table.appendChild(row);
                
                // Track this key as added
                addedKeys.add(savedKey.maskedKey);
            });
        }
        
        // Then add back any newly generated keys from this session
        if (newRows.length > 0) {
            console.log(`Restoring ${newRows.length} newly generated API keys from this session`);
            newRows.forEach(row => {
                const keySpan = row.querySelector('td:first-child span');
                if (keySpan) {
                    const maskedKey = keySpan.textContent.trim();
                    if (!addedKeys.has(maskedKey)) {
                        table.appendChild(row);
                        addedKeys.add(maskedKey);
                    }
                } else {
                    table.appendChild(row);
                }
            });
        }
        
        // Then add the keys from the server
        if (data.apis && data.apis.length > 0) {
            console.log(`Adding ${data.apis.length} API keys from server`);
            
            data.apis.forEach(api => {
                // Create masked version of API key for display
                const maskedKey = api.key.substring(0, 8) + '...' + api.key.substring(api.key.length - 4);
                
                // Skip if this key is already in the table
                if (addedKeys.has(maskedKey)) {
                    console.log(`Skipping duplicate key: ${maskedKey}`);
                    return;
                }
                
                // Add row to table
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><span class="font-monospace">${maskedKey}</span></td>
                    <td>${api.company || 'Unknown'}</td>
                    <td>${api.created_at ? new Date(api.created_at).toLocaleString() : 'N/A'}</td>
                    <td><span class="badge ${api.status === 'active' ? 'bg-success' : 'bg-danger'}">${api.status || 'unknown'}</span></td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="revokeApiKey(${api.id})">
                            <i class="bi bi-trash"></i> Revoke
                        </button>
                    </td>
                `;
                table.appendChild(row);
                addedKeys.add(maskedKey);
                
                // Remove this key from localStorage if it exists there
                // This helps clean up localStorage as keys are confirmed in the database
                const keyIndex = savedApiKeys.findIndex(k => k.key === api.key);
                if (keyIndex !== -1) {
                    savedApiKeys.splice(keyIndex, 1);
                    localStorage.setItem('newlyGeneratedApiKeys', JSON.stringify(savedApiKeys));
                    console.log(`Removed key ${maskedKey} from localStorage as it's now in the database`);
                }
            });
        }
        
        // If no rows were added, show empty state
        if (table.children.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="5" class="text-center">No API keys found</td>';
            table.appendChild(row);
        }
    })
    .catch(error => {
        console.error('Error loading API keys:', error);
        
        // Clear the loading indicator
        table.innerHTML = '';
        
        // First try to show any saved keys from localStorage
        if (savedApiKeys.length > 0) {
            savedApiKeys.forEach(savedKey => {
                const row = document.createElement('tr');
                row.className = 'new-api-key-row';
                row.dataset.apiKey = savedKey.key;
                row.innerHTML = `
                    <td><span class="font-monospace">${savedKey.maskedKey}</span></td>
                    <td>${savedKey.companyName}</td>
                    <td>${new Date(savedKey.createdAt).toLocaleString()}</td>
                    <td><span class="badge bg-success">active</span></td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="revokeLocalApiKey('${savedKey.key}')">
                            <i class="bi bi-trash"></i> Revoke
                        </button>
                    </td>
                `;
                table.appendChild(row);
            });
        }
        // Then try to restore any newly generated keys from this session
        else if (newRows.length > 0) {
            newRows.forEach(row => {
                table.appendChild(row);
            });
        } 
        // If all else fails, show the error
        else {
            table.innerHTML = `<tr><td colspan="5" class="text-center text-danger"><i class="bi bi-exclamation-triangle me-2"></i>${error.message || 'Failed to load API keys'}</td></tr>`;
        }
    });
}

// Revoke (delete) an API key
function revokeApiKey(apiId) {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
        return;
    }
    
    fetch(`/api/admin/apis?id=${apiId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }
        
        // Reload API keys after successful deletion
        loadApiKeys();
    })
    .catch(error => {
        console.error('Error revoking API key:', error);
        alert('Failed to revoke API key. Please try again.');
    });
}

// Revoke a locally stored API key
function revokeLocalApiKey(apiKey) {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
        return;
    }
    
    // Remove from localStorage
    let savedApiKeys = JSON.parse(localStorage.getItem('newlyGeneratedApiKeys') || '[]');
    savedApiKeys = savedApiKeys.filter(key => key.key !== apiKey);
    localStorage.setItem('newlyGeneratedApiKeys', JSON.stringify(savedApiKeys));
    
    console.log(`Removed API key from localStorage`);
    
    // Reload the table
    loadApiKeys();
}

// Load these functions globally
window.revokeApiKey = revokeApiKey;
window.deleteApi = revokeApiKey;
window.apiKeyGenerate = generateApiKey;
window.loadApiKeys = loadApiKeys;
window.copyToClipboard = copyToClipboard;
window.revokeLocalApiKey = revokeLocalApiKey;