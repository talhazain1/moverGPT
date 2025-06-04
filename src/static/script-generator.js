/**
 * Script Generator Functionality
 * This file handles the script generator form and functionality
 */

document.addEventListener('DOMContentLoaded', function() {
  console.log('Script Generator: Initializing');
  
  // Elements
  const modalElement = document.getElementById('scriptGeneratorModal');
  const generateScriptBtn = document.getElementById('generateScriptBtn');
  const closeScriptModalBtn = document.getElementById('closeScriptModalBtn');
  const generateCodeBtn = document.getElementById('generateCodeBtn');
  const startOverBtn = document.getElementById('startOverBtn');
  const copyScriptBtn = document.getElementById('copyScriptBtn');
  const websiteStackSelect = document.getElementById('websiteStack');
  const chatbotSelect = document.getElementById('chatbotSelect');
  const scriptForm = document.getElementById('scriptGeneratorForm');
  const generatedScriptContainer = document.getElementById('generatedScriptContainer');
  const generatedScript = document.getElementById('generatedScript');
  const wordpressInstructions = document.getElementById('wordpressInstructions');
  
  // Check if elements exist
  console.log('Script Generator: Modal element exists:', !!modalElement);
  console.log('Script Generator: Generate script button exists:', !!generateScriptBtn);
  console.log('Script Generator: Form exists:', !!scriptForm);
  
  // Initialize Bootstrap modal
  let scriptModal = null;
  
  // Wait for Bootstrap to be loaded
  function initializeModal() {
    if (typeof bootstrap !== 'undefined') {
      if (modalElement) {
        scriptModal = new bootstrap.Modal(modalElement);
        console.log('Script Generator: Bootstrap modal initialized');
      }
    } else {
      // Retry in 100ms if Bootstrap is not yet loaded
      setTimeout(initializeModal, 100);
    }
  }
  
  // Initialize the modal
  initializeModal();
  
  // Open the modal when the button is clicked
  if (generateScriptBtn) {
    console.log('Script Generator: Adding click handler to button');
    
    generateScriptBtn.addEventListener('click', function(e) {
      console.log('Script Generator: Button clicked');
      e.preventDefault();
      
      // Ensure modal is initialized
      if (!scriptModal && typeof bootstrap !== 'undefined') {
        if (modalElement) {
          scriptModal = new bootstrap.Modal(modalElement);
        }
      }
      
      // Reset the form
      if (scriptForm) {
        scriptForm.reset();
      }
      
      // Set default values
      if (document.getElementById('buttonText')) document.getElementById('buttonText').value = 'Chat with us';
      if (document.getElementById('buttonIcon')) document.getElementById('buttonIcon').value = '💬';
      if (document.getElementById('widgetTitle')) document.getElementById('widgetTitle').value = 'Chat Support';
      if (document.getElementById('primaryColor')) document.getElementById('primaryColor').value = '#4361ee';
      
      // Populate the chatbot select dropdown
      populateChatbotSelect();
      
      // Hide the generated script container and show the form
      if (generatedScriptContainer) generatedScriptContainer.style.display = 'none';
      if (generateCodeBtn) generateCodeBtn.style.display = 'block';
      if (startOverBtn) startOverBtn.style.display = 'none';
      
      // Show the modal using Bootstrap if available
      if (scriptModal) {
        scriptModal.show();
        console.log('Script Generator: Modal shown with Bootstrap');
      } else if (typeof jQuery !== 'undefined' && jQuery.fn.modal) {
        // Fallback to jQuery
        jQuery(modalElement).modal('show');
        console.log('Script Generator: Modal shown with jQuery');
      } else {
        // Manual fallback as last resort
        if (modalElement) {
          modalElement.style.display = 'block';
          modalElement.classList.add('show');
          document.body.classList.add('modal-open');
          const backdrop = document.createElement('div');
          backdrop.className = 'modal-backdrop fade show';
          document.body.appendChild(backdrop);
          console.log('Script Generator: Modal shown manually');
        }
      }
    });
  }
  
  // Close modal button handler
  if (closeScriptModalBtn) {
    closeScriptModalBtn.addEventListener('click', function() {
      console.log('Script Generator: Close button clicked');
      if (scriptModal) {
        scriptModal.hide();
      } else if (typeof jQuery !== 'undefined' && jQuery.fn.modal) {
        jQuery(modalElement).modal('hide');
      } else {
        if (modalElement) {
          modalElement.style.display = 'none';
          modalElement.classList.remove('show');
          document.body.classList.remove('modal-open');
          const backdrop = document.querySelector('.modal-backdrop');
          if (backdrop) backdrop.remove();
        }
      }
    });
  }
  
  // Website stack change handler
  if (websiteStackSelect) {
    websiteStackSelect.addEventListener('change', function() {
      console.log('Script Generator: Website stack changed to', this.value);
      if (this.value === 'wordpress') {
        if (wordpressInstructions) wordpressInstructions.style.display = 'block';
      } else {
        if (wordpressInstructions) wordpressInstructions.style.display = 'none';
      }
    });
  }
  
  // Generate code button handler
  if (generateCodeBtn) {
    generateCodeBtn.addEventListener('click', function() {
      console.log('Script Generator: Generate code button clicked');
      
      // Check form validity
      if (scriptForm && !scriptForm.checkValidity()) {
        // Trigger browser validation
        scriptForm.reportValidity();
        return;
      }
      
      // Get form values
      const websiteStack = websiteStackSelect ? websiteStackSelect.value : 'html';
      const websiteUrl = document.getElementById('websiteUrl') ? document.getElementById('websiteUrl').value : '';
      const chatbotId = chatbotSelect ? chatbotSelect.value : '';
      const buttonPosition = document.getElementById('buttonPosition') ? document.getElementById('buttonPosition').value : 'bottom-right';
      const buttonText = document.getElementById('buttonText') ? document.getElementById('buttonText').value : 'Chat with us';
      const buttonIcon = document.getElementById('buttonIcon') ? document.getElementById('buttonIcon').value : '💬';
      const widgetTitle = document.getElementById('widgetTitle') ? document.getElementById('widgetTitle').value : 'Chat Support';
      const primaryColor = document.getElementById('primaryColor') ? document.getElementById('primaryColor').value : '#4361ee';
      
      console.log('Script Generator: Form values:', {
        websiteStack, websiteUrl, chatbotId, buttonPosition, 
        buttonText, buttonIcon, widgetTitle, primaryColor
      });
      
      // Generate the appropriate code based on the website stack
      if (websiteStack === 'html') {
        // Generate HTML/CSS embed code
        const htmlCode = generateHtmlCode(chatbotId, buttonPosition, buttonText, buttonIcon, widgetTitle, primaryColor);
        if (generatedScript) generatedScript.textContent = htmlCode;
        if (wordpressInstructions) wordpressInstructions.style.display = 'none';
      } else if (websiteStack === 'wordpress') {
        // Generate WordPress instructions
        if (generatedScript) generatedScript.textContent = generateWordPressInstructions(chatbotId);
        if (wordpressInstructions) wordpressInstructions.style.display = 'block';
      }
      
      // Show the generated code container and hide the generate button
      if (generatedScriptContainer) generatedScriptContainer.style.display = 'block';
      if (generateCodeBtn) generateCodeBtn.style.display = 'none';
      if (startOverBtn) startOverBtn.style.display = 'block';
    });
  }
  
  // Start over button handler
  if (startOverBtn) {
    startOverBtn.addEventListener('click', function() {
      console.log('Script Generator: Start over button clicked');
      
      // Hide the generated script container and show the form
      if (generatedScriptContainer) generatedScriptContainer.style.display = 'none';
      if (generateCodeBtn) generateCodeBtn.style.display = 'block';
      if (startOverBtn) startOverBtn.style.display = 'none';
      
      // Reset the form
      if (scriptForm) scriptForm.reset();
      
      // Reset default values
      if (document.getElementById('buttonText')) document.getElementById('buttonText').value = 'Chat with us';
      if (document.getElementById('buttonIcon')) document.getElementById('buttonIcon').value = '💬';
      if (document.getElementById('widgetTitle')) document.getElementById('widgetTitle').value = 'Chat Support';
      if (document.getElementById('primaryColor')) document.getElementById('primaryColor').value = '#4361ee';
    });
  }
  
  // Copy button handler
  if (copyScriptBtn) {
    copyScriptBtn.addEventListener('click', function() {
      console.log('Script Generator: Copy button clicked');
      
      // Copy the generated script to clipboard
      const scriptText = generatedScript ? generatedScript.textContent : '';
      
      // Try modern clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(scriptText)
          .then(() => {
            // Show success feedback
            const originalText = copyScriptBtn.innerHTML;
            copyScriptBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
            setTimeout(() => {
              copyScriptBtn.innerHTML = originalText;
            }, 2000);
          })
          .catch(err => {
            console.error('Script Generator: Clipboard API error', err);
            fallbackCopyToClipboard(scriptText);
          });
      } else {
        // Use fallback for older browsers
        fallbackCopyToClipboard(scriptText);
      }
    });
  }
  
  // Fallback clipboard copy function
  function fallbackCopyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    
    try {
      const success = document.execCommand('copy');
      if (success) {
        // Show success feedback
        const originalText = copyScriptBtn.innerHTML;
        copyScriptBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => {
          copyScriptBtn.innerHTML = originalText;
        }, 2000);
      } else {
        alert('Failed to copy. Please select and copy manually.');
      }
    } catch (err) {
      console.error('Script Generator: execCommand copy error', err);
      alert('Failed to copy. Please select and copy manually.');
    } finally {
      document.body.removeChild(textarea);
    }
  }
  
  // Populate the chatbot select dropdown
  function populateChatbotSelect() {
    if (!chatbotSelect) return;
    
    console.log('Script Generator: Populating chatbot dropdown');
    
    // Clear existing options
    while (chatbotSelect.options.length > 1) {
      chatbotSelect.remove(1);
    }
    
    // Set loading message
    chatbotSelect.options[0].text = 'Loading chatbots...';
    
    // Fetch chatbots from the server
    fetch('/api/chatbot/info', {
      method: 'GET',
      credentials: 'include'
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to fetch chatbots: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      console.log('Script Generator: Chatbots loaded', data);
      
      // Clear the loading message
      chatbotSelect.options[0].text = 'Choose...';
      
      // Add options for each chatbot
      if (data.chatbots && data.chatbots.length > 0) {
        data.chatbots.forEach(chatbot => {
          const option = document.createElement('option');
          option.value = chatbot.chatbot_id || chatbot.id;
          option.text = chatbot.bot_name || `Chatbot ${chatbot.id || chatbot.chatbot_id}`;
          chatbotSelect.appendChild(option);
        });
      } else {
        chatbotSelect.options[0].text = 'No chatbots available';
      }
    })
    .catch(error => {
      console.error('Script Generator: Error fetching chatbots', error);
      chatbotSelect.options[0].text = 'Error loading chatbots';
    });
  }
  
  // Generate HTML/CSS embed code
  function generateHtmlCode(chatbotId, position, buttonText, buttonIcon, widgetTitle, primaryColor) {
    return `<!-- Chatbot Embed Code -->
<script src="https://127.0.0.1:5006/static/chatbot-embed.js"><\/script>
<script>
  document.addEventListener('DOMContentLoaded', function() {
    initChatbotWidget({
      chatbotId: '${chatbotId}',
      serverUrl: 'https://127.0.0.1:5006',
      position: '${position}',
      buttonIcon: '${buttonIcon}',
      buttonText: '${buttonText}',
      widgetTitle: '${widgetTitle}',
      primaryColor: '${primaryColor}',
      textColor: '#343a40',
      widgetWidth: '350px',
      widgetHeight: '500px',
      autoOpen: false
    });
  });
<\/script>`;
  }
  
  // Generate WordPress instructions
  function generateWordPressInstructions(chatbotId) {
    return `WordPress Plugin Configuration:

Chatbot ID: ${chatbotId}
Server URL: https://127.0.0.1:5006

Follow the instructions below to install the plugin.`;
  }
}); 