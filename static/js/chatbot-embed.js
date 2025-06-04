// Chatbot Widget Embed Script
(function() {
    'use strict';

    // Check if we're in a browser environment
    if (typeof window === 'undefined') {
        console.error('chatbot-embed.js must be loaded in a browser environment');
        return;
    }

    // Main initialization function
    function initChatbot(config = {}) {
        try {
            console.log('Initializing chatbot with config:', config);
            
            // Default configuration
            const defaultConfig = {
                chatbotId: "1",
                websiteUrl: window.location.origin,
                buttonPosition: "bottom-right",
                buttonText: "Chat with us",
                buttonIcon: "💬",
                widgetTitle: "Chat Support",
                primaryColor: "#4361ee"
            };

            // Merge default config with provided config
            const finalConfig = { ...defaultConfig, ...config };

            // Create widget container
            const widgetContainer = document.createElement('div');
            widgetContainer.id = 'chatbot-widget-container';
            widgetContainer.style.position = 'fixed';
            widgetContainer.style.zIndex = '9999';
            widgetContainer.style[finalConfig.buttonPosition] = '20px';
            widgetContainer.style.bottom = '20px';

            // Create chat button
            const chatButton = document.createElement('button');
            chatButton.id = 'chatbot-button';
            chatButton.style.backgroundColor = finalConfig.primaryColor;
            chatButton.style.color = 'white';
            chatButton.style.border = 'none';
            chatButton.style.borderRadius = '50%';
            chatButton.style.width = '60px';
            chatButton.style.height = '60px';
            chatButton.style.cursor = 'pointer';
            chatButton.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
            chatButton.style.display = 'flex';
            chatButton.style.alignItems = 'center';
            chatButton.style.justifyContent = 'center';
            chatButton.style.fontSize = '24px';
            chatButton.innerHTML = finalConfig.buttonIcon;

            // Create chat window
            const chatWindow = document.createElement('div');
            chatWindow.id = 'chatbot-window';
            chatWindow.style.display = 'none';
            chatWindow.style.position = 'fixed';
            chatWindow.style.bottom = '90px';
            chatWindow.style.right = '20px';
            chatWindow.style.width = '350px';
            chatWindow.style.height = '500px';
            chatWindow.style.backgroundColor = 'white';
            chatWindow.style.borderRadius = '10px';
            chatWindow.style.boxShadow = '0 5px 20px rgba(0,0,0,0.2)';
            chatWindow.style.overflow = 'hidden';
            chatWindow.style.flexDirection = 'column';

            // Create chat header
            const chatHeader = document.createElement('div');
            chatHeader.style.backgroundColor = finalConfig.primaryColor;
            chatHeader.style.color = 'white';
            chatHeader.style.padding = '15px';
            chatHeader.style.display = 'flex';
            chatHeader.style.justifyContent = 'space-between';
            chatHeader.style.alignItems = 'center';
            chatHeader.innerHTML = `
                <h3 style="margin: 0;">${finalConfig.widgetTitle}</h3>
                <button id="close-chat" style="background: none; border: none; color: white; cursor: pointer; font-size: 20px;">×</button>
            `;

            // Create chat body
            const chatBody = document.createElement('div');
            chatBody.id = 'chatbot-messages';
            chatBody.style.flex = '1';
            chatBody.style.padding = '15px';
            chatBody.style.overflowY = 'auto';
            chatBody.style.display = 'flex';
            chatBody.style.flexDirection = 'column';
            chatBody.style.gap = '10px';

            // Create chat input
            const chatInput = document.createElement('div');
            chatInput.style.padding = '15px';
            chatInput.style.borderTop = '1px solid #eee';
            chatInput.style.display = 'flex';
            chatInput.style.gap = '10px';
            chatInput.innerHTML = `
                <input type="text" id="chatbot-input" style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px;" placeholder="Type your message...">
                <button id="send-message" style="padding: 10px 20px; background-color: ${finalConfig.primaryColor}; color: white; border: none; border-radius: 5px; cursor: pointer;">Send</button>
            `;

            // Assemble chat window
            chatWindow.appendChild(chatHeader);
            chatWindow.appendChild(chatBody);
            chatWindow.appendChild(chatInput);

            // Add elements to container
            widgetContainer.appendChild(chatButton);
            widgetContainer.appendChild(chatWindow);
            document.body.appendChild(widgetContainer);

            // Toggle chat window
            chatButton.addEventListener('click', () => {
                chatWindow.style.display = chatWindow.style.display === 'none' ? 'flex' : 'none';
            });

            // Close chat window
            document.getElementById('close-chat').addEventListener('click', () => {
                chatWindow.style.display = 'none';
            });

            // Send message
            document.getElementById('send-message').addEventListener('click', () => {
                const input = document.getElementById('chatbot-input');
                const message = input.value.trim();
                if (message) {
                    addMessage(message, 'user');
                    input.value = '';
                    
                    // Simulate bot response
                    setTimeout(() => {
                        addMessage('This is a sample response from the chatbot.', 'bot');
                    }, 1000);
                }
            });

            // Handle Enter key
            document.getElementById('chatbot-input').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    document.getElementById('send-message').click();
                }
            });

            // Add message to chat
            function addMessage(text, sender) {
                const messageDiv = document.createElement('div');
                messageDiv.style.maxWidth = '80%';
                messageDiv.style.padding = '10px 15px';
                messageDiv.style.borderRadius = '15px';
                messageDiv.style.marginBottom = '10px';
                messageDiv.style.wordBreak = 'break-word';
                
                if (sender === 'user') {
                    messageDiv.style.backgroundColor = finalConfig.primaryColor;
                    messageDiv.style.color = 'white';
                    messageDiv.style.alignSelf = 'flex-end';
                } else {
                    messageDiv.style.backgroundColor = '#f1f1f1';
                    messageDiv.style.color = 'black';
                    messageDiv.style.alignSelf = 'flex-start';
                }
                
                messageDiv.textContent = text;
                chatBody.appendChild(messageDiv);
                chatBody.scrollTop = chatBody.scrollHeight;
            }

            // Add welcome message
            setTimeout(() => {
                addMessage('Hello! How can I help you today?', 'bot');
            }, 500);

            console.log('Chatbot widget initialized successfully');
        } catch (error) {
            console.error('Error initializing chatbot:', error);
        }
    }

    // Export the function
    window.initChatbot = initChatbot;
})(); 