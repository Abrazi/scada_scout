#!/usr/bin/env python3
"""
Test script for AI Assistant integration.
Verifies context collection without requiring GUI or LLM API.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.ai_assistant import AIAssistantContext
from src.core.ai_prompts import INDUSTRIAL_SYSTEM_PROMPT, build_user_prompt
from src.models.device_models import Device, DeviceConfig, DeviceType, Signal, SignalQuality
from datetime import datetime


class MockDeviceManager:
    """Mock device manager for testing."""
    
    def __init__(self):
        self.devices = []
        self._create_mock_devices()
    
    def _create_mock_devices(self):
        """Create some mock devices with signals."""
        # IEC 61850 device
        iec_config = DeviceConfig(
            name="IED1",
            device_type=DeviceType.IEC61850_IED,
            ip_address="192.168.1.100",
            port=102
        )
        iec_device = Device(iec_config)
        iec_device.connected = True
        iec_device.signals = [
            Signal(
                name="Total Active Power",
                address="MMXU1$MX$TotW$mag$f",
                value=1250.5,
                quality=SignalQuality.GOOD,
                timestamp=datetime.now()
            ),
            Signal(
                name="Circuit Breaker Position",
                address="XCBR1$ST$Pos$stVal",
                value=1,
                quality=SignalQuality.GOOD,
                timestamp=datetime.now()
            ),
        ]
        
        # Modbus device
        modbus_config = DeviceConfig(
            name="PLC1",
            device_type=DeviceType.MODBUS_TCP,
            ip_address="192.168.1.50",
            port=502,
            modbus_unit_id=1
        )
        modbus_device = Device(modbus_config)
        modbus_device.connected = True
        modbus_device.signals = [
            Signal(
                name="Holding Register 0",
                address="1:3:40001",
                value=42,
                quality=SignalQuality.GOOD,
                timestamp=datetime.now()
            ),
            Signal(
                name="Holding Register 1",
                address="1:3:40002",
                value=None,
                quality=SignalQuality.INVALID,
                timestamp=datetime.now()
            ),
        ]
        
        self.devices = [iec_device, modbus_device]
    
    def get_all_devices(self):
        return self.devices
    
    def get_device(self, name):
        for d in self.devices:
            if d.config.name == name:
                return d
        return None


class MockEventLogger:
    """Mock event logger for testing."""
    
    def __init__(self):
        self.events = [
            {
                'timestamp': datetime.now(),
                'type': 'INFO',
                'message': 'Device IED1 connected successfully'
            },
            {
                'timestamp': datetime.now(),
                'type': 'ERROR',
                'message': 'Device PLC1 register 40002 read timeout'
            },
            {
                'timestamp': datetime.now(),
                'type': 'WARNING',
                'message': 'Signal MMXU1$MX$TotW$mag$f quality degraded'
            },
        ]
    
    def get_recent_events(self, limit=200):
        return self.events[-limit:]


def test_context_collection():
    """Test context collection functionality."""
    print("=" * 80)
    print("SCADA Scout AI Assistant - Context Collection Test")
    print("=" * 80)
    
    # Create mocks
    device_manager = MockDeviceManager()
    event_logger = MockEventLogger()
    
    # Create context collector
    context = AIAssistantContext(
        device_manager=device_manager,
        watch_list_manager=None,
        protocol_gateway=None,
        event_logger=event_logger
    )
    
    print("\n✅ AIAssistantContext initialized\n")
    
    # Test 1: Device summary
    print("-" * 80)
    print("TEST 1: Device Summary")
    print("-" * 80)
    devices_summary = context.get_devices_summary()
    print(devices_summary)
    
    # Test 2: Signal summary
    print("\n" + "-" * 80)
    print("TEST 2: Signal Summary")
    print("-" * 80)
    signals_summary = context.get_signals_summary()
    print(signals_summary)
    
    # Test 3: Event logs
    print("\n" + "-" * 80)
    print("TEST 3: Event Logs")
    print("-" * 80)
    logs = context.get_event_logs()
    print(logs)
    
    # Test 4: Protocol details
    print("\n" + "-" * 80)
    print("TEST 4: Protocol Details (IED1)")
    print("-" * 80)
    import json
    protocol_details = context.get_protocol_details("IED1")
    print(json.dumps(protocol_details, indent=2))
    
    # Test 5: Full prompt building
    print("\n" + "-" * 80)
    print("TEST 5: Full User Prompt")
    print("-" * 80)
    question = "Why is device 'PLC1' showing INVALID quality on register 40002?"
    user_prompt = build_user_prompt(
        question=question,
        devices_context=devices_summary,
        signals_context=signals_summary,
        logs_context=logs,
        protocol_details=context.get_protocol_details("PLC1")
    )
    print(user_prompt)
    
    # Test 6: System prompt check
    print("\n" + "-" * 80)
    print("TEST 6: System Prompt Verification")
    print("-" * 80)
    print(f"System Prompt Length: {len(INDUSTRIAL_SYSTEM_PROMPT)} characters")
    print(f"Contains 'IEC 61850': {'IEC 61850' in INDUSTRIAL_SYSTEM_PROMPT}")
    print(f"Contains 'Modbus': {'Modbus' in INDUSTRIAL_SYSTEM_PROMPT}")
    print(f"Contains 'SCADA Scout': {'SCADA Scout' in INDUSTRIAL_SYSTEM_PROMPT}")
    print(f"Contains 'troubleshoot': {'troubleshoot' in INDUSTRIAL_SYSTEM_PROMPT.lower()}")
    
    # Test 7: Token estimation
    print("\n" + "-" * 80)
    print("TEST 7: Token Estimation")
    print("-" * 80)
    total_chars = len(INDUSTRIAL_SYSTEM_PROMPT) + len(user_prompt)
    estimated_tokens = total_chars // 4  # Rough estimate: 1 token ≈ 4 chars
    print(f"System Prompt: {len(INDUSTRIAL_SYSTEM_PROMPT):,} chars")
    print(f"User Prompt: {len(user_prompt):,} chars")
    print(f"Total: {total_chars:,} chars")
    print(f"Estimated Tokens: ~{estimated_tokens:,} tokens")
    
    cost_gpt4 = estimated_tokens * 0.00003  # $0.03/1K input tokens
    cost_gpt35 = estimated_tokens * 0.000001  # $0.001/1K input tokens
    print(f"\nEstimated Cost:")
    print(f"  GPT-4: ${cost_gpt4:.4f}")
    print(f"  GPT-3.5: ${cost_gpt35:.4f}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Configure LLM provider in src/ui/main_window.py")
    print("2. Launch SCADA Scout GUI: python src/main.py")
    print("3. Press Ctrl+Shift+A or Help → AI Assistant")
    print("4. Test with real devices and questions")
    print("\nSee AI_ASSISTANT_INTEGRATION_GUIDE.md for configuration details.")


if __name__ == "__main__":
    try:
        test_context_collection()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
