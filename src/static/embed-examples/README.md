# Chatbot Embedding Guide

This guide explains how to embed your chatbot on different websites and platforms.

## Table of Contents

1. [HTML/CSS Websites](#htmlcss-websites)
2. [WordPress Websites](#wordpress-websites)
3. [Customization Options](#customization-options)
4. [Troubleshooting](#troubleshooting)

## HTML/CSS Websites

### Step 1: Include the Script

Add the following script tag to your website, just before the closing `</body>` tag:

```html
<script src="https://your-server-address.com/static/chatbot-embed.js"></script>
```

Replace `your-server-address.com` with the actual address of your chatbot server.

### Step 2: Initialize the Chatbot

Add the following script to initialize the chatbot with your configuration:

```html
<script>
  document.addEventListener('DOMContentLoaded', function() {
    initChatbotWidget({
      chatbotId: 'YOUR_CHATBOT_ID',
      serverUrl: 'https://your-server-address.com',
      position: 'bottom-right',
      buttonIcon: '💬',
      buttonText: 'Chat with us',
      widgetTitle: 'Your Chatbot',
      primaryColor: '#4361ee',
      textColor: '#343a40',
      widgetWidth: '350px',
      widgetHeight: '500px',
      autoOpen: false
    });
  });
</script>
```

Replace `YOUR_CHATBOT_ID` with the actual ID of your chatbot and `your-server-address.com` with your server address.

### Full Example

See the [html-example.html](./html-example.html) file for a complete example.

## WordPress Websites

### Step 1: Install the WordPress Plugin

1. Download the [WordPress Plugin](./wordpress-chatbot) folder
2. Create a zip file of the `wordpress-chatbot` folder
3. Log in to your WordPress admin panel
4. Go to Plugins > Add New > Upload Plugin
5. Select the zip file you created and click "Install Now"
6. After installation, click "Activate Plugin"

### Step 2: Configure the Chatbot

1. In your WordPress admin panel, go to Settings > Chatbot Widget
2. Enter your Chatbot ID and Server URL provided by the chatbot service
3. Customize the appearance and behavior of the chatbot as needed
4. Click "Save Settings"

The chatbot will now appear on your WordPress website according to your settings.

## Customization Options

You can customize the appearance and behavior of the chatbot by modifying the configuration options:

| Option | Description | Default Value |
|--------|-------------|---------------|
| `chatbotId` | The ID of your chatbot on the server | (required) |
| `serverUrl` | The URL of your server where the chatbot API is hosted | (required) |
| `position` | Where to place the chatbot button | 'bottom-right' |
| `buttonIcon` | Icon to display on the chat button (emoji or HTML) | '💬' |
| `buttonText` | Text displayed on the chat button | 'Chat with us' |
| `widgetTitle` | The title shown at the top of the chat widget | 'Chatbot' |
| `primaryColor` | The main color for the widget (buttons, header, etc.) | '#4361ee' |
| `textColor` | The color for text content | '#343a40' |
| `widgetWidth` | The width of the chat widget | '350px' |
| `widgetHeight` | The height of the chat widget | '500px' |
| `autoOpen` | Whether to automatically open the chat widget when the page loads | false |

## Troubleshooting

### Common Issues

1. **Chatbot not appearing**:
   - Check if the script is loaded correctly
   - Verify that the server URL is correct
   - Make sure the chatbot ID is valid

2. **Connection errors**:
   - Ensure your server is running and accessible
   - Check for CORS settings on your server
   - Verify SSL certificates if using HTTPS

3. **Styling conflicts**:
   - The chatbot uses inline styles to avoid conflicts
   - If you experience styling issues, try adjusting the z-index in the configuration

### Getting Help

If you encounter any issues while embedding the chatbot, please contact our support team at support@your-company.com or open a support ticket in your account dashboard. 