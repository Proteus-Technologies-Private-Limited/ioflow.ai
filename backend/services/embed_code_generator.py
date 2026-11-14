"""
Embed Code Generator Service

Generates HTML, JavaScript, and CSS code for embedding frontend flow applications
in external websites and applications.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin

from core.config import settings

logger = logging.getLogger(__name__)


class EmbedCodeGenerator:
    """Service for generating embeddable code for frontend flow applications"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'base_url', 'http://localhost:7001')
    
    def generate_embed_code(self,
                          frontend_app: Dict[str, Any],
                          embed_type: str = "widget",
                          theme: str = "light",
                          width: str = "100%",
                          height: str = "auto",
                          custom_css: str = None,
                          callback_config: Dict[str, str] = None) -> Dict[str, str]:
        """
        Generate embeddable code for a frontend application
        
        Args:
            frontend_app: Frontend application data
            embed_type: Type of embed ('widget', 'iframe', 'modal')
            theme: UI theme ('light', 'dark', 'custom')
            width: Width of the embed
            height: Height of the embed
            custom_css: Custom CSS styles
            callback_config: Success/error callback URLs
            
        Returns:
            Dictionary with generated code
        """
        logger.info(f"Generating embed code for {frontend_app['frontend_app_name']}")
        
        public_url_slug = frontend_app["public_url_slug"]
        
        if embed_type == "iframe":
            return self._generate_iframe_embed(public_url_slug, width, height, theme)
        elif embed_type == "widget":
            return self._generate_widget_embed(
                frontend_app, theme, width, height, custom_css, callback_config
            )
        elif embed_type == "modal":
            return self._generate_modal_embed(
                frontend_app, theme, custom_css, callback_config
            )
        else:
            raise ValueError(f"Unsupported embed type: {embed_type}")
    
    def _generate_iframe_embed(self,
                              public_url_slug: str,
                              width: str,
                              height: str,
                              theme: str) -> Dict[str, str]:
        """Generate iframe embed code"""
        iframe_url = f"{self.base_url}/public-app/{public_url_slug}?embed=true&theme={theme}"
        
        html = f'''<iframe 
    src="{iframe_url}"
    width="{width}" 
    height="{height}"
    frameborder="0"
    style="border: none; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);"
    title="IOFlow Application">
</iframe>'''
        
        return {
            "type": "iframe",
            "html": html,
            "css": "",
            "javascript": ""
        }
    
    def _generate_widget_embed(self,
                              frontend_app: Dict[str, Any],
                              theme: str,
                              width: str,
                              height: str,
                              custom_css: str = None,
                              callback_config: Dict[str, str] = None) -> Dict[str, str]:
        """Generate widget embed code with full form"""
        public_url_slug = frontend_app["public_url_slug"]
        app_name = frontend_app["frontend_app_name"]
        description = frontend_app.get("description", "")
        
        # Get the flow's manual variables from the published application
        manual_variables = self._get_manual_variables(frontend_app)
        
        # Generate unique container ID
        container_id = f"ioflow-app-{public_url_slug.replace('-', '_')}"
        
        # Generate HTML structure
        html = self._generate_widget_html(
            container_id, app_name, description, manual_variables, theme
        )
        
        # Generate CSS
        css = self._generate_widget_css(theme, width, height, custom_css)
        
        # Generate JavaScript
        javascript = self._generate_widget_javascript(
            container_id, public_url_slug, callback_config, manual_variables
        )
        
        return {
            "type": "widget",
            "html": html,
            "css": css,
            "javascript": javascript
        }
    
    def _generate_modal_embed(self,
                             frontend_app: Dict[str, Any],
                             theme: str,
                             custom_css: str = None,
                             callback_config: Dict[str, str] = None) -> Dict[str, str]:
        """Generate modal embed code"""
        public_url_slug = frontend_app["public_url_slug"]
        app_name = frontend_app["frontend_app_name"]
        
        # Generate unique IDs
        button_id = f"ioflow-btn-{public_url_slug.replace('-', '_')}"
        modal_id = f"ioflow-modal-{public_url_slug.replace('-', '_')}"
        
        html = f'''<!-- IOFlow Application Button -->
<button id="{button_id}" class="ioflow-trigger-btn">
    Launch {app_name}
</button>

<!-- IOFlow Modal (hidden by default) -->
<div id="{modal_id}" class="ioflow-modal" style="display: none;">
    <div class="ioflow-modal-content">
        <div class="ioflow-modal-header">
            <h3>{app_name}</h3>
            <button class="ioflow-close-btn" onclick="IOFlowApp.closeModal('{modal_id}')">&times;</button>
        </div>
        <div class="ioflow-modal-body">
            <iframe 
                src="{self.base_url}/public-app/{public_url_slug}?embed=true&theme={theme}"
                width="100%" 
                height="500px"
                frameborder="0">
            </iframe>
        </div>
    </div>
</div>'''
        
        css = self._generate_modal_css(theme, custom_css)
        
        javascript = f'''// IOFlow Modal Application
window.IOFlowApp = window.IOFlowApp || {{}};

IOFlowApp.openModal = function(modalId) {{
    document.getElementById(modalId).style.display = 'flex';
    document.body.style.overflow = 'hidden';
}};

IOFlowApp.closeModal = function(modalId) {{
    document.getElementById(modalId).style.display = 'none';
    document.body.style.overflow = 'auto';
}};

// Initialize modal trigger
document.addEventListener('DOMContentLoaded', function() {{
    document.getElementById('{button_id}').addEventListener('click', function() {{
        IOFlowApp.openModal('{modal_id}');
    }});
    
    // Close modal when clicking outside
    document.getElementById('{modal_id}').addEventListener('click', function(e) {{
        if (e.target === this) {{
            IOFlowApp.closeModal('{modal_id}');
        }}
    }});
}});'''
        
        return {
            "type": "modal",
            "html": html,
            "css": css,
            "javascript": javascript
        }
    
    def _generate_widget_html(self,
                             container_id: str,
                             app_name: str,
                             description: str,
                             manual_variables: List[Dict[str, Any]],
                             theme: str) -> str:
        """Generate HTML structure for widget embed"""
        
        form_fields = []
        for variable in manual_variables:
            field_html = self._generate_form_field(variable)
            form_fields.append(field_html)
        
        html = f'''<!-- IOFlow Application Widget -->
<div id="{container_id}" class="ioflow-widget ioflow-theme-{theme}">
    <div class="ioflow-header">
        <h3 class="ioflow-title">{app_name}</h3>
        {f'<p class="ioflow-description">{description}</p>' if description else ''}
    </div>
    
    <form class="ioflow-form" onsubmit="return false;">
        {chr(10).join(form_fields)}
        
        <div class="ioflow-actions">
            <button type="button" class="ioflow-submit-btn" onclick="IOFlowApp.executeApp('{container_id}')">
                <span class="ioflow-btn-text">Execute</span>
                <span class="ioflow-loading" style="display: none;">Processing...</span>
            </button>
        </div>
        
        <div class="ioflow-result" style="display: none;">
            <div class="ioflow-result-content"></div>
        </div>
        
        <div class="ioflow-error" style="display: none;">
            <div class="ioflow-error-content"></div>
        </div>
    </form>
</div>'''
        
        return html
    
    def _generate_form_field(self, variable: Dict[str, Any]) -> str:
        """Generate HTML for a form field based on variable configuration"""
        name = variable["name"]
        label = variable.get("displayName", name)
        data_type = variable.get("dataType", "string")
        required = variable.get("required", False)
        description = variable.get("description", "")
        default_value = variable.get("defaultValue", "")
        
        required_attr = 'required' if required else ''
        placeholder = variable.get("placeholder", f"Enter {label.lower()}")
        
        field_html = f'''<div class="ioflow-field">
            <label class="ioflow-label" for="{name}">
                {label}
                {' <span class="ioflow-required">*</span>' if required else ''}
            </label>
            {f'<p class="ioflow-field-help">{description}</p>' if description else ''}
            '''
        
        if data_type == "textarea" or data_type == "text_long":
            field_html += f'''
            <textarea 
                id="{name}" 
                name="{name}" 
                class="ioflow-input ioflow-textarea"
                placeholder="{placeholder}"
                {required_attr}>{default_value}</textarea>
            '''
        elif data_type == "boolean":
            checked = 'checked' if default_value else ''
            field_html += f'''
            <label class="ioflow-checkbox">
                <input 
                    type="checkbox" 
                    id="{name}" 
                    name="{name}" 
                    value="true"
                    {checked}
                    class="ioflow-input">
                <span class="ioflow-checkmark"></span>
            </label>
            '''
        elif data_type == "number":
            field_html += f'''
            <input 
                type="number" 
                id="{name}" 
                name="{name}" 
                class="ioflow-input"
                placeholder="{placeholder}"
                value="{default_value}"
                {required_attr}>
            '''
        elif data_type == "date":
            field_html += f'''
            <input 
                type="date" 
                id="{name}" 
                name="{name}" 
                class="ioflow-input"
                value="{default_value}"
                {required_attr}>
            '''
        elif data_type == "file":
            field_html += f'''
            <input 
                type="file" 
                id="{name}" 
                name="{name}" 
                class="ioflow-input ioflow-file-input"
                {required_attr}>
            '''
        else:  # string, email, etc.
            input_type = "email" if data_type == "email" else "text"
            field_html += f'''
            <input 
                type="{input_type}" 
                id="{name}" 
                name="{name}" 
                class="ioflow-input"
                placeholder="{placeholder}"
                value="{default_value}"
                {required_attr}>
            '''
        
        field_html += '</div>'
        return field_html
    
    def _generate_widget_css(self,
                            theme: str,
                            width: str,
                            height: str,
                            custom_css: str = None) -> str:
        """Generate CSS for widget embed"""
        
        # Base theme variables
        if theme == "dark":
            theme_vars = '''
                --ioflow-bg: #1f2937;
                --ioflow-border: #374151;
                --ioflow-text: #f9fafb;
                --ioflow-text-muted: #9ca3af;
                --ioflow-primary: #3b82f6;
                --ioflow-primary-hover: #2563eb;
                --ioflow-success: #10b981;
                --ioflow-error: #ef4444;
                --ioflow-input-bg: #374151;
                --ioflow-input-border: #4b5563;
            '''
        else:  # light theme
            theme_vars = '''
                --ioflow-bg: #ffffff;
                --ioflow-border: #e5e7eb;
                --ioflow-text: #111827;
                --ioflow-text-muted: #6b7280;
                --ioflow-primary: #3b82f6;
                --ioflow-primary-hover: #2563eb;
                --ioflow-success: #10b981;
                --ioflow-error: #ef4444;
                --ioflow-input-bg: #ffffff;
                --ioflow-input-border: #d1d5db;
            '''
        
        css = f'''/* IOFlow Widget Styles */
.ioflow-widget {{
    {theme_vars}
    width: {width};
    max-width: 600px;
    background: var(--ioflow-bg);
    border: 1px solid var(--ioflow-border);
    border-radius: 12px;
    padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--ioflow-text);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    margin: 16px auto;
}}

.ioflow-header {{
    margin-bottom: 24px;
    text-align: center;
}}

.ioflow-title {{
    margin: 0 0 8px 0;
    font-size: 20px;
    font-weight: 600;
    color: var(--ioflow-text);
}}

.ioflow-description {{
    margin: 0;
    font-size: 14px;
    color: var(--ioflow-text-muted);
    line-height: 1.5;
}}

.ioflow-field {{
    margin-bottom: 20px;
}}

.ioflow-label {{
    display: block;
    margin-bottom: 6px;
    font-size: 14px;
    font-weight: 500;
    color: var(--ioflow-text);
}}

.ioflow-required {{
    color: var(--ioflow-error);
}}

.ioflow-field-help {{
    margin: 4px 0 8px 0;
    font-size: 12px;
    color: var(--ioflow-text-muted);
    line-height: 1.4;
}}

.ioflow-input {{
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--ioflow-input-border);
    border-radius: 6px;
    background: var(--ioflow-input-bg);
    color: var(--ioflow-text);
    font-size: 14px;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-sizing: border-box;
}}

.ioflow-input:focus {{
    outline: none;
    border-color: var(--ioflow-primary);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}}

.ioflow-textarea {{
    min-height: 80px;
    resize: vertical;
}}

.ioflow-checkbox {{
    display: flex;
    align-items: center;
    cursor: pointer;
}}

.ioflow-checkbox input {{
    width: auto;
    margin-right: 8px;
}}

.ioflow-actions {{
    margin-top: 24px;
    text-align: center;
}}

.ioflow-submit-btn {{
    background: var(--ioflow-primary);
    color: white;
    border: none;
    padding: 12px 32px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.2s, transform 0.1s;
    position: relative;
}}

.ioflow-submit-btn:hover {{
    background: var(--ioflow-primary-hover);
}}

.ioflow-submit-btn:active {{
    transform: translateY(1px);
}}

.ioflow-submit-btn:disabled {{
    background: var(--ioflow-text-muted);
    cursor: not-allowed;
    transform: none;
}}

.ioflow-loading {{
    display: inline-block;
}}

.ioflow-result, .ioflow-error {{
    margin-top: 20px;
    padding: 16px;
    border-radius: 8px;
    font-size: 14px;
}}

.ioflow-result {{
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid var(--ioflow-success);
    color: var(--ioflow-success);
}}

.ioflow-error {{
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--ioflow-error);
    color: var(--ioflow-error);
}}

.ioflow-result-content, .ioflow-error-content {{
    word-break: break-word;
}}

/* File input styling */
.ioflow-file-input {{
    padding: 8px;
    cursor: pointer;
}}

.ioflow-file-input::-webkit-file-upload-button {{
    background: var(--ioflow-primary);
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    margin-right: 8px;
}}

/* Responsive design */
@media (max-width: 640px) {{
    .ioflow-widget {{
        margin: 8px;
        padding: 16px;
    }}
    
    .ioflow-title {{
        font-size: 18px;
    }}
    
    .ioflow-submit-btn {{
        width: 100%;
        padding: 14px;
    }}
}}

{custom_css if custom_css else ''}'''
        
        return css
    
    def _generate_widget_javascript(self,
                                   container_id: str,
                                   public_url_slug: str,
                                   callback_config: Dict[str, str] = None,
                                   manual_variables: List[Dict[str, Any]] = None) -> str:
        """Generate JavaScript for widget embed"""
        
        api_url = f"{self.base_url}/api/v1/public-apps/{public_url_slug}/execute"
        
        js = f'''// IOFlow Widget Application
window.IOFlowApp = window.IOFlowApp || {{}};

IOFlowApp.executeApp = function(containerId) {{
    const container = document.getElementById(containerId);
    const form = container.querySelector('.ioflow-form');
    const submitBtn = container.querySelector('.ioflow-submit-btn');
    const btnText = submitBtn.querySelector('.ioflow-btn-text');
    const loading = submitBtn.querySelector('.ioflow-loading');
    const resultDiv = container.querySelector('.ioflow-result');
    const errorDiv = container.querySelector('.ioflow-error');
    
    // Collect form data
    const formData = new FormData(form);
    const data = {{}};
    
    for (let [key, value] of formData.entries()) {{
        // Handle file inputs
        if (value instanceof File) {{
            // For now, we'll skip file uploads in the widget
            // This could be enhanced to support file uploads via base64 encoding
            continue;
        }}
        
        // Handle checkboxes
        const input = form.querySelector(`[name="${{key}}"]`);
        if (input && input.type === 'checkbox') {{
            data[key] = input.checked;
        }} else {{
            data[key] = value;
        }}
    }}
    
    // Add unchecked checkboxes as false
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => {{
        if (!cb.checked) {{
            data[cb.name] = false;
        }}
    }});
    
    // Show loading state
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    loading.style.display = 'inline-block';
    resultDiv.style.display = 'none';
    errorDiv.style.display = 'none';
    
    // Execute the flow
    fetch('{api_url}', {{
        method: 'POST',
        headers: {{
            'Content-Type': 'application/json',
        }},
        body: JSON.stringify(data)
    }})
    .then(response => response.json())
    .then(result => {{
        submitBtn.disabled = false;
        btnText.style.display = 'inline-block';
        loading.style.display = 'none';
        
        if (result.success) {{
            resultDiv.querySelector('.ioflow-result-content').innerHTML = 
                IOFlowApp.formatResult(result.data);
            resultDiv.style.display = 'block';
            
            // Success callback
            {f"if (window.{callback_config.get('onSuccess', 'function(){{}}')}) window.{callback_config.get('onSuccess')}(result);" if callback_config and callback_config.get('onSuccess') else ''}
        }} else {{
            errorDiv.querySelector('.ioflow-error-content').textContent = 
                result.error || 'Execution failed';
            errorDiv.style.display = 'block';
            
            // Error callback
            {f"if (window.{callback_config.get('onError', 'function(){{}}')}) window.{callback_config.get('onError')}(result);" if callback_config and callback_config.get('onError') else ''}
        }}
    }})
    .catch(error => {{
        submitBtn.disabled = false;
        btnText.style.display = 'inline-block';
        loading.style.display = 'none';
        
        errorDiv.querySelector('.ioflow-error-content').textContent = 
            'Network error: ' + error.message;
        errorDiv.style.display = 'block';
        
        // Error callback
        {f"if (window.{callback_config.get('onError', 'function(){{}}')}) window.{callback_config.get('onError')}({{error: error.message}});" if callback_config and callback_config.get('onError') else ''}
    }});
}};

IOFlowApp.formatResult = function(data) {{
    if (typeof data === 'string') {{
        return data;
    }}
    
    if (typeof data === 'object') {{
        return '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
    }}
    
    return String(data);
}};

// Auto-initialize if DOM is ready
if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', function() {{
        console.log('IOFlow widget initialized for {public_url_slug}');
    }});
}} else {{
    console.log('IOFlow widget initialized for {public_url_slug}');
}}'''
        
        return js
    
    def _generate_modal_css(self, theme: str, custom_css: str = None) -> str:
        """Generate CSS for modal embed"""
        
        # Base theme variables
        if theme == "dark":
            theme_vars = '''
                --ioflow-modal-bg: rgba(0, 0, 0, 0.8);
                --ioflow-modal-content-bg: #1f2937;
                --ioflow-modal-border: #374151;
                --ioflow-modal-text: #f9fafb;
                --ioflow-btn-bg: #3b82f6;
                --ioflow-btn-hover: #2563eb;
            '''
        else:
            theme_vars = '''
                --ioflow-modal-bg: rgba(0, 0, 0, 0.5);
                --ioflow-modal-content-bg: #ffffff;
                --ioflow-modal-border: #e5e7eb;
                --ioflow-modal-text: #111827;
                --ioflow-btn-bg: #3b82f6;
                --ioflow-btn-hover: #2563eb;
            '''
        
        css = f'''/* IOFlow Modal Styles */
.ioflow-modal {{
    {theme_vars}
    display: none;
    position: fixed;
    z-index: 10000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: var(--ioflow-modal-bg);
    align-items: center;
    justify-content: center;
}}

.ioflow-modal-content {{
    background: var(--ioflow-modal-content-bg);
    border: 1px solid var(--ioflow-modal-border);
    border-radius: 12px;
    width: 90%;
    max-width: 800px;
    max-height: 90vh;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}}

.ioflow-modal-header {{
    padding: 20px 24px;
    border-bottom: 1px solid var(--ioflow-modal-border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--ioflow-modal-content-bg);
}}

.ioflow-modal-header h3 {{
    margin: 0;
    color: var(--ioflow-modal-text);
    font-size: 18px;
    font-weight: 600;
}}

.ioflow-close-btn {{
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: var(--ioflow-modal-text);
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: background-color 0.2s;
}}

.ioflow-close-btn:hover {{
    background: var(--ioflow-modal-border);
}}

.ioflow-modal-body {{
    padding: 0;
}}

.ioflow-modal-body iframe {{
    width: 100%;
    height: 500px;
    border: none;
}}

.ioflow-trigger-btn {{
    background: var(--ioflow-btn-bg);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.2s, transform 0.1s;
}}

.ioflow-trigger-btn:hover {{
    background: var(--ioflow-btn-hover);
}}

.ioflow-trigger-btn:active {{
    transform: translateY(1px);
}}

/* Responsive design */
@media (max-width: 640px) {{
    .ioflow-modal-content {{
        width: 95%;
        margin: 20px;
    }}
    
    .ioflow-modal-header {{
        padding: 16px 20px;
    }}
    
    .ioflow-modal-body iframe {{
        height: 400px;
    }}
}}

{custom_css if custom_css else ''}'''
        
        return css
    
    def _get_manual_variables(self, frontend_app: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get manual variables configuration from the published application
        This would typically come from the flow's trigger configuration
        """
        # This is a placeholder - in a real implementation, you would
        # fetch the actual manual variables from the published application's flow
        return [
            {
                "name": "input_text",
                "displayName": "Input Text",
                "dataType": "string",
                "required": True,
                "description": "Enter your input text",
                "placeholder": "Type your message here..."
            },
            {
                "name": "email",
                "displayName": "Email Address",
                "dataType": "email",
                "required": False,
                "description": "Optional email for notifications"
            }
        ]
    
    def generate_sdk_code(self, public_url_slug: str) -> str:
        """Generate JavaScript SDK code for programmatic integration"""
        return f'''// IOFlow SDK for {public_url_slug}
class IOFlowSDK {{
    constructor(apiKey = null) {{
        this.baseUrl = '{self.base_url}';
        this.apiKey = apiKey;
    }}
    
    async execute(parameters) {{
        const response = await fetch(`${{this.baseUrl}}/api/v1/public-apps/{public_url_slug}/execute`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                ...(this.apiKey ? {{ 'Authorization': `Bearer ${{this.apiKey}}` }} : {{}})
            }},
            body: JSON.stringify(parameters)
        }});
        
        return await response.json();
    }}
    
    async getInfo() {{
        const response = await fetch(`${{this.baseUrl}}/api/v1/public-apps/{public_url_slug}/info`);
        return await response.json();
    }}
}}

// Usage example:
// const sdk = new IOFlowSDK();
// sdk.execute({{ input_text: "Hello World" }}).then(result => console.log(result));
'''