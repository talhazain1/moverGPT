/**
 * Moving Cost Calculator Widget
 * 
 * This widget provides a multi-step form for calculating moving costs
 * based on a company's specific rates and parameters.
 */

(function() {
    // Widget configuration
    let config = {
        companyId: null,
        apiKey: null,
        apiUrl: null,
        websiteUrl: null,
        containerId: 'moving-cost-calculator-container',
        primaryColor: '#007bff',
        secondaryColor: '#6c757d',
        fontFamily: 'Arial, sans-serif'
    };

    // State management
    let state = {
        currentStep: 1,
        totalSteps: 4,
        origin: '',
        destination: '',
        distance: 0,
        moveSize: '',
        moveDate: '',
        name: '',
        email: '',
        phone: '',
        recipientEmail: '',
        estimate: null,
        isLoading: false,
        error: null,
        quoteSubmitted: false,
        emailSent: false,
        packingService: false,
        storageService: false
    };

    /**
     * Initialize the calculator widget
     * @param {Object} options - Configuration options
     */
    function initMovingCalculator(options) {
        // Merge config with options
        config = { ...config, ...options };
        
        // Debug the config values
        console.log('Moving Calculator Config:', config);
        
        // Add custom styles for checkboxes
        const checkboxStyles = document.createElement('style');
        checkboxStyles.textContent = `
            .moving-calculator .additional-services {
                margin: 15px 0;
                border: 1px solid #eee;
                border-radius: 5px;
                padding: 15px;
                background-color: #f9f9f9;
            }
            
            .moving-calculator .service-option {
                display: flex;
                align-items: center;
                margin-bottom: 12px;
                padding: 8px 12px;
                background-color: white;
                border-radius: 4px;
                border: 1px solid #ddd;
                transition: all 0.2s;
            }
            
            .moving-calculator .service-option:hover {
                border-color: ${config.primaryColor};
            }
            
            .moving-calculator .service-option input[type="checkbox"] {
                width: auto;
                margin-right: 10px;
                transform: scale(1.2);
                accent-color: ${config.primaryColor};
            }
            
            .moving-calculator .service-option label {
                display: inline;
                font-weight: normal;
                flex: 1;
            }
            
            .moving-calculator .service-description {
                font-size: 0.85rem;
                color: #666;
                margin-top: 3px;
            }
        `;
        document.head.appendChild(checkboxStyles);
        
        // IMPORTANT: When running on app.movergpt.com, use window.location.origin
        // But when embedded on customer websites, use the provided apiUrl
        if (window.location.hostname.includes('movergpt.com') && config.apiUrl !== window.location.origin) {
            console.warn(`Running on movergpt.com - overriding apiUrl from ${config.apiUrl} to ${window.location.origin}`);
            config.apiUrl = window.location.origin;
        } else {
            console.log(`Using provided API URL: ${config.apiUrl}`);
        }
        
        // Save staff email to localStorage if provided
        if (options.staffEmail) {
            localStorage.setItem('staff_email', options.staffEmail);
            console.log('Saved staff email to localStorage:', options.staffEmail);
        }
        
        // Validate required options
        if (!config.companyId) {
            console.error('Moving Calculator Error: Company ID is required');
            return;
        }
        
        if (!config.apiUrl) {
            console.error('Moving Calculator Error: API URL is required');
            return;
        }
        
        if (!config.apiKey) {
            console.error('Moving Calculator Error: API Key is required for authentication');
            return;
        }
        
        if (!config.websiteUrl) {
            // Default to current origin if not provided
            config.websiteUrl = window.location.origin;
            console.warn('Moving Calculator Warning: Website URL not provided, using current origin');
        }
        
        // Verify this is an allowed domain
        const currentDomain = window.location.hostname;
        const allowedDomain = new URL(config.websiteUrl).hostname;
        
        if (currentDomain !== allowedDomain && currentDomain !== 'localhost' && !currentDomain.includes('127.0.0.1')) {
            console.error(`Moving Calculator Error: This widget is not authorized for use on ${currentDomain}`);
            
            // Get container element
            const container = document.getElementById(config.containerId);
            if (container) {
                container.innerHTML = `
                    <div style="color: red; text-align: center; padding: 20px;">
                        <h3>Authentication Error</h3>
                        <p>This moving calculator is not authorized for use on this domain.</p>
                        <p>Please contact the widget provider for assistance.</p>
                    </div>
                `;
            }
            return;
        }
        
        // Get container element
        const container = document.getElementById(config.containerId);
        if (!container) {
            console.error(`Moving Calculator Error: Container element with ID "${config.containerId}" not found`);
            return;
        }
        
        // Load Google Maps API if not already loaded
        if (typeof google === 'undefined' || typeof google.maps === 'undefined') {
            loadGoogleMapsScript();
        }
        
        // Create and render the widget
        renderWidget(container);
        
        // Add event listeners
        attachEventListeners();
        
        // Fetch moving parameters to get additional service costs
        fetch(`${config.apiUrl}/api/companies/${config.companyId}/moving-parameters`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.apiKey}`
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.parameters) {
                // Store additional services and rate adjustments from parameters
                config.additionalServiceCosts = data.parameters.additional_service_costs || {};
                config.rateAdjustments = data.parameters.rate_adjustments || {};
                console.log('Loaded additional service costs:', config.additionalServiceCosts);
                console.log('Loaded rate adjustments:', config.rateAdjustments);
            } else {
                console.warn('Failed to load moving parameters:', data.error);
            }
        })
        .catch(err => console.error('Error fetching moving parameters:', err));
    }

    /**
     * Create and render the widget
     * @param {HTMLElement} container - Container element
     */
    function renderWidget(container) {
        // Clear container
        container.innerHTML = '';
        
        // Add custom styles
        const calculatorStyles = document.createElement('style');
        calculatorStyles.textContent = `
            .moving-calculator {
                font-family: ${config.fontFamily};
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                background-color: #fff;
            }
            
            .moving-calculator h2 {
                text-align: center;
                color: ${config.primaryColor};
                margin-bottom: 20px;
            }
            
            .moving-calculator .steps {
                display: flex;
                justify-content: space-between;
                margin-bottom: 30px;
            }
            
            .moving-calculator .step {
                flex: 1;
                text-align: center;
                position: relative;
            }
            
            .moving-calculator .step-number {
                display: inline-block;
                width: 30px;
                height: 30px;
                line-height: 30px;
                border-radius: 50%;
                background-color: #ddd;
                text-align: center;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            .moving-calculator .step.active .step-number {
                background-color: ${config.primaryColor};
                color: #fff;
            }
            
            .moving-calculator .step.completed .step-number {
                background-color: #28a745;
                color: #fff;
            }
            
            .moving-calculator .step-label {
                font-size: 0.8rem;
                color: #666;
            }
            
            .moving-calculator .step.active .step-label {
                color: ${config.primaryColor};
                font-weight: bold;
            }
            
            .moving-calculator .form-group {
                margin-bottom: 15px;
            }
            
            .moving-calculator label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #333;
            }
            
            .moving-calculator input,
            .moving-calculator select {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 16px;
            }
            
            .moving-calculator input[type="date"] {
                padding: 9px;
            }
            
            .moving-calculator button {
                background-color: ${config.primaryColor};
                color: #fff;
                border: none;
                padding: 12px 20px;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
                transition: background-color 0.2s;
            }
            
            .moving-calculator button:hover {
                background-color: ${darkenColor(config.primaryColor, 20)};
            }
            
            .moving-calculator button.secondary {
                background-color: ${config.secondaryColor};
            }
            
            .moving-calculator button.secondary:hover {
                background-color: ${darkenColor(config.secondaryColor, 20)};
            }
            
            .moving-calculator .buttons {
                display: flex;
                justify-content: space-between;
                margin-top: 20px;
            }
            
            .moving-calculator .loader {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 50%;
                border-top-color: #fff;
                animation: spin 1s linear infinite;
                margin-right: 10px;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .moving-calculator .error {
                color: #dc3545;
                margin: 10px 0;
                padding: 10px;
                border-radius: 4px;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
            }
            
            .moving-calculator .summary {
                background-color: #f9f9f9;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
            }
            
            .moving-calculator .summary-item {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            
            .moving-calculator .summary-total {
                font-weight: bold;
                border-top: 1px solid #ddd;
                padding-top: 8px;
                margin-top: 8px;
            }
            
            .moving-calculator .success-message {
                text-align: center;
                background-color: #d4edda;
                color: #155724;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }
            
            .pac-container {
                z-index: 10000; /* Ensure Google Maps dropdown appears above other elements */
            }
        `;
        document.head.appendChild(calculatorStyles);
        
        // Create widget HTML structure
        const widget = document.createElement('div');
        widget.className = 'moving-calculator';
        widget.innerHTML = `
            <h2>Moving Cost Calculator</h2>
            <div class="steps">
                <div class="step active" data-step="1">
                    <div class="step-number">1</div>
                    <div class="step-label">Origin & Destination</div>
                </div>
                <div class="step" data-step="2">
                    <div class="step-number">2</div>
                    <div class="step-label">Move Details</div>
                </div>
                <div class="step" data-step="3">
                    <div class="step-number">3</div>
                    <div class="step-label">Personal Info</div>
                </div>
                <div class="step" data-step="4">
                    <div class="step-number">4</div>
                    <div class="step-label">Quote Summary</div>
                </div>
            </div>
            <div id="moving-calculator-content">
                ${renderStepContent(1)}
            </div>
        `;
        
        container.appendChild(widget);
    }
    
    /**
     * Load Google Maps API script
     */
    function loadGoogleMapsScript() {
        console.log('Attempting to load Google Maps API...');
        
        // Check if Google Maps API is already loaded
        if (window.google && window.google.maps) {
            console.log('Google Maps API already loaded, setting up autocomplete...');
            setupAutocomplete();
            return;
        }
        
        // Create the script element
        const script = document.createElement('script');
        script.src = 'https://maps.googleapis.com/maps/api/js?key=AIzaSyAEHRFyXOPNzQadf6VLzIguRvhqCGZNiJA&libraries=places&callback=initGoogleMapsAutocomplete';
        script.async = true;
        script.defer = true;
        
        // Add error handling
        script.onerror = function() {
            console.error('Failed to load Google Maps API. Using fallback address input.');
        };
        
        // Define the callback function if not already defined
        if (!window.initGoogleMapsAutocomplete) {
            window.initGoogleMapsAutocomplete = function() {
                console.log('Google Maps API loaded from widget.js. Setting up autocomplete...');
                setupAutocomplete();
            };
        }
        
        // Append the script element to the document
        document.head.appendChild(script);
        
        // Set a timeout to ensure we don't wait forever
        setTimeout(function() {
            if (!window.google || !window.google.maps) {
                console.warn('Google Maps API did not load within timeout period. Using fallback address input.');
            }
        }, 5000);
    }
    
    /**
     * Set up Google Places Autocomplete for origin and destination fields
     */
    function setupAutocomplete() {
        const originInput = document.getElementById('moving-origin');
        const destinationInput = document.getElementById('moving-destination');
        
        // Configure zip code database for improved suggestions
        const zipPrefixes = {
            '1': 'New York Area, NY',
            '10': 'New York, NY',
            '100': 'Manhattan, NY',
            '101': 'Manhattan, NY',
            '102': 'Manhattan, NY',
            '104': 'Bronx, NY',
            '11': 'Brooklyn/Queens, NY',
            '110': 'Queens, NY',
            '112': 'Brooklyn, NY',
            // Many more ZIP prefixes here... (shortened for clarity)
        };
        
        // City and state database - will be used to enhance autocomplete results
        const majorCitiesAndStates = [
            { city: 'New York', state: 'NY', zip: '10001' },
            { city: 'Los Angeles', state: 'CA', zip: '90001' },
            { city: 'Chicago', state: 'IL', zip: '60601' },
            { city: 'Houston', state: 'TX', zip: '77001' },
            { city: 'Phoenix', state: 'AZ', zip: '85001' },
            // Many more cities and states... (shortened for clarity)
        ];
        
        // Try to use Google Places API for enhanced functionality
        if (originInput && window.google && google.maps && google.maps.places) {
            try {
                // Create autocomplete for origin with enhanced options
                const originAutocomplete = new google.maps.places.Autocomplete(originInput, {
                    types: ['geocode'],
                    componentRestrictions: { country: 'us' }
                });
                
                // Add listener for when a place is selected
                originAutocomplete.addListener('place_changed', function() {
                    const place = originAutocomplete.getPlace();
                    if (place && place.formatted_address) {
                        originInput.value = place.formatted_address;
                    }
                });
                
                console.log('Google Maps Autocomplete initialized for origin field');
            } catch (error) {
                console.warn('Error setting up Google Maps Autocomplete for origin field:', error);
            }
        }
        
        if (destinationInput && window.google && google.maps && google.maps.places) {
            try {
                // Create autocomplete for destination with enhanced options
                const destinationAutocomplete = new google.maps.places.Autocomplete(destinationInput, {
                    types: ['geocode'],
                    componentRestrictions: { country: 'us' }
                });
                
                // Add listener for when a place is selected
                destinationAutocomplete.addListener('place_changed', function() {
                    const place = destinationAutocomplete.getPlace();
                    if (place && place.formatted_address) {
                        destinationInput.value = place.formatted_address;
                    }
                });
                
                console.log('Google Maps Autocomplete initialized for destination field');
            } catch (error) {
                console.warn('Error setting up Google Maps Autocomplete for destination field:', error);
            }
        }
    }
    
    /**
     * Render the content for a specific step
     * @param {number} step - Step number
     * @returns {string} HTML content
     */
    function renderStepContent(step) {
        switch(step) {
            case 1:
                return `
                    <div class="form-group">
                        <label for="moving-origin">Origin Address</label>
                        <input type="text" id="moving-origin" placeholder="Enter your current address or zip code" value="${state.origin}">
                    </div>
                    <div class="form-group">
                        <label for="moving-destination">Destination Address</label>
                        <input type="text" id="moving-destination" placeholder="Enter your destination address or zip code" value="${state.destination}">
                    </div>
                    ${state.error ? `<div class="error">${state.error}</div>` : ''}
                    <div class="buttons">
                        <div></div> <!-- Empty div for spacing -->
                        <button id="moving-next-1" ${state.isLoading ? 'disabled' : ''}>
                            ${state.isLoading ? '<span class="loader"></span>' : ''}
                            Next
                        </button>
                    </div>
                `;
                
            case 2:
                // Get today's date in YYYY-MM-DD format for the min attribute
                const today = new Date().toISOString().split('T')[0];
                
                return `
                    <div class="summary">
                        <div class="summary-item">
                            <strong>Origin:</strong> ${state.origin}
                        </div>
                        <div class="summary-item">
                            <strong>Destination:</strong> ${state.destination}
                        </div>
                        <div class="summary-item">
                            <strong>Distance:</strong> ${state.distance.toFixed(2)} miles
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="moving-size">Move Size</label>
                        <select id="moving-size">
                            <option value="">Select move size</option>
                            <option value="studio" ${state.moveSize === 'studio' ? 'selected' : ''}>Studio Apartment</option>
                            <option value="1-bedroom" ${state.moveSize === '1-bedroom' ? 'selected' : ''}>1 Bedroom</option>
                            <option value="2-bedroom" ${state.moveSize === '2-bedroom' ? 'selected' : ''}>2 Bedroom</option>
                            <option value="3-bedroom" ${state.moveSize === '3-bedroom' ? 'selected' : ''}>3 Bedroom</option>
                            <option value="4-bedroom" ${state.moveSize === '4-bedroom' ? 'selected' : ''}>4 Bedroom</option>
                            <option value="office" ${state.moveSize === 'office' ? 'selected' : ''}>Office</option>
                            <option value="car" ${state.moveSize === 'car' ? 'selected' : ''}>Car Only</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="moving-date">Move Date</label>
                        <input type="date" id="moving-date" value="${state.moveDate}" min="${today}">
                    </div>
                    <div class="form-group">
                        <label>Additional Services</label>
                        <div class="additional-services">
                            <div class="service-option">
                                <input type="checkbox" id="packing-service" ${state.packingService ? 'checked' : ''}>
                                <label for="packing-service">
                                    Packing Service
                                    <div class="service-description">Professional packing of your belongings</div>
                                </label>
                            </div>
                            <div class="service-option">
                                <input type="checkbox" id="storage-service" ${state.storageService ? 'checked' : ''}>
                                <label for="storage-service">
                                    Storage Service
                                    <div class="service-description">Secure storage for your items</div>
                                </label>
                            </div>
                        </div>
                    </div>
                    ${state.error ? `<div class="error">${state.error}</div>` : ''}
                    <div class="buttons">
                        <button id="moving-prev-2" class="secondary">Previous</button>
                        <button id="moving-next-2" ${state.isLoading ? 'disabled' : ''}>
                            ${state.isLoading ? '<span class="loader"></span>' : ''}
                            Next
                        </button>
                    </div>
                `;
                
            case 3:
                return `
                    <div class="form-group">
                        <label for="customer-name">Full Name *</label>
                        <input type="text" id="customer-name" required value="${state.name}">
                    </div>
                    <div class="form-group">
                        <label for="customer-email">Email Address *</label>
                        <input type="email" id="customer-email" required value="${state.email}">
                    </div>
                    <div class="form-group">
                        <label for="customer-phone">Phone Number *</label>
                        <input type="tel" id="customer-phone" required value="${state.phone}">
                    </div>
                    ${state.error ? `<div class="error">${state.error}</div>` : ''}
                    <div class="buttons">
                        <button id="moving-prev-3" class="secondary">Previous</button>
                        <button id="moving-next-3" ${state.isLoading ? 'disabled' : ''}>
                            ${state.isLoading ? '<span class="loader"></span>' : ''}
                            Moving Estimate
                        </button>
                    </div>
                `;
                
            case 4:
                if (!state.estimate) {
                    return `
                        <div class="error">Sorry, something went wrong with calculating your quote. Please try again.</div>
                        <div class="buttons">
                            <button id="moving-prev-4" class="secondary">Previous</button>
                        </div>
                    `;
                }
                
                // Calculate individual service costs
                const baseCost = parseFloat(state.estimate.base_cost) || 0;
                const distanceCost = parseFloat(state.estimate.distance_cost) || 0;
                
                // Calculate packing cost using configured rates
                let packingCost = 0;
                if (state.packingService && config.additionalServiceCosts && config.additionalServiceCosts.packing) {
                    packingCost = parseFloat(config.additionalServiceCosts.packing[state.moveSize] || 0);
                }
                
                // Calculate storage cost using configured rates
                let storageCost = 0;
                if (state.storageService && config.additionalServiceCosts && config.additionalServiceCosts.storage) {
                    storageCost = parseFloat(config.additionalServiceCosts.storage[state.moveSize] || 0);
                }
                
                // Calculate additional services total
                const additionalServicesCost = packingCost + storageCost;
                
                // Calculate minimum total (sum of all individual costs)
                const minimumTotal = baseCost + distanceCost + additionalServicesCost;
                
                // Ensure minimum is not less than the sum of all services
                const finalMinimum = Math.max(minimumTotal, parseFloat(state.estimate.min_cost) || 0);
                
                // Calculate maximum based on multiplier from rate adjustments
                let maxMultiplier = 1;
                if (config.rateAdjustments && config.rateAdjustments.max_cost_multiplier) {
                    maxMultiplier = parseFloat(config.rateAdjustments.max_cost_multiplier) || 1;
                }
                const finalMaximum = finalMinimum * maxMultiplier;
                
                // Debug log to check values
                console.log('Cost Breakdown:', {
                    baseCost,
                    distanceCost,
                    packingCost,
                    storageCost,
                    additionalServicesCost,
                    minimumTotal,
                    finalMinimum,
                    finalMaximum,
                    estimate: state.estimate,
                    packingService: state.packingService,
                    storageService: state.storageService,
                    moveSize: state.moveSize
                });
                
                return `
                    <div class="summary">
                        <div class="summary-item">
                            <strong>Origin:</strong> ${state.origin}
                        </div>
                        <div class="summary-item">
                            <strong>Destination:</strong> ${state.destination}
                        </div>
                        <div class="summary-item">
                            <strong>Distance:</strong> ${state.distance.toFixed(2)} miles
                        </div>
                        <div class="summary-item">
                            <strong>Move Size:</strong> ${state.moveSize}
                        </div>
                        <div class="summary-item">
                            <strong>Move Date:</strong> ${formatDate(state.moveDate)}
                        </div>
                        ${state.packingService ? `
                        <div class="summary-item">
                            <strong>Packing Service:</strong> Yes
                        </div>` : ''}
                        ${state.storageService ? `
                        <div class="summary-item">
                            <strong>Storage Service:</strong> Yes
                        </div>` : ''}
                    </div>
                    <h3>Your Moving Estimate Breakdown</h3>
                    <div class="summary">
                        <div class="summary-item">
                            <span>Base Rate:</span>
                            <span>$${baseCost.toFixed(2)}</span>
                        </div>
                        <div class="summary-item">
                            <span>Distance Cost:</span>
                            <span>$${distanceCost.toFixed(2)}</span>
                        </div>
                        ${additionalServicesCost > 0 ? `
                            <div class="summary-item">
                                <span>Additional Services Cost:</span>
                                <span>$${additionalServicesCost.toFixed(2)}</span>
                            </div>
                            ${packingCost > 0 ? `
                                <div class="summary-item" style="margin-left: 20px; font-size: 0.9em; color: #666;">
                                    <span>• Packing Service:</span>
                                    <span>$${packingCost.toFixed(2)}</span>
                                </div>
                            ` : ''}
                            ${storageCost > 0 ? `
                                <div class="summary-item" style="margin-left: 20px; font-size: 0.9em; color: #666;">
                                    <span>• Storage Service:</span>
                                    <span>$${storageCost.toFixed(2)}</span>
                                </div>
                            ` : ''}
                        ` : ''}
                        <div class="summary-item summary-total">
                            <span><strong>Total Estimated Cost:</strong></span>
                            <span><strong>$${finalMinimum.toFixed(2)} - $${finalMaximum.toFixed(2)}</strong></span>
                        </div>
                    </div>
                    <div class="success-message">
                        <h3>Thank you!</h3>
                        ${state.quoteSubmitted ? 
                            `<p>We've received your details and a representative will contact you shortly.</p>
                             ${state.emailSent ? '<p>A quote confirmation has been sent to your email.</p>' : ''}` : 
                            `<p>Here is your estimated moving cost. Please note that this is an estimate and the actual cost may vary.</p>`
                        }
                    </div>
                    <div class="buttons">
                        <button id="moving-new-quote" class="secondary">New Quote</button>
                    </div>
                `;
                
            default:
                return '<div class="error">Invalid step</div>';
        }
    }

    /**
     * Attach event listeners to form elements
     */
    function attachEventListeners() {
        const container = document.getElementById(config.containerId);
        
        // Initialize Google Maps autocomplete if available
        if (window.google && window.maps && window.google.maps.places) {
            setupAutocomplete();
        } else {
            // Load Google Maps API if not already loaded
            loadGoogleMapsScript();
        }

        // Next button - Step 1
        container.addEventListener('click', function(e) {
            if (e.target.id === 'moving-next-1') {
                const origin = document.getElementById('moving-origin').value.trim();
                const destination = document.getElementById('moving-destination').value.trim();
                
                if (!origin || !destination) {
                    setState({ error: 'Please enter both origin and destination addresses' });
                    return;
                }
                
                setState({ isLoading: true, error: null, origin, destination });
                
                // Get distance from API - always use the configured API URL
                fetch(`${config.apiUrl}/api/companies/get-distance`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${config.apiKey}`
                    },
                    body: JSON.stringify({ origin, destination })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        setState({
                            isLoading: false,
                            currentStep: 2,
                            distance: data.distance.miles,
                            error: null
                        });
                        updateUI();
                    } else {
                        setState({ isLoading: false, error: data.error || 'Failed to calculate distance' });
                    }
                })
                .catch(error => {
                    setState({ isLoading: false, error: 'Failed to calculate distance. Please try again.' });
                });
            }
        });
        
        // Next button - Step 2
        container.addEventListener('click', function(e) {
            if (e.target.id === 'moving-next-2') {
                const moveSize = document.getElementById('moving-size').value.trim();
                const moveDate = document.getElementById('moving-date').value.trim();
                const packingService = document.getElementById('packing-service').checked;
                const storageService = document.getElementById('storage-service').checked;
                
                if (!moveSize) {
                    setState({ error: 'Please select your move size' });
                    return;
                }
                
                if (!moveDate) {
                    setState({ error: 'Please select your move date' });
                    return;
                }
                
                // Check if the selected date is not in the past
                const selectedDate = new Date(moveDate);
                const today = new Date();
                today.setHours(0, 0, 0, 0); // Set to beginning of the day for fair comparison
                
                if (selectedDate < today) {
                    setState({ error: 'Please select a date that is not in the past' });
                    return;
                }
                
                setState({
                    moveSize,
                    moveDate,
                    packingService,
                    storageService,
                    currentStep: 3,
                    error: null
                });
                updateUI();
            }
        });
        
        // Next button - Step 3
        container.addEventListener('click', function(e) {
            if (e.target.id === 'moving-next-3') {
                const name = document.getElementById('customer-name').value.trim();
                const email = document.getElementById('customer-email').value.trim();
                const phone = document.getElementById('customer-phone').value.trim();
                
                if (!name || !email || !phone) {
                    setState({ error: 'Please fill out all required fields' });
                    return;
                }
                
                // Simple email validation
                if (!validateEmail(email)) {
                    setState({ error: 'Please enter a valid email address' });
                    return;
                }
                
                // Simple phone validation
                if (!validatePhone(phone)) {
                    setState({ error: 'Please enter a valid phone number' });
                    return;
                }
                
                // Make sure we save all customer info to state immediately
                setState({ 
                    isLoading: true, 
                    name, 
                    email, 
                    phone,
                    error: null 
                });

                console.log("Saved customer information to state:", { name, email, phone });
                
                // Calculate cost
                fetch(`${config.apiUrl}/api/companies/calculate-moving-cost`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${config.apiKey}`
                    },
                    body: JSON.stringify({
                        company_id: config.companyId,
                        origin: state.origin,
                        destination: state.destination,
                        move_size: state.moveSize,
                        distance: state.distance,
                        packing_service: state.packingService,
                        storage_service: state.storageService
                    })
                })
                .then(response => response.json())
                .then(costData => {
                    // Debug log the API response
                    console.log('Cost Calculation API Response:', costData);
                    console.log('Additional Services in Response:', {
                        packing: costData.estimate?.packing_cost,
                        storage: costData.estimate?.storage_cost,
                        hasPacking: Boolean(costData.estimate?.packing_cost),
                        hasStorage: Boolean(costData.estimate?.storage_cost)
                    });
                    
                    if (costData.success) {
                        // Debug logging of customer info before submitting
                        console.log('Submitting quote with customer info:', {
                            name: state.name,
                            email: state.email,
                            phone: state.phone
                        });
                        
                        // Prepare the quote data
                        const quoteData = {
                            company_id: config.companyId,
                            origin: state.origin,
                            destination: state.destination,
                            distance_miles: state.distance,
                            move_size: state.moveSize,
                            move_date: state.moveDate,
                            customer_name: state.name,
                            customer_email: state.email,
                            customer_phone: state.phone,
                            recipient_email: state.email,
                            total_cost: costData.estimate.max_cost,
                            additional_services: {
                                packing: state.packingService,
                                storage: state.storageService
                            },
                            notes: 'Submitted via online calculator'
                        };
                        
                        console.log('Quote submission data:', quoteData);
                        
                        // Submit quote request
                        fetch(`${config.apiUrl}/api/companies/submit-moving-quote`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${config.apiKey}`
                            },
                            body: JSON.stringify(quoteData)
                        })
                        .then(response => {
                            if (!response.ok) {
                                console.warn('Failed to submit quote request, but continuing with quote display');
                            }
                            return response.json().catch(e => {
                                // Ignore JSON parse errors, just return empty object
                                return {};
                            });
                        })
                        .then(submitData => {
                            // Continue regardless of success/failure
                            setState({
                                isLoading: false,
                                currentStep: 4,
                                estimate: costData.estimate,
                                error: null,
                                quoteSubmitted: submitData.success || false,
                                emailSent: submitData.email_sent || false
                            });
                            updateUI();
                            
                            // Send confirmation email with debug mode in a separate try-catch
                            try {
                                console.log('Sending confirmation email with debug mode...');
                                // Use setTimeout to give the UI a chance to update first
                                setTimeout(() => {
                                    try {
                                        sendConfirmationEmail(true);
                                    } catch (emailError) {
                                        console.error('Error in sendConfirmationEmail:', emailError);
                                    }
                                }, 500);
                            } catch (outerError) {
                                console.error('Fatal error initiating email send:', outerError);
                            }
                        })
                        .catch(error => {
                            // Continue even if the quote submission failed
                            console.error('Error submitting quote:', error);
                            setState({
                                isLoading: false,
                                currentStep: 4,
                                estimate: costData.estimate,
                                error: null,
                                quoteSubmitted: false,
                                emailSent: false
                            });
                            updateUI();
                        });
                    } else {
                        throw new Error(costData.error || 'Failed to calculate moving cost');
                    }
                })
                .catch(error => {
                    setState({ isLoading: false, error: error.message || 'Something went wrong. Please try again.' });
                });
            }
        });
        
        // Previous buttons
        container.addEventListener('click', function(e) {
            if (e.target.id === 'moving-prev-2') {
                setState({ currentStep: 1, error: null });
                updateUI();
            } else if (e.target.id === 'moving-prev-3') {
                setState({ currentStep: 2, error: null });
                updateUI();
            } else if (e.target.id === 'moving-prev-4') {
                setState({ currentStep: 3, error: null });
                updateUI();
            }
        });
        
        // New quote button
        container.addEventListener('click', function(e) {
            if (e.target.id === 'moving-new-quote') {
                setState({
                    currentStep: 1,
                    origin: '',
                    destination: '',
                    distance: 0,
                    moveSize: '',
                    moveDate: '',
                    name: '',
                    email: '',
                    phone: '',
                    packingService: false,
                    storageService: false,
                    estimate: null,
                    isLoading: false,
                    error: null,
                    quoteSubmitted: false
                });
                updateUI();
            }
        });
    }
    
    /**
     * Send confirmation email with estimate details
     * @param {boolean} debug - If true, show more detailed logs
     */
    function sendConfirmationEmail(debug = false) {
        if (debug) console.log('DEBUG MODE: Starting sendConfirmationEmail function');
        
        // Safely get form field values with error handling
        let customerName = '';
        let customerEmail = '';
        let customerPhone = '';
        
        try {
            const nameField = document.getElementById('customer-name');
            const emailField = document.getElementById('customer-email');
            const phoneField = document.getElementById('customer-phone');
            
            if (debug) {
                console.log('DEBUG MODE: Form fields:', {
                    nameField: nameField,
                    emailField: emailField,
                    phoneField: phoneField
                });
            }
            
            customerName = nameField ? nameField.value || 'Not provided' : state.name || 'Not provided';
            customerEmail = emailField ? emailField.value || 'no-reply@movergpt.com' : state.email || 'no-reply@movergpt.com';
            customerPhone = phoneField ? phoneField.value || 'Not provided' : state.phone || 'Not provided';
            
            // Store customer information in state for future use
            setState({
                name: customerName,
                email: customerEmail,
                phone: customerPhone
            });
            
            if (debug) console.log('DEBUG MODE: Updated state with customer info:', state);
        } catch(e) {
            console.error('Error retrieving customer form data:', e);
            if (debug) console.log('DEBUG MODE: Exception when getting customer data:', e);
            
            // Use state values if available, otherwise use defaults
            customerName = state.name || 'Form Customer';
            customerEmail = state.email || 'no-reply@movergpt.com';
            customerPhone = state.phone || 'Not provided';
        }

        if (debug) {
            console.log('DEBUG MODE: Customer info:', {
                name: customerName,
                email: customerEmail,
                phone: customerPhone
            });
        }

        // Get staff email from the input field in cost_calculator.html
        let staffEmail = 'info@movergpt.com'; // Default fallback email
        
        try {
            // Try to get staff email from input field
            const staffEmailInput = document.getElementById('staff_email');
            if (debug) console.log('DEBUG MODE: staffEmailInput =', staffEmailInput);
            
            if (staffEmailInput && staffEmailInput.value) {
                staffEmail = staffEmailInput.value;
                if (debug) console.log('DEBUG MODE: Using staff email from input field:', staffEmail);
            } 
            // If input not found or empty, try localStorage
            else {
                const savedStaffEmail = localStorage.getItem('staff_email');
                if (debug) console.log('DEBUG MODE: savedStaffEmail from localStorage =', savedStaffEmail);
                
                if (savedStaffEmail) {
                    staffEmail = savedStaffEmail;
                    if (debug) console.log('DEBUG MODE: Using staff email from localStorage:', staffEmail);
                } else {
                    if (debug) console.log('DEBUG MODE: No staff email found, using default:', staffEmail);
                }
            }
        } catch(e) {
            console.error('Error retrieving staff email:', e);
            if (debug) console.log('DEBUG MODE: Exception when retrieving staff email:', e);
            // Continue with default email
        }

        if (debug) console.log('DEBUG MODE: Final selected staff email:', staffEmail);
        
        // Safety check for required state properties
        if (!state.origin) state.origin = 'Not provided';
        if (!state.destination) state.destination = 'Not provided';
        if (!state.moveDate) state.moveDate = new Date().toISOString().split('T')[0];
        if (!state.moveSize) state.moveSize = 'Not provided';
        if (!state.distance) state.distance = 0;
        if (!state.estimate) {
            state.estimate = {
                base_cost: 0,
                distance_cost: 0,
                min_cost: 0,
                max_cost: 0
            };
        }
        
        const emailData = {
            customer_name: customerName,
            customer_email: customerEmail,
            customer_phone: customerPhone,
            recipient_email: customerEmail,
            staff_email: staffEmail,
            company_id: config.companyId,
            origin: state.origin,
            destination: state.destination,
            move_date: state.moveDate,
            move_size: state.moveSize,
            distance: state.distance,
            estimate: state.estimate,
            notify_staff: true,
            smtp_config: {
                server: "smtp.gmail.com",
                port: 587,
                username: "info@movergpt.com",
                password: "squx iyum vgaw yqhv"
            },
            debug_mode: debug
        };

        // Log the email data for debugging
        console.log('Sending email with data:', emailData);

        // Make the API call in a try-catch block
        try {
            fetch(`${config.apiUrl}/api/companies/send-estimate-email`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${config.apiKey}`
                },
                body: JSON.stringify(emailData)
            })
            .then(response => {
                if (debug) console.log('DEBUG MODE: API response status:', response.status);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (debug) console.log('DEBUG MODE: API response data:', data);
                
                if (data.success) {
                    setState({
                        emailSent: true
                    });
                    updateUI();
                } else {
                    console.error('Failed to send confirmation email:', data.error);
                    throw new Error(data.error || 'Failed to send email');
                }
            })
            .catch(error => {
                console.error('Error sending confirmation email:', error);
                if (debug) console.log('DEBUG MODE: Error in fetch operation:', error);
                
                setState({
                    error: 'Failed to send email. Please try again. Error: ' + error.message
                });
                updateUI();
            });
        } catch (outerError) {
            console.error('Fatal error in sendConfirmationEmail:', outerError);
            if (debug) console.log('DEBUG MODE: Fatal error in sendConfirmationEmail:', outerError);
            
            setState({
                error: 'Fatal error sending email: ' + outerError.message
            });
            updateUI();
        }
    }
    
    /**
     * Update the UI based on the current state
     */
    function updateUI() {
        const contentContainer = document.getElementById('moving-calculator-content');
        if (!contentContainer) return;
        
        // Update content
        contentContainer.innerHTML = renderStepContent(state.currentStep);
        
        // Update step indicators
        const steps = document.querySelectorAll('.moving-calculator .step');
        steps.forEach(step => {
            const stepNumber = parseInt(step.getAttribute('data-step'));
            step.classList.remove('active', 'completed');
            
            if (stepNumber === state.currentStep) {
                step.classList.add('active');
            } else if (stepNumber < state.currentStep) {
                step.classList.add('completed');
            }
        });
    }
    
    /**
     * Set state and optionally update UI
     * @param {Object} newState - State to merge
     */
    function setState(newState) {
        state = { ...state, ...newState };
    }
    
    /**
     * Helper function to darken a color
     * @param {string} color - Hex color
     * @param {number} percent - Percent to darken
     * @returns {string} Darkened color
     */
    function darkenColor(color, percent) {
        if (color.startsWith('#')) {
            color = color.substring(1);
        }
        
        let r = parseInt(color.substr(0, 2), 16);
        let g = parseInt(color.substr(2, 2), 16);
        let b = parseInt(color.substr(4, 2), 16);
        
        r = Math.floor(r * (100 - percent) / 100);
        g = Math.floor(g * (100 - percent) / 100);
        b = Math.floor(b * (100 - percent) / 100);
        
        r = (r < 10) ? '0' + r.toString(16) : r.toString(16);
        g = (g < 10) ? '0' + g.toString(16) : g.toString(16);
        b = (b < 10) ? '0' + b.toString(16) : b.toString(16);
        
        return '#' + r + g + b;
    }
    
    /**
     * Format date for display
     * @param {string} dateString - Date string in YYYY-MM-DD format
     * @returns {string} Formatted date
     */
    function formatDate(dateString) {
        if (!dateString) return '';
        
        const options = { year: 'numeric', month: 'long', day: 'numeric' };
        return new Date(dateString).toLocaleDateString(undefined, options);
    }
    
    /**
     * Validate email address
     * @param {string} email - Email to validate
     * @returns {boolean} Is valid
     */
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    /**
     * Validate phone number
     * @param {string} phone - Phone to validate
     * @returns {boolean} Is valid
     */
    function validatePhone(phone) {
        // Basic validation - at least 10 digits
        return /\d{10,}/.test(phone.replace(/\D/g, ''));
    }
    
    // Expose the init function globally
    window.initMovingCalculator = initMovingCalculator;
    
    // Expose test function for debugging
    window.testMovingCalculatorEmail = function(staffEmail = null, customerData = null) {
        console.log('Running email test function...');
        
        // Set dummy state if needed
        if (!state.origin || !state.destination || !state.moveDate || !state.moveSize || !state.distance || !state.estimate) {
            state = {
                ...state,
                origin: 'Test Origin, New York',
                destination: 'Test Destination, Los Angeles',
                moveDate: new Date().toISOString().split('T')[0],
                moveSize: '2-bedroom',
                distance: 2800,
                estimate: {
                    base_cost: 960,
                    distance_cost: 4200.00,
                    min_cost: 4128.00,
                    max_cost: 6192.00
                }
            };
        }
        
        // Set customer data if provided or use defaults
        if (customerData) {
            state.name = customerData.name || 'Test Customer';
            state.email = customerData.email || 'test@example.com';
            state.phone = customerData.phone || '555-123-4567';
            console.log('Set customer data for test:', { name: state.name, email: state.email, phone: state.phone });
        } else if (!state.name || !state.email || !state.phone) {
            // Set defaults if not provided and not in state
            state.name = 'Test Customer';
            state.email = 'test@example.com';
            state.phone = '555-123-4567';
            console.log('Set default customer data for test');
        }
        
        // Override staff email if provided
        if (staffEmail) {
            localStorage.setItem('staff_email', staffEmail);
            console.log('Set staff email for test:', staffEmail);
        }
        
        // Run confirmation email with debug
        try {
            sendConfirmationEmail(true);
            return "Email test initiated - check console for details";
        } catch(e) {
            console.error('Error in test function:', e);
            return "Error: " + e.message;
        }
    };
})(); 