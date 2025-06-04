/**
 * Chatbot Embed Script with Direct Proxy
 * This script allows embedding the chatbot on any website without CORS issues.
 */

(function() {
  // Configuration
  const defaultConfig = {
    chatbotId: null,
    companyId: null,
    apiKey: null,
    serverUrl: window.location.origin,
    websiteUrl: null,
    position: 'bottom-right',
    buttonIcon: '💬',
    buttonText: 'Chat with us',
    widgetTitle: 'Chatbot',
    primaryColor: '#4361ee',
    textColor: '#343a40',
    widgetWidth: '350px',
    widgetHeight: '500px',
    autoOpen: false
  };

  // Create a unique session ID for this user
  let sessionId = localStorage.getItem('chatbot_session_id');
  let accessToken = null;

  // Initialize the widget
  function initChatWidget(config) {
    const mergedConfig = { ...defaultConfig, ...config };
    
    // Store API key for later use
    accessToken = mergedConfig.apiKey;
    
    // Create the widget container
    const widgetContainer = document.createElement('div');
    widgetContainer.id = 'chatbot-widget-container';
    widgetContainer.style.position = 'fixed';
    widgetContainer.style.zIndex = '9999';
    
    // Set position based on config
    switch(mergedConfig.position) {
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
    }
    
    // Create the chat button
    const chatButton = document.createElement('button');
    chatButton.id = 'chatbot-button';
    chatButton.innerHTML = `${mergedConfig.buttonIcon} ${mergedConfig.buttonText}`;
    chatButton.style.backgroundColor = mergedConfig.primaryColor;
    chatButton.style.color = '#ffffff';
    chatButton.style.border = 'none';
    chatButton.style.borderRadius = '50px';
    chatButton.style.padding = '10px 20px';
    chatButton.style.cursor = 'pointer';
    chatButton.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.2)';
    chatButton.style.display = 'flex';
    chatButton.style.alignItems = 'center';
    chatButton.style.justifyContent = 'center';
    chatButton.style.gap = '8px';
    chatButton.style.fontFamily = "'Poppins', sans-serif";
    
    // Create the chat widget
    const chatWidget = document.createElement('div');
    chatWidget.id = 'chatbot-widget';
    chatWidget.style.display = 'none';
    chatWidget.style.flexDirection = 'column';
    chatWidget.style.position = 'absolute';
    chatWidget.style.bottom = '60px';
    chatWidget.style.right = '0';
    chatWidget.style.width = mergedConfig.widgetWidth;
    chatWidget.style.height = mergedConfig.widgetHeight;
    chatWidget.style.backgroundColor = '#ffffff';
    chatWidget.style.borderRadius = '10px';
    chatWidget.style.overflow = 'hidden';
    chatWidget.style.boxShadow = '0 5px 40px rgba(0, 0, 0, 0.16)';
    chatWidget.style.transition = 'all 0.3s ease';
    chatWidget.style.fontFamily = "'Poppins', sans-serif";
    
    // Create widget header
    const widgetHeader = document.createElement('div');
    widgetHeader.style.padding = '15px';
    widgetHeader.style.backgroundColor = mergedConfig.primaryColor;
    widgetHeader.style.color = '#ffffff';
    widgetHeader.style.display = 'flex';
    widgetHeader.style.justifyContent = 'space-between';
    widgetHeader.style.alignItems = 'center';
    
    const headerTitle = document.createElement('div');
    headerTitle.textContent = mergedConfig.widgetTitle;
    headerTitle.style.fontWeight = 'bold';
    
    const closeButton = document.createElement('button');
    closeButton.innerHTML = '&times;';
    closeButton.style.background = 'none';
    closeButton.style.border = 'none';
    closeButton.style.color = '#ffffff';
    closeButton.style.fontSize = '20px';
    closeButton.style.cursor = 'pointer';
    
    widgetHeader.appendChild(headerTitle);
    widgetHeader.appendChild(closeButton);
    
    // Create messages container
    const messagesContainer = document.createElement('div');
    messagesContainer.id = 'chatbot-messages';
    messagesContainer.style.flex = '1';
    messagesContainer.style.overflowY = 'auto';
    messagesContainer.style.padding = '15px';
    
    // Create input area
    const inputContainer = document.createElement('div');
    inputContainer.style.display = 'flex';
    inputContainer.style.padding = '10px';
    inputContainer.style.borderTop = '1px solid #dee2e6';
    
    const messageInput = document.createElement('input');
    messageInput.type = 'text';
    messageInput.id = 'chatbot-input';
    messageInput.placeholder = 'Type your message...';
    messageInput.style.flex = '1';
    messageInput.style.padding = '10px';
    messageInput.style.border = '1px solid #dee2e6';
    messageInput.style.borderRadius = '4px';
    messageInput.style.marginRight = '10px';
    
    const sendButton = document.createElement('button');
    sendButton.id = 'chatbot-send';
    sendButton.textContent = 'Send';
    sendButton.style.backgroundColor = mergedConfig.primaryColor;
    sendButton.style.color = '#ffffff';
    sendButton.style.border = 'none';
    sendButton.style.borderRadius = '4px';
    sendButton.style.padding = '10px 15px';
    sendButton.style.cursor = 'pointer';
    
    inputContainer.appendChild(messageInput);
    inputContainer.appendChild(sendButton);
    
    // Assemble the widget
    chatWidget.appendChild(widgetHeader);
    chatWidget.appendChild(messagesContainer);
    chatWidget.appendChild(inputContainer);
    
    widgetContainer.appendChild(chatWidget);
    widgetContainer.appendChild(chatButton);
    
    // Add the widget to the document
    document.body.appendChild(widgetContainer);
    
    // Add event listeners
    chatButton.addEventListener('click', toggleWidget);
    closeButton.addEventListener('click', toggleWidget);
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        sendMessage();
      }
    });
    
    // Initialize the session
    initSession(mergedConfig);
    
    // Auto open if configured
    if (mergedConfig.autoOpen) {
      toggleWidget();
    }
  }
  
  // Toggle the widget visibility
  function toggleWidget() {
    const widget = document.getElementById('chatbot-widget');
    const button = document.getElementById('chatbot-button');
    
    if (widget.style.display === 'none') {
      widget.style.display = 'flex';
      button.style.display = 'none';
    } else {
      widget.style.display = 'none';
      button.style.display = 'flex';
    }
  }
  
  // Initialize session with the server
  function initSession(config) {
    try {
      if (!sessionId) {
        // Create a hidden iframe to handle cross-origin communication
        const iframeId = 'chatbot-proxy-' + Math.random().toString(36).substring(2, 15);
        const iframe = document.createElement('iframe');
        iframe.id = iframeId;
        iframe.style.display = 'none';
        iframe.src = `${config.serverUrl}/static/proxy.html?action=init&apiKey=${encodeURIComponent(config.apiKey)}&chatbotId=${encodeURIComponent(config.chatbotId)}&companyId=${encodeURIComponent(config.companyId)}`;
        
        // Handle message from iframe
        window.addEventListener('message', function(event) {
          if (event.data && event.data.source === 'chatbot-proxy') {
            if (event.data.action === 'init') {
              if (event.data.status === 'success') {
                sessionId = event.data.session_id;
                localStorage.setItem('chatbot_session_id', sessionId);
                
                // Add welcome message
                addBotMessage("Hello! How can I help you today?");
              } else {
                addBotMessage("Sorry, I'm having trouble connecting to the server. Please try again later.");
                console.error("Error initializing session:", event.data.message);
              }
              
              // Remove the iframe
              document.body.removeChild(document.getElementById(iframeId));
            }
          }
        });
        
        // Add iframe to document
        document.body.appendChild(iframe);
      } else {
        // Session exists, fetch previous messages
        fetchMessages(config);
      }
    } catch (error) {
      console.error("Error initializing session:", error);
      addBotMessage("Sorry, I'm having trouble connecting to the server. Please try again later.");
    }
  }
  
  // Fetch messages for an existing session
  function fetchMessages(config) {
    try {
      // Create hidden iframe to fetch messages
      const iframeId = 'chatbot-proxy-' + Math.random().toString(36).substring(2, 15);
      const iframe = document.createElement('iframe');
      iframe.id = iframeId;
      iframe.style.display = 'none';
      iframe.src = `${config.serverUrl}/static/proxy.html?action=messages&apiKey=${encodeURIComponent(config.apiKey)}&sessionId=${encodeURIComponent(sessionId)}`;
      
      // Handle message from iframe
      window.addEventListener('message', function messageHandler(event) {
        if (event.data && event.data.source === 'chatbot-proxy' && event.data.action === 'messages') {
          // Remove event listener to avoid duplicates
          window.removeEventListener('message', messageHandler);
          
          if (event.data.status === 'success') {
            // Clear messages container
            const messagesContainer = document.getElementById('chatbot-messages');
            messagesContainer.innerHTML = '';
            
            // Display fetched messages
            event.data.messages.forEach(message => {
              if (message.sender === 'user') {
                addUserMessage(message.message);
              } else {
                addBotMessage(message.message);
              }
            });
          } else {
            console.error("Error fetching messages:", event.data.message);
            // Session might be invalid, create a new one
            localStorage.removeItem('chatbot_session_id');
            sessionId = null;
            initSession(config);
          }
          
          // Remove the iframe
          document.body.removeChild(document.getElementById(iframeId));
        }
      });
      
      // Add iframe to document
      document.body.appendChild(iframe);
    } catch (error) {
      console.error("Error fetching messages:", error);
    }
  }
  
  // Send a message
  function sendMessage() {
    const messageInput = document.getElementById('chatbot-input');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // Clear input
    messageInput.value = '';
    
    // Add user message to UI
    addUserMessage(message);
    
    // Get bot response using iframe proxy
    getBotResponse(message, defaultConfig);
  }
  
  // Get response from the bot
  function getBotResponse(userMessage, config) {
    try {
      // Show typing indicator
      const typingIndicator = addTypingIndicator();
      
      // Create hidden iframe to get bot response
      const iframeId = 'chatbot-proxy-' + Math.random().toString(36).substring(2, 15);
      const iframe = document.createElement('iframe');
      iframe.id = iframeId;
      iframe.style.display = 'none';
      iframe.src = `${config.serverUrl}/static/proxy.html?action=inference&apiKey=${encodeURIComponent(config.apiKey)}&sessionId=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(userMessage)}&companyId=${encodeURIComponent(config.companyId)}&websiteUrl=${encodeURIComponent(config.websiteUrl || window.location.href)}`;
      
      // Handle message from iframe
      window.addEventListener('message', function messageHandler(event) {
        if (event.data && event.data.source === 'chatbot-proxy' && event.data.action === 'inference') {
          // Remove event listener to avoid duplicates
          window.removeEventListener('message', messageHandler);
          
          // Remove typing indicator
          typingIndicator.remove();
          
          if (event.data.status === 'success') {
            addBotMessage(event.data.response);
          } else {
            console.error("Error getting bot response:", event.data.message);
            addBotMessage("Sorry, I couldn't process your request. Please try again.");
          }
          
          // Remove the iframe
          document.body.removeChild(document.getElementById(iframeId));
        }
      });
      
      // Add iframe to document
      document.body.appendChild(iframe);
    } catch (error) {
      console.error("Error getting bot response:", error);
      addBotMessage("Sorry, I'm having trouble connecting to the server. Please check your connection.");
    }
  }
  
  // Add user message to UI
  function addUserMessage(message) {
    const messagesContainer = document.getElementById('chatbot-messages');
    
    const messageElement = document.createElement('div');
    messageElement.className = 'user-message';
    messageElement.style.display = 'flex';
    messageElement.style.justifyContent = 'flex-end';
    messageElement.style.marginBottom = '10px';
    
    const messageBubble = document.createElement('div');
    messageBubble.textContent = message;
    messageBubble.style.backgroundColor = defaultConfig.primaryColor;
    messageBubble.style.color = '#ffffff';
    messageBubble.style.padding = '10px 15px';
    messageBubble.style.borderRadius = '18px 18px 0 18px';
    messageBubble.style.maxWidth = '80%';
    messageBubble.style.wordWrap = 'break-word';
    
    messageElement.appendChild(messageBubble);
    messagesContainer.appendChild(messageElement);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
  // Add bot message to UI
  function addBotMessage(message) {
    const messagesContainer = document.getElementById('chatbot-messages');
    
    const messageElement = document.createElement('div');
    messageElement.className = 'bot-message';
    messageElement.style.display = 'flex';
    messageElement.style.justifyContent = 'flex-start';
    messageElement.style.marginBottom = '10px';
    
    const messageBubble = document.createElement('div');
    messageBubble.textContent = message;
    messageBubble.style.backgroundColor = '#f0f0f0';
    messageBubble.style.color = defaultConfig.textColor;
    messageBubble.style.padding = '10px 15px';
    messageBubble.style.borderRadius = '18px 18px 18px 0';
    messageBubble.style.maxWidth = '80%';
    messageBubble.style.wordWrap = 'break-word';
    
    messageElement.appendChild(messageBubble);
    messagesContainer.appendChild(messageElement);
    
    // Scroll to bottom
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
    messageBubble.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    messageBubble.style.backgroundColor = '#f0f0f0';
    messageBubble.style.padding = '14px 18px';
    messageBubble.style.borderRadius = '18px 18px 18px 0';
    
    // Style the dots
    const style = document.createElement('style');
    style.textContent = `
      .typing-indicator .dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #aaa;
        margin: 0 2px;
        animation: pulse 1.5s infinite;
      }
      
      .typing-indicator .dot:nth-child(2) {
        animation-delay: 0.2s;
      }
      
      .typing-indicator .dot:nth-child(3) {
        animation-delay: 0.4s;
      }
      
      @keyframes pulse {
        0%, 100% { opacity: 0.3; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1); }
      }
    `;
    document.head.appendChild(style);
    
    messageElement.appendChild(messageBubble);
    messagesContainer.appendChild(messageElement);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return messageElement;
  }
  
  // Expose the init function globally
  window.initChatbot = initChatWidget;
})();
