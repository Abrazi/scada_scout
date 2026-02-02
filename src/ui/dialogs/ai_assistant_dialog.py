"""
AI Assistant Dialog - User Interface
Provides a chat-like interface for industrial protocol analysis
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTextEdit, QLabel, QComboBox, QCheckBox, QGroupBox,
    QSplitter, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QSettings
from PySide6.QtGui import QFont
from datetime import datetime, timedelta

from src.core.ai_assistant import AIAssistantContext
from src.core.ai_prompts import INDUSTRIAL_SYSTEM_PROMPT, build_user_prompt


class AIWorkerThread(QThread):
    """
    Background thread for AI API calls to prevent UI freezing.
    """
    response_ready = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, system_prompt: str, user_prompt: str, api_client=None):
        super().__init__()
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.api_client = api_client
    
    def run(self):
        """Execute AI API call in background."""
        try:
            if not self.api_client:
                self.error_occurred.emit(
                    "AI API client not configured. Please set up your LLM provider "
                    "(OpenAI, Anthropic, etc.) in application settings."
                )
                return
            
            # Call your LLM API here
            # Example structure (adapt to your provider):
            # response = self.api_client.chat.completions.create(
            #     model="gpt-4",
            #     messages=[
            #         {"role": "system", "content": self.system_prompt},
            #         {"role": "user", "content": self.user_prompt}
            #     ],
            #     temperature=0.2
            # )
            # result = response.choices[0].message.content
            
            # Placeholder response for testing
            result = (
                "AI Assistant Response (Placeholder)\n\n"
                "To enable actual AI responses, configure your LLM API client.\n\n"
                "The context has been properly formatted and would be sent to:\n"
                f"- System Prompt Length: {len(self.system_prompt)} chars\n"
                f"- User Prompt Length: {len(self.user_prompt)} chars\n\n"
                "Supported providers: OpenAI, Anthropic Claude, Azure OpenAI, etc."
            )
            
            self.response_ready.emit(result)
        
        except Exception as e:
            self.error_occurred.emit(f"AI API Error: {str(e)}")


class AIAssistantDialog(QDialog):
    """
    AI Assistant dialog for industrial protocol analysis.
    Provides context selection, question input, and response display.
    """
    
    def __init__(self, device_manager, watch_list_manager=None, 
                 protocol_gateway=None, event_logger=None, parent=None):
        super().__init__(parent)
        
        self.device_manager = device_manager
        self.context_collector = AIAssistantContext(
            device_manager=device_manager,
            watch_list_manager=watch_list_manager,
            protocol_gateway=protocol_gateway,
            event_logger=event_logger
        )
        
        self.settings = QSettings("ScadaScout", "UI")
        self.api_client = None  # Will be created from settings
        self.worker_thread = None
        
        self.setWindowTitle("AI Assistant - Industrial Protocol Analysis")
        self.setMinimumSize(1000, 700)
        
        self._init_ui()
        self._create_api_client()  # Create client from saved settings
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Title and description
        title_label = QLabel("🤖 Industrial Protocol AI Assistant")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        desc_label = QLabel(
            "Ask questions about device configurations, signal analysis, "
            "log troubleshooting, or protocol-specific issues."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Context selection group
        context_group = QGroupBox("Context to Include")
        context_layout = QVBoxLayout()
        
        # Device filter
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Focus on Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItem("All Devices", None)
        for device in self.device_manager.get_all_devices():
            self.device_combo.addItem(device.config.name, device.config.name)
        device_layout.addWidget(self.device_combo)
        device_layout.addStretch()
        context_layout.addLayout(device_layout)
        
        # Context checkboxes
        self.context_checkboxes = {}
        context_options = [
            ("device_config", "Device Configurations", True),
            ("signals", "Signal Status", True),
            ("logs", "Event Logs (Recent)", True),
            ("logs_all", "All Event History", False),
            ("watchlist", "Watch List", False),
            ("gateway", "Protocol Gateway", False),
            ("protocol_details", "Protocol Details", False),
        ]
        
        checkbox_layout = QHBoxLayout()
        for key, label, default in context_options:
            cb = QCheckBox(label)
            cb.setChecked(default)
            self.context_checkboxes[key] = cb
            checkbox_layout.addWidget(cb)
        context_layout.addLayout(checkbox_layout)
        
        context_group.setLayout(context_layout)
        layout.addWidget(context_group)
        
        # Splitter for question/response
        splitter = QSplitter(Qt.Vertical)
        
        # Question input
        question_widget = QGroupBox("Your Question")
        question_layout = QVBoxLayout()
        
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText(
            "Examples:\n"
            "• Why is device 'IED1' showing INVALID quality on signal 'MMXU1.TotW.mag'?\n"
            "• What could cause Modbus timeouts on device 'PLC1'?\n"
            "• Analyze the IEC 61850 control failure in the logs\n"
            "• Compare signal update rates across all devices\n"
        )
        self.question_input.setMaximumHeight(120)
        question_layout.addWidget(self.question_input)
        
        question_widget.setLayout(question_layout)
        splitter.addWidget(question_widget)
        
        # Response display
        response_widget = QGroupBox("AI Analysis")
        response_layout = QVBoxLayout()
        
        self.response_display = QTextEdit()
        self.response_display.setReadOnly(True)
        self.response_display.setPlaceholderText("AI response will appear here...")
        response_layout.addWidget(self.response_display)
        
        response_widget.setLayout(response_layout)
        splitter.addWidget(response_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter, stretch=1)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.preview_context_btn = QPushButton("Preview Context")
        self.preview_context_btn.clicked.connect(self._preview_context)
        button_layout.addWidget(self.preview_context_btn)
        
        button_layout.addStretch()
        
        self.analyze_btn = QPushButton("🔍 Analyze")
        self.analyze_btn.setDefault(True)
        self.analyze_btn.clicked.connect(self._on_analyze)
        button_layout.addWidget(self.analyze_btn)
        
        self.copy_btn = QPushButton("Copy Response")
        self.copy_btn.clicked.connect(self._copy_response)
        button_layout.addWidget(self.copy_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _collect_context(self) -> dict:
        """Collect selected context from application state."""
        device_name = self.device_combo.currentData()
        context = {}
        
        if self.context_checkboxes["device_config"].isChecked():
            context["devices_context"] = self.context_collector.get_devices_summary(
                [device_name] if device_name else None
            )
        
        if self.context_checkboxes["signals"].isChecked():
            context["signals_context"] = self.context_collector.get_signals_summary(
                device_name=device_name
            )
        
        if self.context_checkboxes["logs"].isChecked():
            context["logs_context"] = self.context_collector.get_event_logs(
                device_name=device_name,
                limit=50  # Recent 50 events
            )
        
        # Get ALL event history if requested (for comprehensive analysis)
        if self.context_checkboxes["logs_all"].isChecked():
            context["logs_context"] = self.context_collector.get_event_logs(
                device_name=device_name,
                since=datetime.now() - timedelta(hours=24),  # Last 24 hours
                limit=500  # Much larger limit for comprehensive analysis
            )
        
        if self.context_checkboxes["watchlist"].isChecked():
            context["watchlist_context"] = self.context_collector.get_watchlist_summary()
        
        if self.context_checkboxes["gateway"].isChecked():
            context["gateway_context"] = self.context_collector.get_gateway_summary()
        
        if self.context_checkboxes["protocol_details"].isChecked() and device_name:
            context["protocol_details"] = self.context_collector.get_protocol_details(device_name)
        
        return context
    
    def _preview_context(self):
        """Show a preview of what context will be sent to AI."""
        question = self.question_input.toPlainText().strip()
        if not question:
            question = "[No question provided yet]"
        
        context = self._collect_context()
        user_prompt = build_user_prompt(question, **context)
        
        # Show in a dialog
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("Context Preview")
        preview_dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        info_label = QLabel(
            f"System Prompt: {len(INDUSTRIAL_SYSTEM_PROMPT)} characters\n"
            f"User Prompt: {len(user_prompt)} characters\n"
            f"Total Context: ~{(len(INDUSTRIAL_SYSTEM_PROMPT) + len(user_prompt)) / 1000:.1f}K chars"
        )
        layout.addWidget(info_label)
        
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setPlainText(user_prompt)
        layout.addWidget(preview_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(preview_dialog.accept)
        layout.addWidget(close_btn)
        
        preview_dialog.setLayout(layout)
        preview_dialog.exec()
    
    def _on_analyze(self):
        """Handle analyze button click."""
        question = self.question_input.toPlainText().strip()
        
        if not question:
            QMessageBox.warning(
                self,
                "No Question",
                "Please enter a question or analysis request."
            )
            return
        
        # Disable button during analysis
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")
        self.response_display.setPlainText("Analyzing... Please wait.")
        
        # Collect context
        context = self._collect_context()
        user_prompt = build_user_prompt(question, **context)
        
        # Start worker thread
        self.worker_thread = AIWorkerThread(
            system_prompt=INDUSTRIAL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            api_client=self.api_client
        )
        self.worker_thread.response_ready.connect(self._on_response_ready)
        self.worker_thread.error_occurred.connect(self._on_error)
        self.worker_thread.finished.connect(self._on_analysis_finished)
        self.worker_thread.start()
    
    def _on_response_ready(self, response: str):
        """Handle AI response."""
        self.response_display.setPlainText(response)
    
    def _on_error(self, error_msg: str):
        """Handle AI error."""
        self.response_display.setPlainText(f"ERROR:\n\n{error_msg}")
    
    def _on_analysis_finished(self):
        """Re-enable analyze button after completion."""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍 Analyze")
    
    def _copy_response(self):
        """Copy response to clipboard."""
        from PySide6.QtGui import QGuiApplication
        
        response = self.response_display.toPlainText()
        if response:
            QGuiApplication.clipboard().setText(response)
            QMessageBox.information(self, "Copied", "Response copied to clipboard.")
    
    def _create_api_client(self):
        """Create API client from saved settings."""
        provider = self.settings.value("ai_provider", "Disabled")
        
        if provider == "Disabled":
            self.api_client = None
            return
        
        try:
            if provider == "OpenAI":
                from openai import OpenAI
                api_key = self.settings.value("ai_openai_key", "")
                if not api_key:
                    return
                
                client = OpenAI(api_key=api_key)
                model = self.settings.value("ai_openai_model", "gpt-4-turbo-preview")
                temperature = self.settings.value("ai_temperature", 20, type=int) / 100.0
                max_tokens = self.settings.value("ai_max_tokens", 4096, type=int)
                
                class OpenAIWrapper:
                    def __init__(self, openai_client, model_name, temp, max_tok):
                        self.client = openai_client
                        self.model = model_name
                        self.temperature = temp
                        self.max_tokens = max_tok
                    
                    def chat(self, system: str, user: str, temperature: float = None):
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system},
                                {"role": "user", "content": user}
                            ],
                            temperature=temperature or self.temperature,
                            max_tokens=self.max_tokens
                        )
                        return response.choices[0].message.content
                
                self.api_client = OpenAIWrapper(client, model, temperature, max_tokens)
            
            elif provider == "Anthropic Claude":
                from anthropic import Anthropic
                api_key = self.settings.value("ai_anthropic_key", "")
                if not api_key:
                    return
                
                client = Anthropic(api_key=api_key)
                model = self.settings.value("ai_anthropic_model", "claude-3-opus-20240229")
                temperature = self.settings.value("ai_temperature", 20, type=int) / 100.0
                max_tokens = self.settings.value("ai_max_tokens", 4096, type=int)
                
                class AnthropicWrapper:
                    def __init__(self, anthropic_client, model_name, temp, max_tok):
                        self.client = anthropic_client
                        self.model = model_name
                        self.temperature = temp
                        self.max_tokens = max_tok
                    
                    def chat(self, system: str, user: str, temperature: float = None):
                        message = self.client.messages.create(
                            model=self.model,
                            max_tokens=self.max_tokens,
                            temperature=temperature or self.temperature,
                            system=system,
                            messages=[{"role": "user", "content": user}]
                        )
                        return message.content[0].text
                
                self.api_client = AnthropicWrapper(client, model, temperature, max_tokens)
            
            elif provider == "Azure OpenAI":
                from openai import AzureOpenAI
                endpoint = self.settings.value("ai_azure_endpoint", "")
                api_key = self.settings.value("ai_azure_key", "")
                deployment = self.settings.value("ai_azure_deployment", "gpt-4")
                api_version = self.settings.value("ai_azure_api_version", "2024-02-15-preview")
                
                if not endpoint or not api_key:
                    return
                
                client = AzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=endpoint
                )
                temperature = self.settings.value("ai_temperature", 20, type=int) / 100.0
                max_tokens = self.settings.value("ai_max_tokens", 4096, type=int)
                
                class AzureOpenAIWrapper:
                    def __init__(self, azure_client, deployment_name, temp, max_tok):
                        self.client = azure_client
                        self.deployment = deployment_name
                        self.temperature = temp
                        self.max_tokens = max_tok
                    
                    def chat(self, system: str, user: str, temperature: float = None):
                        response = self.client.chat.completions.create(
                            model=self.deployment,
                            messages=[
                                {"role": "system", "content": system},
                                {"role": "user", "content": user}
                            ],
                            temperature=temperature or self.temperature,
                            max_tokens=self.max_tokens
                        )
                        return response.choices[0].message.content
                
                self.api_client = AzureOpenAIWrapper(client, deployment, temperature, max_tokens)
            
            elif provider == "Ollama (Local)":
                import requests
                base_url = self.settings.value("ai_ollama_url", "http://localhost:11434")
                model = self.settings.value("ai_ollama_model", "llama2")
                temperature = self.settings.value("ai_temperature", 20, type=int) / 100.0
                
                class OllamaWrapper:
                    def __init__(self, url, model_name, temp):
                        self.base_url = url
                        self.model = model_name
                        self.temperature = temp
                    
                    def chat(self, system: str, user: str, temperature: float = None):
                        combined_prompt = f"{system}\\n\\n{user}"
                        response = requests.post(
                            f"{self.base_url}/api/generate",
                            json={
                                "model": self.model,
                                "prompt": combined_prompt,
                                "stream": False,
                                "options": {"temperature": temperature or self.temperature}
                            },
                            timeout=120
                        )
                        response.raise_for_status()
                        return response.json()["response"]
                
                self.api_client = OllamaWrapper(base_url, model, temperature)
            
            elif provider == "Custom":
                endpoint = self.settings.value("ai_custom_endpoint", "")
                api_key = self.settings.value("ai_custom_key", "")
                model = self.settings.value("ai_custom_model", "")
                
                if not endpoint:
                    return
                
                # Basic custom wrapper - user may need to modify based on their API
                class CustomWrapper:
                    def __init__(self, endpoint_url, key, model_name):
                        self.endpoint = endpoint_url
                        self.api_key = key
                        self.model = model_name
                    
                    def chat(self, system: str, user: str, temperature: float = 0.2):
                        # This is a placeholder - customize based on your API
                        import requests
                        response = requests.post(
                            self.endpoint,
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json={
                                "model": self.model,
                                "messages": [
                                    {"role": "system", "content": system},
                                    {"role": "user", "content": user}
                                ],
                                "temperature": temperature
                            },
                            timeout=60
                        )
                        response.raise_for_status()
                        return response.json()["choices"][0]["message"]["content"]
                
                self.api_client = CustomWrapper(endpoint, api_key, model)
        
        except ImportError as e:
            missing_pkg = str(e).split("'")[1] if "'" in str(e) else "required package"
            QMessageBox.warning(
                self,
                "Missing Package",
                f"Cannot use {provider}: {missing_pkg} not installed.\\n\\n"
                f"Install with: pip install {missing_pkg}"
            )
            self.api_client = None
        except Exception as e:
            QMessageBox.warning(
                self,
                "Configuration Error",
                f"Failed to initialize {provider}:\\n{str(e)}"
            )
            self.api_client = None
    
    def set_api_client(self, client):
        """
        Set the LLM API client.
        
        Args:
            client: Configured API client (OpenAI, Anthropic, etc.)
        """
        self.api_client = client
