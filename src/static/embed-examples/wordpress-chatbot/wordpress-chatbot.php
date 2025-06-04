<?php
/**
 * Plugin Name: Chatbot Widget
 * Plugin URI: https://127.0.0.1:5006
 * Description: Adds a customizable chatbot widget to your WordPress website.
 * Version: 1.0.0
 * Author: Your Company Name
 * License: GPL-2.0+
 * License URI: http://www.gnu.org/licenses/gpl-2.0.txt
 */

// If this file is called directly, abort.
if (!defined('WPINC')) {
    die;
}

// Define plugin constants
define('CHATBOT_WIDGET_VERSION', '1.0.0');
define('CHATBOT_WIDGET_PATH', plugin_dir_path(__FILE__));
define('CHATBOT_WIDGET_URL', plugin_dir_url(__FILE__));

/**
 * The code that runs during plugin activation.
 */
function activate_chatbot_widget() {
    // Initialize default settings if not already set
    if (!get_option('chatbot_widget_settings')) {
        $default_settings = array(
            'chatbot_id' => '',
            'server_url' => 'https://127.0.0.1:5006',
            'position' => 'bottom-right',
            'button_icon' => '💬',
            'button_text' => 'Chat with us',
            'widget_title' => 'Chatbot',
            'primary_color' => '#4361ee',
            'text_color' => '#343a40',
            'widget_width' => '350px',
            'widget_height' => '500px',
            'auto_open' => false,
            'enable_chatbot' => true
        );
        add_option('chatbot_widget_settings', $default_settings);
    }
}
register_activation_hook(__FILE__, 'activate_chatbot_widget');

/**
 * The code that runs during plugin deactivation.
 */
function deactivate_chatbot_widget() {
    // Nothing special to do on deactivation
}
register_deactivation_hook(__FILE__, 'deactivate_chatbot_widget');

/**
 * Enqueue scripts for the frontend
 */
function chatbot_widget_enqueue_scripts() {
    $settings = get_option('chatbot_widget_settings');
    
    // Only load if chatbot is enabled
    if (isset($settings['enable_chatbot']) && $settings['enable_chatbot']) {
        // Enqueue the chatbot embed script
        wp_enqueue_script(
            'chatbot-embed',
            $settings['server_url'] . '/static/chatbot-embed.js',
            array(),
            CHATBOT_WIDGET_VERSION,
            true
        );
        
        // Inline script to initialize the chatbot with the settings
        $init_script = "
            document.addEventListener('DOMContentLoaded', function() {
                initChatbotWidget({
                    chatbotId: '" . esc_js($settings['chatbot_id']) . "',
                    serverUrl: '" . esc_js($settings['server_url']) . "',
                    position: '" . esc_js($settings['position']) . "',
                    buttonIcon: '" . esc_js($settings['button_icon']) . "',
                    buttonText: '" . esc_js($settings['button_text']) . "',
                    widgetTitle: '" . esc_js($settings['widget_title']) . "',
                    primaryColor: '" . esc_js($settings['primary_color']) . "',
                    textColor: '" . esc_js($settings['text_color']) . "',
                    widgetWidth: '" . esc_js($settings['widget_width']) . "',
                    widgetHeight: '" . esc_js($settings['widget_height']) . "',
                    autoOpen: " . ($settings['auto_open'] ? 'true' : 'false') . "
                });
            });
        ";
        
        wp_add_inline_script('chatbot-embed', $init_script);
    }
}
add_action('wp_enqueue_scripts', 'chatbot_widget_enqueue_scripts');

/**
 * Add settings page to the WordPress admin menu
 */
function chatbot_widget_add_settings_page() {
    add_options_page(
        'Chatbot Widget Settings',
        'Chatbot Widget',
        'manage_options',
        'chatbot-widget-settings',
        'chatbot_widget_settings_page'
    );
}
add_action('admin_menu', 'chatbot_widget_add_settings_page');

/**
 * Register settings
 */
function chatbot_widget_register_settings() {
    register_setting('chatbot_widget_options', 'chatbot_widget_settings', 'chatbot_widget_validate_settings');
}
add_action('admin_init', 'chatbot_widget_register_settings');

/**
 * Validate settings
 */
function chatbot_widget_validate_settings($input) {
    $valid = array();
    
    $valid['enable_chatbot'] = isset($input['enable_chatbot']) ? true : false;
    $valid['chatbot_id'] = sanitize_text_field($input['chatbot_id']);
    $valid['server_url'] = esc_url_raw($input['server_url']);
    $valid['position'] = sanitize_text_field($input['position']);
    $valid['button_icon'] = sanitize_text_field($input['button_icon']);
    $valid['button_text'] = sanitize_text_field($input['button_text']);
    $valid['widget_title'] = sanitize_text_field($input['widget_title']);
    $valid['primary_color'] = sanitize_hex_color($input['primary_color']);
    $valid['text_color'] = sanitize_hex_color($input['text_color']);
    $valid['widget_width'] = sanitize_text_field($input['widget_width']);
    $valid['widget_height'] = sanitize_text_field($input['widget_height']);
    $valid['auto_open'] = isset($input['auto_open']) ? true : false;
    
    return $valid;
}

/**
 * Render the settings page
 */
function chatbot_widget_settings_page() {
    ?>
    <div class="wrap">
        <h1><?php echo esc_html(get_admin_page_title()); ?></h1>
        <form method="post" action="options.php">
            <?php
            settings_fields('chatbot_widget_options');
            $settings = get_option('chatbot_widget_settings');
            ?>
            
            <table class="form-table">
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[enable_chatbot]">Enable Chatbot</label>
                    </th>
                    <td>
                        <input type="checkbox" id="chatbot_widget_settings[enable_chatbot]" 
                               name="chatbot_widget_settings[enable_chatbot]" 
                               value="1" <?php checked(isset($settings['enable_chatbot']) ? $settings['enable_chatbot'] : false); ?>>
                        <p class="description">Check to enable the chatbot widget on your website.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[chatbot_id]">Chatbot ID</label>
                    </th>
                    <td>
                        <input type="text" id="chatbot_widget_settings[chatbot_id]" 
                               name="chatbot_widget_settings[chatbot_id]" 
                               value="<?php echo esc_attr($settings['chatbot_id']); ?>"
                               class="regular-text" required>
                        <p class="description">Enter your chatbot ID provided by the service.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[server_url]">Server URL</label>
                    </th>
                    <td>
                        <input type="url" id="chatbot_widget_settings[server_url]" 
                               name="chatbot_widget_settings[server_url]" 
                               value="<?php echo esc_url($settings['server_url']); ?>"
                               class="regular-text" required>
                        <p class="description">Enter the URL of the chatbot service (e.g., https://127.0.0.1:5006).</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[position]">Widget Position</label>
                    </th>
                    <td>
                        <select id="chatbot_widget_settings[position]" 
                                name="chatbot_widget_settings[position]">
                            <option value="bottom-right" <?php selected($settings['position'], 'bottom-right'); ?>>Bottom Right</option>
                            <option value="bottom-left" <?php selected($settings['position'], 'bottom-left'); ?>>Bottom Left</option>
                            <option value="top-right" <?php selected($settings['position'], 'top-right'); ?>>Top Right</option>
                            <option value="top-left" <?php selected($settings['position'], 'top-left'); ?>>Top Left</option>
                        </select>
                        <p class="description">Choose the position of the chatbot widget on your website.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[button_icon]">Button Icon</label>
                    </th>
                    <td>
                        <input type="text" id="chatbot_widget_settings[button_icon]" 
                               name="chatbot_widget_settings[button_icon]" 
                               value="<?php echo esc_attr($settings['button_icon']); ?>"
                               class="regular-text">
                        <p class="description">Enter an emoji or HTML for the chat button icon (e.g., 💬, 🤖).</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[button_text]">Button Text</label>
                    </th>
                    <td>
                        <input type="text" id="chatbot_widget_settings[button_text]" 
                               name="chatbot_widget_settings[button_text]" 
                               value="<?php echo esc_attr($settings['button_text']); ?>"
                               class="regular-text">
                        <p class="description">Enter the text to display on the chat button.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[widget_title]">Widget Title</label>
                    </th>
                    <td>
                        <input type="text" id="chatbot_widget_settings[widget_title]" 
                               name="chatbot_widget_settings[widget_title]" 
                               value="<?php echo esc_attr($settings['widget_title']); ?>"
                               class="regular-text">
                        <p class="description">Enter the title to display in the chatbot header.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[primary_color]">Primary Color</label>
                    </th>
                    <td>
                        <input type="color" id="chatbot_widget_settings[primary_color]" 
                               name="chatbot_widget_settings[primary_color]" 
                               value="<?php echo esc_attr($settings['primary_color']); ?>">
                        <p class="description">Choose the primary color for buttons and headers.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[text_color]">Text Color</label>
                    </th>
                    <td>
                        <input type="color" id="chatbot_widget_settings[text_color]" 
                               name="chatbot_widget_settings[text_color]" 
                               value="<?php echo esc_attr($settings['text_color']); ?>">
                        <p class="description">Choose the color for text content.</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[widget_width]">Widget Width</label>
                    </th>
                    <td>
                        <input type="text" id="chatbot_widget_settings[widget_width]" 
                               name="chatbot_widget_settings[widget_width]" 
                               value="<?php echo esc_attr($settings['widget_width']); ?>"
                               class="regular-text">
                        <p class="description">Enter the width of the chat widget (e.g., 350px, 400px).</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[widget_height]">Widget Height</label>
                    </th>
                    <td>
                        <input type="text" id="chatbot_widget_settings[widget_height]" 
                               name="chatbot_widget_settings[widget_height]" 
                               value="<?php echo esc_attr($settings['widget_height']); ?>"
                               class="regular-text">
                        <p class="description">Enter the height of the chat widget (e.g., 500px, 600px).</p>
                    </td>
                </tr>
                
                <tr>
                    <th scope="row">
                        <label for="chatbot_widget_settings[auto_open]">Auto Open</label>
                    </th>
                    <td>
                        <input type="checkbox" id="chatbot_widget_settings[auto_open]" 
                               name="chatbot_widget_settings[auto_open]" 
                               value="1" <?php checked(isset($settings['auto_open']) ? $settings['auto_open'] : false); ?>>
                        <p class="description">Check to automatically open the chat widget when the page loads.</p>
                    </td>
                </tr>
            </table>
            
            <?php submit_button('Save Settings'); ?>
        </form>
    </div>
    <?php
}

/**
 * Add a link to the settings page from the plugins page
 */
function chatbot_widget_add_settings_link($links) {
    $settings_link = '<a href="options-general.php?page=chatbot-widget-settings">' . __('Settings') . '</a>';
    array_unshift($links, $settings_link);
    return $links;
}
$plugin_basename = plugin_basename(__FILE__);
add_filter("plugin_action_links_$plugin_basename", 'chatbot_widget_add_settings_link'); 