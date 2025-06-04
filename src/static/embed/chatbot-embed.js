// Chatbot Widget Embed Script
(function() {
    // Check if the script is loaded in a browser environment
    if (typeof window === 'undefined') {
        console.error('This script must be loaded in a browser environment');
        return;
    }

    // Define the initChatbot function
    window.initChatbot = function(config) {
        try {
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

            // Merge default config with user config
            const finalConfig = { ...defaultConfig, ...config };

            // Create widget container
            const widgetContainer = document.createElement('div');
            widgetContainer.id = 'chatbot-widget-container';
            widgetContainer.style.cssText = `
                position: fixed;
                ${finalConfig.buttonPosition === 'bottom-right' ? 'right: 20px;' : 'left: 20px;'}
                bottom: 20px;
                z-index: 9999;
            `;

            // Create chat button
            const chatButton = document.createElement('button');
            chatButton.id = 'chatbot-button';
            chatButton.style.cssText = `
                background-color: ${finalConfig.primaryColor};
                color: white;
                border: none;
                border-radius: 50px;
                padding: 12px 24px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 16px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
            `;
            chatButton.innerHTML = `
                <span>${finalConfig.buttonIcon}</span>
                <span>${finalConfig.buttonText}</span>
            `;

            // Create chat window
            const chatWindow = document.createElement('div');
            chatWindow.id = 'chatbot-window';
            chatWindow.style.cssText = `
                position: fixed;
                ${finalConfig.buttonPosition === 'bottom-right' ? 'right: 20px;' : 'left: 20px;'}
                bottom: 80px;
                width: 350px;
                height: 500px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                display: none;
                flex-direction: column;
            `;

            // Create chat header
            const chatHeader = document.createElement('div');
            chatHeader.style.cssText = `
                background-color: ${finalConfig.primaryColor};
                color: white;
                padding: 15px;
                border-radius: 8px 8px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            `;
            chatHeader.innerHTML = `
                <h3 style="margin: 0;">${finalConfig.widgetTitle}</h3>
                <button id="close-chat" style="background: none; border: none; color: white; cursor: pointer;">×</button>
            `;

            // Create chat body
            const chatBody = document.createElement('div');
            chatBody.id = 'chatbot-messages';
            chatBody.style.cssText = `
                flex: 1;
                padding: 15px;
                overflow-y: auto;
                background: #f5f5f5;
            `;

            // Create chat input
            const chatInput = document.createElement('div');
            chatInput.style.cssText = `
                padding: 15px;
                background: white;
                border-top: 1px solid #eee;
                display: flex;
                gap: 10px;
            `;
            chatInput.innerHTML = `
                <input type="text" id="chatbot-input" placeholder="Type your message..." style="flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                <button id="send-message" style="padding: 8px 15px; background-color: ${finalConfig.primaryColor}; color: white; border: none; border-radius: 4px; cursor: pointer;">Send</button>
            `;

            // Assemble chat window
            chatWindow.appendChild(chatHeader);
            chatWindow.appendChild(chatBody);
            chatWindow.appendChild(chatInput);

            // Add elements to container
            widgetContainer.appendChild(chatButton);
            widgetContainer.appendChild(chatWindow);
            document.body.appendChild(widgetContainer);

            // Chat state
            let isChatOpen = false;

            // Toggle chat window
            function toggleChat() {
                isChatOpen = !isChatOpen;
                chatWindow.style.display = isChatOpen ? 'flex' : 'none';
                chatButton.style.opacity = isChatOpen ? '0.7' : '1';
            }

            // Event listeners
            chatButton.addEventListener('click', toggleChat);
            document.getElementById('close-chat').addEventListener('click', toggleChat);

            // Handle sending messages
            document.getElementById('send-message').addEventListener('click', sendMessage);
            document.getElementById('chatbot-input').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });

            function sendMessage() {
                const input = document.getElementById('chatbot-input');
                const message = input.value.trim();
                
                if (message) {
                    // Add user message to chat
                    addMessage(message, 'user');
                    input.value = '';

                    // Simulate bot response (replace with actual API call)
                    setTimeout(() => {
                        addMessage('This is a sample response from the chatbot. Replace this with actual API integration.', 'bot');
                    }, 1000);
                }
            }

            function addMessage(text, sender) {
                const messageDiv = document.createElement('div');
                messageDiv.style.cssText = `
                    margin-bottom: 10px;
                    padding: 10px;
                    border-radius: 8px;
                    max-width: 80%;
                    ${sender === 'user' ? 
                        'background-color: ' + finalConfig.primaryColor + '; color: white; margin-left: auto;' : 
                        'background-color: #eee; color: black; margin-right: auto;'}
                `;
                messageDiv.textContent = text;
                chatBody.appendChild(messageDiv);
                chatBody.scrollTop = chatBody.scrollHeight;
            }

            // Add welcome message
            addMessage('Hello! How can I help you today?', 'bot');

            console.log('Chatbot widget initialized successfully');
        } catch (error) {
            console.error('Error initializing chatbot:', error);
        }
    };

    // Log that the script has loaded
    console.log('Chatbot embed script loaded successfully');
})(); 