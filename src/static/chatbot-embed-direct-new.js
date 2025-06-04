/**
 * Chatbot Embed Script - Direct Approach
 * This script allows embedding the chatbot on any website without CORS issues.
 * Uses JSONP for cross-domain communication
 */

(function () {
  console.log('DEBUG: chatbot-embed-direct-new.js loaded');
  // Initialize embed JWT token (fallback to API key if none)
  let embedJwtToken = localStorage.getItem('jwt_access_token') || localStorage.getItem('access_token');
  console.log('DEBUG: initial embed JWT token:', embedJwtToken);
  // Try to retrieve JWT via global TokenManager if available
  if (!embedJwtToken && window.TokenManager && typeof window.TokenManager.getJwtToken === 'function') {
    embedJwtToken = window.TokenManager.getJwtToken();
    console.log('DEBUG: embed JWT token from TokenManager:', embedJwtToken);
  }
  // Add a flag to ensure welcome only shows once per page load
  let welcomeShownOnThisLoad = false;
  // Add a flag to ensure we load existing history only once per page load
  let historyLoaded = false;
  // Load Font Awesome icons for chat button
  const faScript = document.createElement('script');
  faScript.src = 'https://kit.fontawesome.com/6823100966.js';
  faScript.crossOrigin = 'anonymous';
  document.head.appendChild(faScript);

  // Global configuration
  let globalConfig = {
    chatbotId: null,
    companyId: null,
    apiKey: null,
    serverUrl: window.location.origin,
    websiteUrl: null,
    buttonPosition: 'bottom-right',
    buttonIcon: '💬',
    buttonText: 'Chat with us',
    widgetSubtitle: null,
    logoUrl: null,
    widgetTitle: 'Chatbot',
    primaryColor: '#4361ee',
    textColor: '#343a40',
    widgetWidth: '350px',
    widgetHeight: '610px',
    autoOpen: false,
    footerLogoUrl: 'https://www.movergpt.com/assets/img/logo2.0.webp',
    messageUrl: 'https://www.movergpt.com/assets/img/favicon.webp'
  };

  // Create or load session ID. Numeric (server) sessions are ready; local_session_ prefixes wait for server assignment
  let sessionId = localStorage.getItem('chatbot_session_id');
  let sessionReady = false;
  if (sessionId && !sessionId.startsWith('local_session_')) {
    // Already have a server-issued numeric session
    sessionReady = true;
  } else {
    // Generate provisional local session until server assigns real ID
    sessionId = 'local_session_' + Date.now();
    localStorage.setItem('chatbot_session_id', sessionId);
    sessionReady = false;
  }

  // Session history management
  function getSessionHistory() {
    const historyJson = localStorage.getItem('chatbot_session_history_' + sessionId);
    return historyJson ? JSON.parse(historyJson) : [];
  }

  function saveSessionHistory(history) {
    localStorage.setItem('chatbot_session_history_' + sessionId, JSON.stringify(history));
  }

  function getSessionId() {
    return sessionId;
  }

  // Initialize the widget
  function initChatWidget(config) {
    console.log('DEBUG: initChatWidget called with config:', config);
    // Merge with default config
    globalConfig = { ...globalConfig, ...config };
    // Support JWT passed via config for same-site auth
    if (config.token) {
      embedJwtToken = config.token;
      console.log('DEBUG: embed JWT token from config:', embedJwtToken);
    }
    console.log('DEBUG: final embed JWT token used:', embedJwtToken);

    console.log('Initializing chatbot with config:', {
      serverUrl: globalConfig.serverUrl,
      apiKey: globalConfig.apiKey ? globalConfig.apiKey.substring(0, 4) + '...' : 'undefined',
      companyId: globalConfig.companyId,
      chatbotId: globalConfig.chatbotId
    });

    // Create the widget container
    const widgetContainer = document.createElement('div');
    widgetContainer.id = 'chatbot-widget-container';
    widgetContainer.style.position = 'fixed';
    widgetContainer.style.zIndex = '9999';

    // Set position based on config
    switch (globalConfig.buttonPosition) {
      case 'bottom-right':
        widgetContainer.style.right = '20px';
        widgetContainer.style.bottom = '20px';
        break;
      case 'bottom-left':
        widgetContainer.style.left = '20px';
        widgetContainer.style.bottom = '20px';
        break;
      case 'top-right':
        widgetContainer.style.right = '20px';
        widgetContainer.style.top = '20px';
        break;
      case 'top-left':
        widgetContainer.style.left = '20px';
        widgetContainer.style.top = '20px';
        break;
      default:
        widgetContainer.style.right = '20px';
        widgetContainer.style.bottom = '20px';
    }

    // Create the chat button
    const chatButton = document.createElement('div');
    chatButton.id = 'chatbot-button';
    chatButton.style.backgroundColor = globalConfig.primaryColor;
    chatButton.style.color = '#ffffff';
    chatButton.style.borderRadius = '50%';
    chatButton.style.width = '60px';
    chatButton.style.height = '60px';
    chatButton.style.display = 'flex';
    chatButton.style.justifyContent = 'center';
    chatButton.style.alignItems = 'center';
    chatButton.style.cursor = 'pointer';
    chatButton.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
    chatButton.style.transition = 'all 0.3s ease';
    chatButton.innerHTML = `<i class="fas fa-comment" style="font-size:30px;color:#ffffff;"></i>`;
    chatButton.addEventListener('mouseover', function () {
      this.style.transform = 'scale(1.1)';
    });
    chatButton.addEventListener('mouseout', function () {
      this.style.transform = 'scale(1)';
    });

    // Create the chat widget
    const chatWidget = document.createElement('div');
    chatWidget.id = 'chatbot-widget';
    chatWidget.style.display = 'none';
    chatWidget.style.position = 'absolute';
    chatWidget.style.bottom = '80px';
    chatWidget.style.right = '0';
    chatWidget.style.width = globalConfig.widgetWidth;
    chatWidget.style.height = globalConfig.widgetHeight;
    chatWidget.style.backgroundColor = '#ffffff';
    chatWidget.style.borderRadius = '10px';
    chatWidget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
    chatWidget.style.overflow = 'hidden';
    chatWidget.style.flexDirection = 'column';
    chatWidget.style.transition = 'all 0.3s ease';

    // Create the header
    const chatHeader = document.createElement('div');
    chatHeader.style.backgroundColor = globalConfig.primaryColor;
    chatHeader.style.color = '#ffffff';
    chatHeader.style.padding = '15px';
    chatHeader.style.fontWeight = 'bold';
    chatHeader.style.display = 'flex';
    chatHeader.style.justifyContent = 'space-between';
    chatHeader.style.alignItems = 'center';
    chatHeader.innerHTML = `
      <div style="display: flex; align-items: center;">
        <div style="background: white; border-radius: 50%; width: 35px; height: 35px; display: flex; align-items: center; justify-content: center; margin-right: 10px;">
          <img src="${globalConfig.logoUrl}" alt="Company Logo" style="width:24px; height:24px; border-radius:50%;" />
        </div>
        <div>
          <div style="font-size: 16px; line-height: 20px; font-weight: bold;">${globalConfig.widgetTitle}</div>
          <div style="font-size: 12px; opacity: 0.8;">${globalConfig.widgetSubtitle || ''}</div>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 10px;">
        <div id="chatbot-feedback" style="cursor: pointer; font-size: 18px;">
          <svg width="33" height="33" viewBox="0 0 40 40" fill="none" style="vertical-align: middle;">
            <!-- Sad face (back, left, up) -->
            <g>
              <circle cx="15" cy="15" r="11" stroke="black" stroke-width="1" fill="white"></circle>
              <circle cx="11" cy="13" r="2" fill="black"></circle>
              <circle cx="19" cy="13" r="2" fill="black"></circle>
              <path d="M11 20C13 22 17 22 19 20" stroke="black" stroke-width="2" stroke-linecap="round"></path>
            </g>
            <!-- Happy face (front, right, down, clipped to overlap) -->
            <clipPath id="clip-happy">
              <circle cx="25" cy="25" r="13"></circle>
            </clipPath>
            <g clip-path="url(#clip-happy)">
              <circle cx="25" cy="25" r="13" stroke="black" stroke-width="3" fill="white"></circle>
              <circle cx="21" cy="23" r="2" fill="black"></circle>
              <circle cx="29" cy="23" r="2" fill="black"></circle>
              <path d="M21 28c2 2 6 2 8 0" stroke="black" stroke-width="2" stroke-linecap="round"></path>
            </g>
          </svg>
        </div>
        <div id="chatbot-delete" style="cursor: pointer; font-size: 18px; padding: 5px;"><i class="fa-sharp fa-solid fa-trash"></i></div>
        <div id="chatbot-close" style="cursor: pointer; font-size: 28px;">×</div>
      </div>
    `;

    // Create confirmation popup
    const confirmPopup = document.createElement('div');
    confirmPopup.id = 'chatbot-confirm-popup';
    confirmPopup.style.display = 'none';
    confirmPopup.style.position = 'absolute';
    confirmPopup.style.top = '50%';
    confirmPopup.style.left = '50%';
    confirmPopup.style.transform = 'translate(-50%, -50%)';
    confirmPopup.style.backgroundColor = '#ffffff';
    confirmPopup.style.padding = '20px';
    confirmPopup.style.borderRadius = '12px';
    confirmPopup.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    confirmPopup.style.zIndex = '1000';
    confirmPopup.style.width = '90%';
    confirmPopup.style.maxWidth = '248px';

    confirmPopup.innerHTML = `
    <div style="font-size: 18px; color: #1a1a1a; font-weight: 600; margin-bottom: 8px;">Clear chat</div>
    <div style="font-size: 14px; color: #666; margin-bottom: 20px;">After clearing history you won't be able to access previous chats.</div>
    <div style="display: flex; justify-content: flex-end; gap: 12px;">
      <button id="cancel-delete" style="
        padding: 8px 16px;
        background: none;
        border: none;
        color: #6366f1;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        border-radius: 6px;
      ">Cancel</button>
      <button id="confirm-delete" style="
        padding: 8px 16px;
        background-color: #6366f1;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
      ">Clear chat</button>
    </div>
  `;

    // Add overlay behind popup
    const overlay = document.createElement('div');
    overlay.id = 'chatbot-overlay';
    overlay.style.display = 'none';
    overlay.style.position = 'absolute';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.bottom = '0';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
    overlay.style.zIndex = '999';

    chatWidget.appendChild(overlay);
    chatWidget.appendChild(confirmPopup);

    // Create the messages container
    const messagesContainer = document.createElement('div');
    messagesContainer.id = 'chatbot-messages';
    messagesContainer.style.padding = '15px';
    messagesContainer.style.height = 'calc(100% - 120px)';
    messagesContainer.style.overflowY = 'auto';

    // Create the input area
    const inputArea = document.createElement('div');
    inputArea.style.padding = '10px 15px';
    inputArea.style.display = 'flex';
    inputArea.style.alignItems = 'center';
    inputArea.style.backgroundColor = '#ffffff';
    inputArea.style.position = 'relative';

    const inputField = document.createElement('input');
    inputField.id = 'chatbot-input';
    inputField.type = 'text';
    inputField.placeholder = 'Type a message...';
    inputField.style.width = '100%';
    inputField.style.padding = '12px 15px';
    inputField.style.border = '1px solid #e6e6e6';
    inputField.style.borderRadius = '20px';
    inputField.style.outline = 'none';
    inputField.style.fontSize = '14px';
    inputField.style.backgroundColor = '#ffffff';
    inputField.style.transition = 'all 0.3s ease';
    inputField.style.boxSizing = 'border-box';
    inputField.autocomplete = 'off';
    inputField.spellcheck = true;

    // Add input event listener to change border color
    inputField.addEventListener('input', function () {
      if (this.value.trim().length > 0) {
        this.style.border = '2px solid #1e88e5';
      } else {
        this.style.border = '1px solid #e6e6e6';
      }
    });

    // Reset border color when clicking outside
    document.addEventListener('click', function (e) {
      if (e.target !== inputField) {
        inputField.style.border = '1px solid #e6e6e6';
      }
    });

    const sendButton = document.createElement('button');
    sendButton.id = 'chatbot-send-button';
    sendButton.innerHTML = `<i class="fas fa-paper-plane" style="font-size:16px;color:#ffffff;transform:rotate(45deg);"></i>`;
    sendButton.style.marginLeft = '10px';
    sendButton.style.backgroundColor = '#cccccc';
    sendButton.style.color = '#ffffff';
    sendButton.style.border = 'none';
    sendButton.style.borderRadius = '50%';
    sendButton.style.width = '40px';
    sendButton.style.padding = '20px';
    sendButton.style.height = '40px';
    sendButton.style.cursor = 'pointer';
    sendButton.style.display = 'flex';
    sendButton.style.justifyContent = 'center';
    sendButton.style.alignItems = 'center';
    sendButton.style.flexShrink = '0';
    sendButton.style.transition = 'all 0.3s ease';

    // Update send button color based on input
    inputField.addEventListener('input', function () {
      sendButton.style.backgroundColor = this.value.trim().length > 0 ? '#1e88e5' : '#cccccc';
      sendButton.style.cursor = this.value.trim().length > 0 ? 'pointer' : 'default';
    });

    // Handle Enter key
    inputField.addEventListener('keypress', function (e) {
      if (e.key === 'Enter' && this.value.trim().length > 0) {
        sendUserMessage();
      }
    });

    // Handle send button click
    sendButton.addEventListener('click', function () {
      if (inputField.value.trim().length > 0) {
        sendUserMessage();
      }
    });

    // Assemble the input area
    inputArea.appendChild(inputField);
    inputArea.appendChild(sendButton);

    chatWidget.appendChild(chatHeader);
    chatWidget.appendChild(messagesContainer);
    chatWidget.appendChild(inputArea);

    // Insert the powered by footer inside the chat widget, below the input area
    const poweredBy = document.createElement('div');
    poweredBy.id = 'chatbot-powered-by';
    poweredBy.style.display = 'flex';
    poweredBy.style.justifyContent = 'center';
    poweredBy.style.alignItems = 'center';
    poweredBy.style.fontSize = '14px';
    poweredBy.style.color ='black';
    poweredBy.style.fontWeight = 'bold';
    poweredBy.style.marginTop = '2px';
    poweredBy.innerHTML = `
      <span>Powered by <a href="https://www.movergpt.com" target="_blank" style="color: ${globalConfig.primaryColor}; text-decoration: underline;">MoverGPT</a></span>
      <img src="${globalConfig.footerLogoUrl}" alt="MoverGPT Logo" style="width:40px; height:32px; margin-left:4px; margin-bottom: 4px;" />
    `;
    chatWidget.appendChild(poweredBy);

    // Create semi-transparent overlay behind feedback dialog
    const feedbackOverlay = document.createElement('div');
    feedbackOverlay.id = 'chatbot-feedback-overlay';
    feedbackOverlay.style.position = 'absolute';
    feedbackOverlay.style.top = '0';
    feedbackOverlay.style.left = '0';
    feedbackOverlay.style.width = '100%';
    feedbackOverlay.style.height = '100%';
    feedbackOverlay.style.backgroundColor = 'rgba(0,0,0,0.4)';
    feedbackOverlay.style.zIndex = '9998';
    feedbackOverlay.style.display = 'none';
    chatWidget.appendChild(feedbackOverlay);

    // Create feedback dialog inside the widget
    const feedbackDialog = document.createElement('div');
    feedbackDialog.id = 'chatbot-feedback-dialog';
    feedbackDialog.style.position = 'absolute';
    feedbackDialog.style.top = '50%';
    feedbackDialog.style.left = '50%';
    feedbackDialog.style.transform = 'translate(-50%, -50%)';
    feedbackDialog.style.backgroundColor = '#fff';
    feedbackDialog.style.boxSizing = 'border-box';
    feedbackDialog.style.width = '90%';
    feedbackDialog.style.maxWidth = '280px';
    feedbackDialog.style.border = `2px solid ${globalConfig.primaryColor}`;
    feedbackDialog.style.borderRadius = '12px';
    feedbackDialog.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)';
    feedbackDialog.style.padding = '20px';
    feedbackDialog.style.zIndex = '9999';
    feedbackDialog.style.display = 'none';
    feedbackDialog.innerHTML = `
      <div style="border-bottom:1px solid #eee;padding-bottom:10px;margin-bottom:15px;text-align:center;">
        <div style="font-size:18px;font-weight:bold;color:${globalConfig.primaryColor};">Rate this chat</div>
        <div style="font-size:12px;color:#666;">Your feedback matters!</div>
      </div>
      <div id="chatbot-star-container" style="display:flex;justify-content:center;gap:8px;margin-bottom:20px;align-items:baseline;">
        <div style="text-align:center;">
          <button class="chatbot-rating-btn" data-value="1" style="padding:12px; display:flex;align-items:center;justify-content:center;width:35px;height:35px;border-radius:50%;border:2px solid ${globalConfig.primaryColor};background:#fff;color:${globalConfig.primaryColor};font-size:14px;cursor:pointer;transition:all 0.2s ease;">1</button>
          <div style="font-size:12px;color:#666;margin-top:4px;">Poor</div>
        </div>
        <div style="text-align:center;">
          <button class="chatbot-rating-btn" data-value="2" style="padding:12px; display:flex;align-items:center;justify-content:center;width:35px;height:35px;border-radius:50%;border:2px solid ${globalConfig.primaryColor};background:#fff;color:${globalConfig.primaryColor};font-size:14px;cursor:pointer;transition:all 0.2s ease;">2</button>
        </div>
        <div style="text-align:center;">
          <button class="chatbot-rating-btn" data-value="3" style="padding:12px; display:flex;align-items:center;justify-content:center;width:35px;height:35px;border-radius:50%;border:2px solid ${globalConfig.primaryColor};background:#fff;color:${globalConfig.primaryColor};font-size:14px;cursor:pointer;transition:all 0.2s ease;">3</button>
        </div>
        <div style="text-align:center;">
          <button class="chatbot-rating-btn" data-value="4" style="padding:12px; display:flex;align-items:center;justify-content:center;width:35px;height:35px;border-radius:50%;border:2px solid ${globalConfig.primaryColor};background:#fff;color:${globalConfig.primaryColor};font-size:14px;cursor:pointer;transition:all 0.2s ease;">4</button>
        </div>
        <div style="text-align:center;">
          <button class="chatbot-rating-btn" data-value="5" style="padding:12px; display:flex;align-items:center;justify-content:center;width:35px;height:35px;border-radius:50%;border:2px solid ${globalConfig.primaryColor};background:#fff;color:${globalConfig.primaryColor};font-size:14px;cursor:pointer;transition:all 0.2s ease;">5</button>
          <div style="font-size:12px;color:#666;margin-top:4px;">Excellent</div>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:10px;">
        <button id="chatbot-feedback-cancel" style="padding:8px 12px;border:2px solid ${globalConfig.primaryColor};background:#fff;color:${globalConfig.primaryColor};border-radius:4px;cursor:pointer;transition:all 0.2s ease;">Cancel</button>
        <button id="chatbot-feedback-submit" style="padding:8px 12px;background:${globalConfig.primaryColor};color:#fff;border:none;border-radius:4px;cursor:pointer;transition:all 0.2s ease;">Submit</button>
      </div>
    `;
    chatWidget.appendChild(feedbackDialog);

    // Append the chat button and chat widget container to the DOM
    widgetContainer.appendChild(chatButton);
    widgetContainer.appendChild(chatWidget);
    document.body.appendChild(widgetContainer);

    // Add event listeners
    chatButton.addEventListener('click', function () {
      toggleChatWidget();
    });

    document.getElementById('chatbot-close').addEventListener('click', function () {
      toggleChatWidget();
    });

    // Add event listeners for delete confirmation
    document.getElementById('chatbot-delete').addEventListener('click', function () {
      const popup = document.getElementById('chatbot-confirm-popup');
      const overlay = document.getElementById('chatbot-overlay');
      popup.style.display = 'block';
      overlay.style.display = 'block';
    });

    document.getElementById('cancel-delete').addEventListener('click', function () {
      const popup = document.getElementById('chatbot-confirm-popup');
      const overlay = document.getElementById('chatbot-overlay');
      popup.style.display = 'none';
      overlay.style.display = 'none';
    });

    document.getElementById('confirm-delete').addEventListener('click', function () {
      // Clear chat history and UI
      saveSessionHistory([]);
      const messages = document.getElementById('chatbot-messages');
      if (messages) messages.innerHTML = '';

      // Hide popup and overlay
      const popup = document.getElementById('chatbot-confirm-popup');
      const overlay = document.getElementById('chatbot-overlay');
      popup.style.display = 'none';
      overlay.style.display = 'none';

      // Show welcome message after deletion
      const welcome = "Hello! How can I help you today?";
      addBotMessage(welcome);
      const newHistory = getSessionHistory();
      newHistory.push({ role: 'assistant', content: welcome, timestamp: new Date().toISOString() });
      saveSessionHistory(newHistory);
    });

    // Add event listeners for feedback dialog
    document.getElementById('chatbot-feedback').addEventListener('click', function () {
      feedbackOverlay.style.display = 'block';
      feedbackDialog.style.display = 'block';
    });
    // Star selection logic
    let selectedRating = 0;
    const stars = feedbackDialog.querySelectorAll('#chatbot-star-container .chatbot-rating-btn');
    stars.forEach(b => {
      b.addEventListener('click', function () {
        selectedRating = parseInt(this.dataset.value);
        stars.forEach(btn => {
          const val = parseInt(btn.dataset.value);
          if (val <= selectedRating) {
            btn.style.backgroundColor = globalConfig.primaryColor;
            btn.style.color = '#ffffff';
            btn.style.transform = 'scale(1.1)';
          } else {
            btn.style.backgroundColor = '#ffffff';
            btn.style.color = globalConfig.primaryColor;
            btn.style.transform = 'scale(1)';
          }
        });
      });
    });
    // Cancel feedback dialog
    document.getElementById('chatbot-feedback-cancel').addEventListener('click', function () {
      feedbackDialog.style.display = 'none';
      feedbackOverlay.style.display = 'none';
    });
    // Submit rating
    document.getElementById('chatbot-feedback-submit').addEventListener('click', function () {
      if (selectedRating === 0) { alert('Please select a rating'); return; }
      const sessionId = getSessionId();
      const apiKey = globalConfig.apiKey;
      fetch(`${globalConfig.serverUrl}/api/chatbot/rate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey: apiKey, session_id: sessionId, rating: selectedRating })
      })
        .then(res => res.json())
        .then(data => {
          console.log('Feedback submitted:', data);
          addBotMessage('Thanks for your feedback!');
        })
        .catch(err => {
          console.error('Error submitting feedback:', err);
          addBotMessage('Failed to submit feedback.');
        })
        .finally(() => {
          feedbackDialog.style.display = 'none';
          feedbackOverlay.style.display = 'none';
          selectedRating = 0;
          stars.forEach(btn => {
            btn.style.backgroundColor = '#fff';
            btn.style.color = globalConfig.primaryColor;
            btn.style.transform = 'scale(1)';
          });
        });
    });

    // Toggle chat widget
    function toggleChatWidget() {
      const widget = document.getElementById('chatbot-widget');
      if (widget.style.display === 'none') {
        widget.style.display = 'flex';
        // Load and render existing session history if not already done
        const history = getSessionHistory();
        if (!historyLoaded && history.length > 0) {
          history.forEach(msg => {
            if (msg.role === 'user') {
              addUserMessage(msg.content);
            } else {
              addBotMessage(msg.content);
            }
          });
          historyLoaded = true;
        }
        // Show welcome only if no previous history
        if (history.length === 0 && !welcomeShownOnThisLoad) {
          const welcome = "Hello! How can I help you today?";
          addBotMessage(welcome);
          history.push({ role: 'assistant', content: welcome, timestamp: new Date().toISOString() });
          saveSessionHistory(history);
          welcomeShownOnThisLoad = true;
        }
      } else {
        widget.style.display = 'none';
      }
    }

    // Auto-open if configured
    if (globalConfig.autoOpen) {
      setTimeout(toggleChatWidget, 1000);
    }

    // Add Google Fonts
    const fontLink = document.createElement('link');
    fontLink.rel = 'stylesheet';
    fontLink.href = 'https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Outfit:wght@100..900&family=Plus+Jakarta+Sans:ital,wght@0,200..800;1,200..800&family=Rubik:ital,wght@0,300..900;1,300..900&display=swap';
    document.head.appendChild(fontLink);

    // Responsive style for full-page widget on small screens
    const responsiveStyle = document.createElement('style');
    responsiveStyle.textContent = `
      @media (max-width: 600px) {

        #chatbot-widget {
          position: fixed !important;
          left: 0 !important;
          top: 0 !important;
          width: 100% !important;
          bottom: 0 !important;
          border-radius: 0 !important;
          box-shadow: none !important;
          min-width: 0 !important;
          height: 100% !important;
        }
      }
    `;
    document.head.appendChild(responsiveStyle);

    // Create server-side chat session via JSONP (JWT cookie auth)
    const sessionCallbackName = 'chatbotSessionCb_' + Math.random().toString(36).substring(2, 15);
    window[sessionCallbackName] = function(data) {
      console.log('Server session created:', data);
      if (data.status === 'success' && data.session_id) {
        // Replace provisional ID with real session
        sessionId = data.session_id;
        localStorage.setItem('chatbot_session_id', sessionId);
        sessionReady = true;
      }
      // Cleanup
      delete window[sessionCallbackName];
      document.head.removeChild(sessionScript);
    };
    const sessionScript = document.createElement('script');
    // Build session creation URL with embedded JWT
    let sessionUrl = `${globalConfig.serverUrl}/api/chatbot/jsonp/session?callback=${sessionCallbackName}`;
    // Include JWT token for auth if available, else use API key fallback
    if (embedJwtToken) {
      sessionUrl += `&token=${encodeURIComponent(embedJwtToken)}`;
    } else if (globalConfig.apiKey) {
      sessionUrl += `&apiKey=${encodeURIComponent(globalConfig.apiKey)}`;
    }
    if (globalConfig.chatbotId) {
      sessionUrl += `&chatbotId=${encodeURIComponent(globalConfig.chatbotId)}`;
    }
    if (globalConfig.companyId) {
      sessionUrl += `&companyId=${encodeURIComponent(globalConfig.companyId)}`;
    }
    console.log('DEBUG: session JSONP URL:', sessionUrl);
    sessionScript.src = sessionUrl;
    document.head.appendChild(sessionScript);
  }

  // Helper to store messages to server via JSONP
  function storeMessageToServer(sender, message) {
    if (!sessionReady) {
      // Delay sending until real server session exists
      console.log('Session not ready, retrying storeMessageToServer');
      setTimeout(() => storeMessageToServer(sender, message), 200);
      return;
    }
    const cbName = 'chatbotStoreMsgCb_' + Math.random().toString(36).substring(2, 15);
    window[cbName] = function(resp) {
      console.log('Stored message result:', resp);
      delete window[cbName];
      document.head.removeChild(scriptMsg);
    };
    // Build add_message URL with embedded JWT
    const scriptMsg = document.createElement('script');
    let msgUrl = `${globalConfig.serverUrl}/api/chatbot/jsonp/session/${encodeURIComponent(sessionId)}/add_message?sender=${encodeURIComponent(sender)}&message=${encodeURIComponent(message)}&callback=${cbName}`;
    // Include JWT token for auth if available, else use API key fallback
    if (embedJwtToken) {
      msgUrl += `&token=${encodeURIComponent(embedJwtToken)}`;
    } else if (globalConfig.apiKey) {
      msgUrl += `&apiKey=${encodeURIComponent(globalConfig.apiKey)}`;
    }
    console.log('DEBUG: add_message JSONP URL:', msgUrl);
    scriptMsg.src = msgUrl;
    document.head.appendChild(scriptMsg);
  }

  // Send user message
  function sendUserMessage() {
    const inputField = document.getElementById('chatbot-input');
    const sendButton = document.getElementById('chatbot-send-button');
    const message = inputField.value.trim();

    if (!message) return;

    // Store user message on server
    storeMessageToServer('user', message);

    // Add to session history
    const history = getSessionHistory();
    history.push({
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    });
    saveSessionHistory(history);

    // Add to UI
    addUserMessage(message);

    // Clear input and reset styles
    inputField.value = '';
    inputField.style.border = '1px solid #e6e6e6';
    sendButton.style.backgroundColor = '#cccccc';
    sendButton.style.cursor = 'default';

    // Send to API
    sendMessageToAPI(message);
  }

  // Send message to API
  function sendMessageToAPI(message) {
    // Show typing indicator
    const typingIndicator = addTypingIndicator();

    // Create JSONP callback for inference
    const callbackName = 'chatbotCallback_' + Math.random().toString(36).substring(2, 15);
    // Prepare and load JSONP script
    const directApiUrl = `${globalConfig.serverUrl}/api/chatbot/direct/inference?apiKey=${encodeURIComponent(globalConfig.apiKey)}&sessionId=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(message)}&companyId=${encodeURIComponent(globalConfig.companyId)}&websiteUrl=${encodeURIComponent(globalConfig.websiteUrl || window.location.href)}`;
    console.log('API URL:', directApiUrl);
    const script = document.createElement('script');
    script.src = directApiUrl + '&callback=' + callbackName;
    document.head.appendChild(script);

    window[callbackName] = function (response) {
      console.log('Received response:', response);

      // Remove typing indicator
      if (typingIndicator) {
        typingIndicator.remove();
      }

      // Process the response
      if (response && response.status === 'success') {
        const botMsg = response.response;
        // Store bot message on server
        storeMessageToServer('assistant', botMsg);
        // Add to session history
        const history = getSessionHistory();
        history.push({ role: 'assistant', content: botMsg, timestamp: new Date().toISOString() });
        saveSessionHistory(history);

        // Add to UI
        addBotMessage(botMsg);
      } else {
        console.error('Error in API response:', response);
        addBotMessage("Sorry, I'm having trouble connecting to the server. Please try again later.");
      }

      // Clean up JSONP script
      document.head.removeChild(script);
      delete window[callbackName];
    };

    // Set up error handling
    script.onerror = function () {
      console.error('Script loading error');

      // Remove typing indicator
      if (typingIndicator) {
        typingIndicator.remove();
      }

      // Add error message
      addBotMessage("Sorry, I'm having trouble connecting to the server. Please try again later.");

      // Clean up
      document.head.removeChild(script);
      delete window[callbackName];
    };
  }

  // Add user message to UI
  function addUserMessage(message) {
    const messagesContainer = document.getElementById('chatbot-messages');

    // Create wrapper for entire message including timestamp
    const messageWrapper = document.createElement('div');
    messageWrapper.style.display = 'flex';
    messageWrapper.style.flexDirection = 'column';
    messageWrapper.style.width = '100%';
    messageWrapper.style.marginBottom = '4px';

    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'user-message';
    messageElement.style.display = 'flex';
    messageElement.style.alignItems = 'center';
    messageElement.style.width = '100%';

    // Create message bubble
    const messageBubble = document.createElement('div');
    messageBubble.style.backgroundColor = 'transparent';
    messageBubble.style.borderRadius = '8px';
    messageBubble.style.padding = '8px';
    messageBubble.style.display = 'flex';
    messageBubble.style.alignItems = 'baseline';
    messageBubble.style.gap = '8px';
    messageBubble.style.width = '100%';

    // Add user icon
    const userIcon = document.createElement('div');
    userIcon.style.width = '30px';
    userIcon.style.height = '30px';
    userIcon.style.borderRadius = '8px';
    userIcon.style.backgroundColor = '#f2f3f6';
    userIcon.style.display = 'flex';
    userIcon.style.justifyContent = 'center';
    userIcon.style.alignItems = 'center';
    userIcon.style.flexShrink = '0';
    userIcon.innerHTML = '<i class="fa-regular fa-user" style="color: #6d7081;"></i>';

    // Add message text for user message
    const messageText = document.createElement('div');
    messageText.style.display = 'flex';
    messageText.style.flexDirection = 'column';
    messageText.style.flex = '1';

    const messageContent = document.createElement('div');
    messageContent.textContent = message;
    messageContent.style.color = '#black';
    messageContent.style.fontSize = '14px';
    messageContent.style.fontWeight = '400';
    messageContent.style.lineHeight = '24px';
    messageContent.style.fontFamily = 'DM Sans, san-serif';
    messageContent.style.wordWrap = 'break-word';

    // Add timestamp inside message
    const time = new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    const timestampElement = document.createElement('div');
    timestampElement.style.fontSize = '11px';
    timestampElement.style.color = '#999';
    timestampElement.style.textAlign = 'end';
    timestampElement.style.marginTop = '4px';
    timestampElement.textContent = time;

    messageText.appendChild(messageContent);
    messageText.appendChild(timestampElement);
    messageBubble.appendChild(userIcon);
    messageBubble.appendChild(messageText);
    messageElement.appendChild(messageBubble);
    messageWrapper.appendChild(messageElement);
    messagesContainer.appendChild(messageWrapper);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Add bot message to UI
  function addBotMessage(message) {
    const messagesContainer = document.getElementById('chatbot-messages');

    // Create wrapper for entire message including timestamp
    const messageWrapper = document.createElement('div');
    messageWrapper.style.display = 'flex';
    messageWrapper.style.flexDirection = 'column';
    messageWrapper.style.width = '100%';
    messageWrapper.style.marginBottom = '4px';

    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'bot-message';
    messageElement.style.display = 'flex';
    messageElement.style.alignItems = 'center';
    messageElement.style.width = '100%';

    // Create message bubble
    const messageBubble = document.createElement('div');
    messageBubble.style.backgroundColor = '#f1f1f1';
    messageBubble.style.borderRadius = '8px';
    messageBubble.style.padding = '8px';
    messageBubble.style.display = 'flex';
    messageBubble.style.alignItems = 'flex-start';
    messageBubble.style.gap = '8px';
    messageBubble.style.width = '100%';

    // Add bot icon
    const botIcon = document.createElement('div');
    botIcon.style.width = '30px';
    botIcon.style.height = '30px';
    botIcon.style.borderRadius = '8px';
    botIcon.style.backgroundColor = '#4361ee';
    botIcon.style.display = 'flex';
    botIcon.style.justifyContent = 'center';
    botIcon.style.alignItems = 'center';
    botIcon.style.flexShrink = '0';
    botIcon.style.overflow = 'hidden';
    botIcon.style.border = '1px solid #e0e0e0';

    const botLogo = document.createElement('img');
    botLogo.src = globalConfig.messageUrl;
    botLogo.style.width = '100%';
    botLogo.style.height = '100%';
    botLogo.style.objectFit = 'cover';
    botIcon.appendChild(botLogo);

    // Add message text for bot message
    const messageText = document.createElement('div');
    messageText.style.display = 'flex';
    messageText.style.flexDirection = 'column';
    messageText.style.flex = '1';

    const messageContent = document.createElement('div');
    messageContent.textContent = message;
    messageContent.style.color = '#333333';
    messageContent.style.fontSize = '14px';
    messageContent.style.fontWeight = '400';
    messageContent.style.lineHeight = '24px';
    messageContent.style.fontFamily = 'DM Sans, san-serif';
    messageContent.style.wordWrap = 'break-word';

    // Add timestamp inside message
    const time = new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    const timestampElement = document.createElement('div');
    timestampElement.style.fontSize = '11px';
    timestampElement.style.color = '#999';
    timestampElement.style.marginTop = '4px';
    timestampElement.style.textAlign = 'end';
    timestampElement.textContent = time;

    messageText.appendChild(messageContent);
    messageText.appendChild(timestampElement);
    messageBubble.appendChild(botIcon);
    messageBubble.appendChild(messageText);
    messageElement.appendChild(messageBubble);
    messageWrapper.appendChild(messageElement);
    messagesContainer.appendChild(messageWrapper);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Add typing indicator
  function addTypingIndicator() {
    const messagesContainer = document.getElementById('chatbot-messages');

    const messageElement = document.createElement('div');
    messageElement.className = 'bot-message typing-indicator';
    messageElement.style.display = 'flex';
    messageElement.style.justifyContent = 'flex-start';
    messageElement.style.marginBottom = '10px';

    const messageBubble = document.createElement('div');
    messageBubble.style.backgroundColor = '#f1f1f1';
    messageBubble.style.padding = '10px 15px';
    messageBubble.style.borderRadius = '18px 18px 18px 0';

    // Create typing dots
    const typingDots = document.createElement('div');
    typingDots.style.display = 'flex';
    typingDots.style.alignItems = 'center';
    typingDots.style.justifyContent = 'center';
    typingDots.style.height = '20px';

    for (let i = 0; i < 3; i++) {
      const dot = document.createElement('div');
      dot.style.width = '6px';
      dot.style.height = '6px';
      dot.style.backgroundColor = '#888';
      dot.style.borderRadius = '50%';
      dot.style.margin = '0 2px';
      dot.style.animation = 'typingAnimation 1.5s infinite ease-in-out';
      dot.style.animationDelay = (i * 0.2) + 's';
      typingDots.appendChild(dot);
    }

    // Add animation style
    const style = document.createElement('style');
    style.textContent = `
    @keyframes typingAnimation {
      0%, 100% { opacity: 0.3; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1); }
    }
  `;
    document.head.appendChild(style);

    messageBubble.appendChild(typingDots);
    messageElement.appendChild(messageBubble);
    messagesContainer.appendChild(messageElement);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return messageElement;
  }

  // Expose the init function globally
  window.initChatbot = initChatWidget;
})();