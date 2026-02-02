# AI Assistant Integration Guide

## Overview

The AI Assistant feature provides intelligent analysis and troubleshooting capabilities for industrial protocols within SCADA Scout. It's optimized for:

- **IEC 61850** (MMS, GOOSE, SV, control blocks, SBO operations)
- **Modbus** (TCP/RTU, registers, data types, endianness)
- **IEC 60870-5-101/103/104** (ASDU, COT, IOA)
- **OPC/OPC UA** (namespaces, nodes, subscriptions)
- Log analysis and troubleshooting
- Signal quality diagnosis
- Configuration validation

## Architecture

### Components

1. **`src/core/ai_prompts.py`**
   - Contains the industrial-optimized system prompt
   - Prompt building utilities for structured context

2. **`src/core/ai_assistant.py`**
   - `AIAssistantContext` class for safe data collection
   - Read-only access to application state
   - Intelligent context filtering and summarization

3. **`src/ui/dialogs/ai_assistant_dialog.py`**
   - User interface with context selection
   - Background thread for API calls (prevents UI freezing)
   - Response display and clipboard integration

### Key Features

- **Protocol-aware context collection**: Automatically formats device configs, signal states, and logs for AI understanding
- **Safety-first design**: Read-only access, size limits, workspace sandboxing
- **Flexible context selection**: Users choose what data to include
- **Background processing**: AI calls run in separate thread to prevent UI blocking

## Quick Start

### 1. Access the AI Assistant

**Menu**: `Help → AI Assistant` (or press `Ctrl+Shift+A`)

### 2. Select Context

Choose what data to include:
- ✅ **Device Configurations** (recommended)
- ✅ **Signal Status** (recommended)
- ✅ **Event Logs** (recommended)
- ☐ **Watch List** (optional - for polling issues)
- ☐ **Protocol Gateway** (optional - for cross-protocol issues)
- ☐ **Protocol Details** (optional - for deep protocol analysis)

### 3. Ask a Question

Examples:
```
Why is device 'IED1' showing INVALID quality on signal 'MMXU1.TotW.mag'?

What could cause Modbus timeouts on device 'PLC1' with unit ID 1?

Analyze the IEC 61850 SBO control failure in the recent logs.

Compare signal update rates across all devices and identify bottlenecks.

Why is the gateway mapping from IEC61850 to Modbus not updating?
```

### 4. Review Analysis

The AI will provide:
- **Observations**: What the data shows
- **Analysis**: Protocol-specific interpretation
- **Likely Causes**: Ranked by probability
- **Recommended Actions**: Concrete next steps

## Configuration

### Setting Up Your LLM Provider

The AI Assistant requires an LLM API client. Configure it in `src/ui/main_window.py` in the `_show_ai_assistant()` method:

#### Option 1: OpenAI

```python
from openai import OpenAI

def _show_ai_assistant(self):
    # ... existing code ...
    
    client = OpenAI(api_key="your-api-key-here")
    dialog.set_api_client(client)
    
    dialog.exec()
```

#### Option 2: Anthropic Claude

```python
from anthropic import Anthropic

def _show_ai_assistant(self):
    # ... existing code ...
    
    client = Anthropic(api_key="your-api-key-here")
    dialog.set_api_client(client)
    
    dialog.exec()
```

#### Option 3: Azure OpenAI

```python
from openai import AzureOpenAI

def _show_ai_assistant(self):
    # ... existing code ...
    
    client = AzureOpenAI(
        api_key="your-api-key",
        api_version="2024-02-15-preview",
        azure_endpoint="your-endpoint"
    )
    dialog.set_api_client(client)
    
    dialog.exec()
```

### Custom API Wrapper

If using a different provider, wrap it to match this interface:

```python
class CustomLLMClient:
    def chat(self, system: str, user: str, temperature: float = 0.2):
        """
        Send prompt and return response.
        
        Args:
            system: System/developer prompt
            user: User prompt with context
            temperature: Sampling temperature (0.2 recommended for troubleshooting)
        
        Returns:
            str: AI response
        """
        # Your API call here
        pass
```

Then update `AIWorkerThread.run()` in `src/ui/dialogs/ai_assistant_dialog.py` to use your client.

## Advanced Usage

### Programmatic Context Collection

```python
from src.core.ai_assistant import AIAssistantContext
from src.core.ai_prompts import build_user_prompt, INDUSTRIAL_SYSTEM_PROMPT

# Initialize context collector
context = AIAssistantContext(
    device_manager=device_manager,
    watch_list_manager=watch_list_mgr,
    protocol_gateway=gateway,
    event_logger=logger
)

# Collect specific device diagnostics
diagnostic_report = context.get_diagnostic_context(device_name="IED1")

# Build full prompt
user_prompt = build_user_prompt(
    question="Why is IED1 timing out?",
    devices_context=context.get_devices_summary(["IED1"]),
    signals_context=context.get_signals_summary("IED1"),
    logs_context=context.get_event_logs(device_name="IED1"),
    protocol_details=context.get_protocol_details("IED1")
)

# Send to LLM
response = llm_client.chat(
    system=INDUSTRIAL_SYSTEM_PROMPT,
    user=user_prompt,
    temperature=0.2
)
```

### Reading Configuration Files

```python
# Safely read a config file (size-limited, workspace-sandboxed)
config_content = context.read_config_file_safe(
    "/home/majid/Documents/scada_scout/devices.json"
)

user_prompt = build_user_prompt(
    question="Analyze my device configuration for issues",
    config_files=config_content
)
```

### Filtering Event Logs

```python
from src.core.event_logger import EventType
from datetime import datetime, timedelta

# Get only errors from last 30 minutes
logs = context.get_event_logs(
    device_name="PLC1",
    event_types=[EventType.ERROR, EventType.WARNING],
    since=datetime.now() - timedelta(minutes=30),
    limit=100
)
```

## Best Practices

### For Users

1. **Be specific**: "Device 'IED1' signal 'MMXU1.TotW' quality INVALID" is better than "signal not working"
2. **Include timestamps**: "Since 14:30" or "in the last hour"
3. **Mention protocols**: Helps AI apply correct standards and rules
4. **Focus context**: Uncheck unrelated context to improve response speed and accuracy
5. **Preview context**: Use "Preview Context" to see what's being sent

### For Developers

1. **Temperature = 0.2**: Industrial troubleshooting requires precision, not creativity
2. **Token limits**: Monitor prompt size (shown in preview) - trim if >100K chars
3. **Error handling**: AI responses should be treated as suggestions, not commands
4. **Privacy**: Never include credentials or sensitive IP addresses in prompts
5. **Validation**: Always validate AI recommendations before applying changes

## Safety & Security

### Built-in Protections

- ✅ **Read-only access**: AI Assistant cannot modify devices, signals, or configurations
- ✅ **Workspace sandboxing**: File reads restricted to project directory
- ✅ **Size limits**: Files limited to 50KB, logs to 200 entries
- ✅ **No execution**: AI cannot run commands or scripts
- ✅ **Data validation**: All inputs sanitized and validated

### User Responsibilities

- Never paste credentials or API keys into questions
- Review all recommended actions before applying
- Treat AI responses as expert suggestions, not guaranteed solutions
- Verify protocol-specific claims against standards documentation

## Troubleshooting

### "AI API client not configured"

Configure your LLM provider in `_show_ai_assistant()` as shown in the Configuration section above.

### Empty or missing context

Ensure devices are connected and signals have been read at least once. Use "Preview Context" to verify data is available.

### Slow responses

- Reduce context by unchecking unnecessary options
- Focus on a single device instead of "All Devices"
- Use "Preview Context" to check prompt size (keep under 50K chars for best performance)

### API errors

Check:
- API key is valid and has credits/quota
- Network connectivity
- Rate limits on your API plan
- Error message in response display

### Response quality issues

- Be more specific in your question
- Include relevant protocol details (addresses, object references, etc.)
- Add recent log entries for context
- Use "Protocol Details" checkbox for deep protocol analysis

## Example Workflows

### Troubleshooting Modbus Timeouts

1. Select device from dropdown
2. Check: Device Config, Signal Status, Event Logs
3. Ask: "Why is device 'PLC1' timing out on Modbus reads? Unit ID 1, register 40001-40010"
4. Review analysis of network issues, unit ID mismatches, or data type problems

### Analyzing IEC 61850 Control Failures

1. Select IEC 61850 device
2. Check: Device Config, Event Logs, Protocol Details
3. Ask: "Why did SBO control fail for XCBR1.Pos? See error in logs at 14:35"
4. Get protocol-specific analysis of control model, timeout, or response issues

### Gateway Mapping Issues

1. Select "All Devices"
2. Check: Device Config, Protocol Gateway, Signal Status
3. Ask: "Gateway mapping from IED1::MMXU1.TotW to PLC1::40001 not updating. Why?"
4. Receive analysis of source signal quality, target device status, or mapping configuration

## API Reference

### AIAssistantContext

```python
context = AIAssistantContext(
    device_manager=DeviceManager,
    watch_list_manager=WatchListManager,  # Optional
    protocol_gateway=ProtocolGateway,     # Optional
    event_logger=EventLogger              # Optional
)

# Device summaries
devices_summary = context.get_devices_summary(device_names=["IED1", "PLC1"])

# Signal status with quality flags
signals_summary = context.get_signals_summary(device_name="IED1", limit=100)

# Filtered event logs
logs = context.get_event_logs(
    device_name="IED1",
    event_types=[EventType.ERROR],
    since=datetime.now() - timedelta(hours=1),
    limit=200
)

# Watch list performance
watchlist = context.get_watchlist_summary()

# Gateway mappings
gateway = context.get_gateway_summary()

# Protocol metadata
protocol_info = context.get_protocol_details("IED1")

# Comprehensive diagnostic report
full_report = context.get_diagnostic_context(device_name="IED1")

# Safe config file reading
config = context.read_config_file_safe("/path/to/config.json")
```

### build_user_prompt

```python
from src.core.ai_prompts import build_user_prompt

prompt = build_user_prompt(
    question="Your question here",
    devices_context=devices_summary,      # Optional
    signals_context=signals_summary,      # Optional
    logs_context=logs,                    # Optional
    gateway_context=gateway,              # Optional
    watchlist_context=watchlist,          # Optional
    protocol_details=protocol_info,       # Optional
    config_files=config_content,          # Optional
    error_context=error_messages          # Optional
)
```

## Future Enhancements

Planned features:
- [ ] Local LLM support (Ollama, LM Studio)
- [ ] Conversation history and follow-up questions
- [ ] Export analysis reports to PDF/HTML
- [ ] Integration with event log right-click context menu
- [ ] Signal comparison and trend analysis
- [ ] Protocol compliance validation
- [ ] SCD file analysis and recommendations

## Support

For issues or questions:
1. Check this guide first
2. Review example workflows above
3. Use "Preview Context" to debug data collection
4. Check event logs for API errors
5. Open an issue on GitHub with:
   - Question asked
   - Context selected
   - Error message (if any)
   - Prompt size from preview

---

**Remember**: The AI Assistant is a powerful analysis tool, but always verify recommendations against protocol standards and your specific system requirements.
