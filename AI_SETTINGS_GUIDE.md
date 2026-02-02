# AI Assistant Settings Configuration - Quick Guide

## Overview

The AI Assistant now has **full runtime configuration** through the Settings dialog. No code changes needed!

## Access Settings

1. **Menu**: `View → ⚙️ Settings...` (or press `Ctrl+,`)
2. Click on **🤖 AI Assistant** tab
3. Configure your preferred LLM provider
4. Click **OK** or **Apply** to save

## Supported Providers

### 1. OpenAI (GPT-4/GPT-3.5)
**Best for**: Production use, highest quality responses

**Setup:**
1. Get API key from https://platform.openai.com/api-keys
2. Select "OpenAI" from Provider dropdown
3. Enter your API key (starts with `sk-...`)
4. Choose model: `gpt-4-turbo-preview` (recommended) or `gpt-3.5-turbo` (faster/cheaper)
5. Click "🧪 Test Connection" to verify
6. Click OK to save

**Cost**: ~$0.04 per query (GPT-4), ~$0.001 per query (GPT-3.5)

---

### 2. Anthropic Claude
**Best for**: Detailed technical analysis, longer context

**Setup:**
1. Get API key from https://console.anthropic.com/
2. Select "Anthropic Claude" from Provider dropdown
3. Enter your API key (starts with `sk-ant-...`)
4. Choose model: `claude-3-opus-20240229` (best) or `claude-3-sonnet-20240229` (faster)
5. Click "🧪 Test Connection"
6. Click OK to save

**Cost**: Similar to GPT-4

---

### 3. Azure OpenAI
**Best for**: Enterprise deployments, private cloud

**Setup:**
1. Get your Azure OpenAI resource details from Azure Portal
2. Select "Azure OpenAI" from Provider dropdown
3. Enter:
   - **Endpoint**: `https://your-resource.openai.azure.com/`
   - **API Key**: From Azure Portal
   - **Deployment**: Your deployment name (e.g., `gpt-4`)
   - **API Version**: `2024-02-15-preview` (default)
4. Click "🧪 Test Connection"
5. Click OK to save

---

### 4. Ollama (Local LLM) - FREE
**Best for**: No internet required, privacy, no API costs

**Setup:**
1. Install Ollama from https://ollama.ai/
2. Open terminal and run:
   ```bash
   ollama serve
   ollama pull llama2
   ```
3. In Settings, select "Ollama (Local)"
4. Base URL: `http://localhost:11434` (default)
5. Choose model: `llama2`, `mistral`, `codellama`, etc.
6. Click "🧪 Test Connection" (will check if Ollama is running)
7. Click OK to save

**Cost**: FREE (runs on your computer)
**Note**: Slower than cloud APIs, requires good CPU/GPU

---

### 5. Custom Provider
**Best for**: Custom LLM deployments, company-specific endpoints

**Setup:**
1. Select "Custom" from Provider dropdown
2. Enter your endpoint URL
3. Enter API key (if required)
4. Enter model name
5. Click OK to save

**Note**: May require code customization in `ai_assistant_dialog.py` for non-standard APIs

---

## Advanced Settings

### Temperature (0-100)
- **Default**: 20 (0.2)
- **Lower values** (0-30): More focused, deterministic (recommended for troubleshooting)
- **Higher values** (50-100): More creative, varied responses

### Max Tokens (1000-16000)
- **Default**: 4096
- Controls maximum response length
- Higher = longer responses (but more expensive)

---

## Quick Setup Examples

### Example 1: OpenAI GPT-4 (Recommended)
```
1. Settings → AI Assistant tab
2. Provider: OpenAI
3. API Key: sk-proj-abc123xyz...
4. Model: gpt-4-turbo-preview
5. Temperature: 20
6. Max Tokens: 4096
7. Test → OK
```

### Example 2: Free Local with Ollama
```bash
# Terminal
ollama serve
ollama pull llama2

# Settings → AI Assistant tab
1. Provider: Ollama (Local)
2. Base URL: http://localhost:11434
3. Model: llama2
4. Test → OK
```

### Example 3: Claude for Deep Analysis
```
1. Settings → AI Assistant tab
2. Provider: Anthropic Claude
3. API Key: sk-ant-abc123...
4. Model: claude-3-opus-20240229
5. Test → OK
```

---

## Using the AI Assistant

1. Press **Ctrl+Shift+A** or **Help → AI Assistant**
2. Select context to include (devices, signals, logs, etc.)
3. Ask your question
4. Click **🔍 Analyze**

### Example Questions
```
Why is device 'IED1' showing INVALID quality on signal 'MMXU1.TotW.mag'?

What could cause Modbus timeouts on device 'PLC1' with unit ID 1?

Analyze the IEC 61850 SBO control failure in the recent logs.

Compare signal update rates across all devices and identify bottlenecks.
```

---

## Troubleshooting

### "AI API client not configured"
→ Go to Settings → AI Assistant tab and configure a provider

### "Missing Package: openai not installed"
→ Install required package:
```bash
pip install openai         # For OpenAI or Azure
pip install anthropic      # For Claude
pip install requests       # For Ollama or Custom
```

### "Connection Failed" (Ollama)
→ Make sure Ollama is running:
```bash
ollama serve
```

### API Key Invalid
→ Check your API key in the provider's dashboard
→ Make sure there are no extra spaces when pasting

### Test Connection Fails
→ Check internet connection (for cloud providers)
→ Verify API key has not expired
→ Check API quota/credits remaining

---

## Switching Providers

You can easily switch between providers:

1. Open Settings → AI Assistant
2. Change Provider dropdown
3. Enter new credentials
4. Test and Save

Settings are saved per provider, so you can switch back without re-entering credentials.

---

## Security Notes

- **API Keys stored locally**: Keys are saved in Qt settings on your computer
- **Not encrypted**: Keys are stored as plain text (like other app settings)
- **For sensitive environments**: Use environment variables or Azure KeyVault
- **Never commit**: Don't commit your `settings.ini` file to version control

---

## Cost Optimization

### Use GPT-3.5 for simple queries
- Change model to `gpt-3.5-turbo`
- ~25x cheaper than GPT-4
- Good for quick checks

### Use Ollama for development
- Free and unlimited
- No internet required
- Good for testing

### Reduce context
- Uncheck unnecessary context options
- Focus on single device instead of "All Devices"
- Fewer tokens = lower cost

---

## Next Steps

1. ✅ Configure your preferred provider in Settings
2. ✅ Test the connection
3. ✅ Try the AI Assistant (Ctrl+Shift+A)
4. ✅ Ask a question about your devices

**All configuration is now runtime - no code changes needed!** 🎉
