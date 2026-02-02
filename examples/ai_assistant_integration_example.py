"""
Example: Integrating OpenAI GPT-4 with SCADA Scout AI Assistant

This example shows how to configure the AI Assistant to use OpenAI's API.

Prerequisites:
    pip install openai

Usage:
    1. Set your OpenAI API key as environment variable:
       export OPENAI_API_KEY="sk-..."
    
    2. Update src/ui/main_window.py with the code below
"""

# ============================================================================
# INTEGRATION CODE FOR src/ui/main_window.py
# ============================================================================

def _show_ai_assistant(self):
    """Opens the AI Assistant dialog for protocol analysis."""
    try:
        # Get watch list manager if available
        watch_list_mgr = getattr(self, 'watch_list_manager', None)
        
        # Get protocol gateway if available
        protocol_gateway = getattr(self.device_manager, 'protocol_gateway', None)
        
        dialog = AIAssistantDialog(
            device_manager=self.device_manager,
            watch_list_manager=watch_list_mgr,
            protocol_gateway=protocol_gateway,
            event_logger=self.event_logger,
            parent=self
        )
        
        # ============== OPENAI CONFIGURATION ==============
        import os
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            QMessageBox.warning(
                self,
                "API Key Missing",
                "Please set OPENAI_API_KEY environment variable.\n\n"
                "Example:\nexport OPENAI_API_KEY='sk-...'"
            )
            return
        
        # Create OpenAI client
        client = OpenAI(api_key=api_key)
        
        # Create wrapper that matches expected interface
        class OpenAIWrapper:
            def __init__(self, openai_client):
                self.client = openai_client
            
            def chat(self, system: str, user: str, temperature: float = 0.2):
                """Call OpenAI Chat Completions API."""
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",  # or "gpt-4", "gpt-3.5-turbo"
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    temperature=temperature,
                    max_tokens=4096
                )
                return response.choices[0].message.content
        
        wrapped_client = OpenAIWrapper(client)
        dialog.set_api_client(wrapped_client)
        # ==================================================
        
        dialog.exec()
    except ImportError:
        QMessageBox.critical(
            self, 
            "Missing Dependency", 
            "OpenAI package not installed.\n\n"
            "Install with: pip install openai"
        )
    except Exception as e:
        QMessageBox.critical(
            self, 
            "Error", 
            f"Failed to open AI Assistant:\n{e}"
        )


# ============================================================================
# ALTERNATIVE: Using Anthropic Claude
# ============================================================================

"""
Prerequisites:
    pip install anthropic

Environment:
    export ANTHROPIC_API_KEY="sk-ant-..."
"""

def _show_ai_assistant_claude(self):
    """Opens AI Assistant with Anthropic Claude."""
    try:
        # ... same dialog setup as above ...
        
        # ============== ANTHROPIC CONFIGURATION ==============
        import os
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            QMessageBox.warning(
                self,
                "API Key Missing",
                "Please set ANTHROPIC_API_KEY environment variable."
            )
            return
        
        client = Anthropic(api_key=api_key)
        
        class AnthropicWrapper:
            def __init__(self, anthropic_client):
                self.client = anthropic_client
            
            def chat(self, system: str, user: str, temperature: float = 0.2):
                """Call Anthropic Messages API."""
                message = self.client.messages.create(
                    model="claude-3-opus-20240229",  # or "claude-3-sonnet-20240229"
                    max_tokens=4096,
                    temperature=temperature,
                    system=system,
                    messages=[
                        {"role": "user", "content": user}
                    ]
                )
                return message.content[0].text
        
        wrapped_client = AnthropicWrapper(client)
        dialog.set_api_client(wrapped_client)
        # =====================================================
        
        dialog.exec()
    except ImportError:
        QMessageBox.critical(
            self, 
            "Missing Dependency", 
            "Anthropic package not installed.\n\n"
            "Install with: pip install anthropic"
        )
    except Exception as e:
        QMessageBox.critical(
            self, 
            "Error", 
            f"Failed to open AI Assistant:\n{e}"
        )


# ============================================================================
# ALTERNATIVE: Using Azure OpenAI
# ============================================================================

"""
Prerequisites:
    pip install openai

Environment:
    export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
    export AZURE_OPENAI_API_KEY="your-key"
    export AZURE_OPENAI_DEPLOYMENT="gpt-4"
"""

def _show_ai_assistant_azure(self):
    """Opens AI Assistant with Azure OpenAI."""
    try:
        # ... same dialog setup ...
        
        # ============== AZURE OPENAI CONFIGURATION ==============
        import os
        from openai import AzureOpenAI
        
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        
        if not all([endpoint, api_key]):
            QMessageBox.warning(
                self,
                "Configuration Missing",
                "Please set Azure OpenAI environment variables:\n"
                "- AZURE_OPENAI_ENDPOINT\n"
                "- AZURE_OPENAI_API_KEY\n"
                "- AZURE_OPENAI_DEPLOYMENT (optional)"
            )
            return
        
        client = AzureOpenAI(
            api_key=api_key,
            api_version="2024-02-15-preview",
            azure_endpoint=endpoint
        )
        
        class AzureOpenAIWrapper:
            def __init__(self, azure_client, deployment_name):
                self.client = azure_client
                self.deployment = deployment_name
            
            def chat(self, system: str, user: str, temperature: float = 0.2):
                """Call Azure OpenAI Chat Completions API."""
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    temperature=temperature,
                    max_tokens=4096
                )
                return response.choices[0].message.content
        
        wrapped_client = AzureOpenAIWrapper(client, deployment)
        dialog.set_api_client(wrapped_client)
        # ========================================================
        
        dialog.exec()
    except Exception as e:
        QMessageBox.critical(
            self, 
            "Error", 
            f"Failed to open AI Assistant:\n{e}"
        )


# ============================================================================
# ALTERNATIVE: Using Local LLM (Ollama)
# ============================================================================

"""
Prerequisites:
    1. Install Ollama: https://ollama.ai/
    2. Pull a model: ollama pull llama2
    3. pip install requests

No API key needed - runs locally!
"""

def _show_ai_assistant_ollama(self):
    """Opens AI Assistant with local Ollama LLM."""
    try:
        # ... same dialog setup ...
        
        # ============== OLLAMA CONFIGURATION ==============
        import requests
        
        class OllamaWrapper:
            def __init__(self, base_url="http://localhost:11434", model="llama2"):
                self.base_url = base_url
                self.model = model
            
            def chat(self, system: str, user: str, temperature: float = 0.2):
                """Call local Ollama API."""
                # Combine system and user prompts for Ollama
                combined_prompt = f"{system}\n\n{user}"
                
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": combined_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature
                        }
                    },
                    timeout=120  # Local models can be slow
                )
                response.raise_for_status()
                return response.json()["response"]
        
        # Test connection
        try:
            requests.get("http://localhost:11434/api/version", timeout=2)
        except requests.RequestException:
            QMessageBox.warning(
                self,
                "Ollama Not Running",
                "Ollama server is not accessible at http://localhost:11434\n\n"
                "Please start Ollama:\n"
                "1. Install from https://ollama.ai/\n"
                "2. Run: ollama serve\n"
                "3. Pull a model: ollama pull llama2"
            )
            return
        
        wrapped_client = OllamaWrapper(model="llama2")  # or "mistral", "codellama"
        dialog.set_api_client(wrapped_client)
        # ==================================================
        
        dialog.exec()
    except Exception as e:
        QMessageBox.critical(
            self, 
            "Error", 
            f"Failed to open AI Assistant:\n{e}"
        )


# ============================================================================
# TESTING WITHOUT LLM
# ============================================================================

"""
For testing the UI and context collection without an LLM API:
"""

def _show_ai_assistant_mock(self):
    """Opens AI Assistant with mock responses for testing."""
    try:
        # ... same dialog setup ...
        
        class MockLLMClient:
            def chat(self, system: str, user: str, temperature: float = 0.2):
                """Return mock analysis response."""
                return f"""
**Mock AI Analysis** (for testing)

System Prompt Length: {len(system)} characters
User Prompt Length: {len(user)} characters

Your question has been received and processed. In production, this would contain:

1. **Observations**
   - Data points extracted from your context
   - Current device states and signal qualities
   - Relevant log entries and timestamps

2. **Analysis**
   - Protocol-specific interpretation
   - Standard references (IEC 61850, Modbus, etc.)
   - Correlation between events

3. **Likely Causes**
   - Ranked list of potential issues
   - Supporting evidence from your data
   - Confidence levels

4. **Recommended Actions**
   - Concrete configuration changes
   - Verification steps
   - Preventive measures

To enable real AI responses, configure an LLM provider in the code.
See examples/ai_assistant_integration_example.py for details.
"""
        
        dialog.set_api_client(MockLLMClient())
        dialog.exec()
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to open AI Assistant:\n{e}")
