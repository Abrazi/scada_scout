import sys
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Mock classes to avoid full app dependencies
@dataclass
class Signal:
    name: str = "TestSignal"
    address: str = "100"
    value: Any = 0
    enum_map: Dict[int, str] = field(default_factory=dict)

class WatchListWidgetMock:
    def _is_pos_stval(self, signal: Signal) -> bool:
        addr = (signal.address or "").lower()
        name = (signal.name or "").lower()
        return "pos.stval" in addr or "pos$stval" in addr or ("pos" in addr and name == "stval")

    def _extract_numeric_and_enum(self, signal: Signal) -> tuple[int | None, str | None]:
        num = None
        enum_label = None

        mapping = getattr(signal, "enum_map", None)
        if not mapping and self._is_pos_stval(signal):
            mapping = {0: "intermediate", 1: "open", 2: "closed", 3: "bad"}

        val = signal.value
        if isinstance(val, bool):
            num = int(val)
        elif isinstance(val, int):
            num = val
        elif isinstance(val, float) and val.is_integer():
            num = int(val)
        elif isinstance(val, str):
            text = val.strip()
            try:
                if text.lower().startswith("0x"):
                    num = int(text.split()[0], 16)
                else:
                    m = re.search(r"\(([-]?\d+)\)", text)
                    if m:
                        num = int(m.group(1))
                    elif re.fullmatch(r"-?\d+", text):
                        num = int(text)
            except Exception:
                num = None

            if num is None:
                if mapping:
                    for k, v in mapping.items():
                        if str(v).lower() == text.lower():
                            num = int(k)
                            break

            if num is not None and not enum_label:
                m = re.match(r"(.+?)\s*\(\s*[-]?\d+\s*\)", text)
                if m:
                    enum_label = m.group(1).strip()

        if num is not None and mapping and num in mapping:
            enum_label = mapping[num]

        return num, enum_label

    def _format_value(self, signal: Signal) -> str:
        if signal.value is None:
            return "--"

        # Try to format as Hex/Decimal/Enum
        num, enum_label = self._extract_numeric_and_enum(signal)
        if num is not None:
            hex_str = f"0x{num:X}"
            if enum_label:
                return f"{hex_str} ({num}) {enum_label}"
            return f"{hex_str} ({num})"

        return str(signal.value)

def run_tests():
    widget = WatchListWidgetMock()
    
    # Test 1: Generic Integer (Should be Hex + Decimal)
    sig1 = Signal(value=100)
    print(f"Test 1 (Int 100): {widget._format_value(sig1)} (Expected: 0x64 (100))")
    assert "0x64 (100)" in widget._format_value(sig1)

    # Test 2: Integer with Enum Map
    sig2 = Signal(value=1, enum_map={1: "Active", 0: "Inactive"})
    print(f"Test 2 (Enum 1): {widget._format_value(sig2)} (Expected: 0x1 (1) Active)")
    assert "0x1 (1) Active" in widget._format_value(sig2)

    # Test 3: Circuit Breaker pos.stval (Integer)
    sig3 = Signal(name="stval", address="LD0/XCBR1.Pos.stval", value=2)
    print(f"Test 3 (CB Pos 2): {widget._format_value(sig3)} (Expected: 0x2 (2) closed)")
    assert "closed" in widget._format_value(sig3)

    # Test 4: Circuit Breaker pos.stval (String from 61850 lib seems to give strings sometimes?)
    # Assuming value comes as int usually, but let's test string parsing if value was "closed"
    sig4 = Signal(name="stval", address="LD0/XCBR1.Pos.stval", value="closed")
    print(f"Test 4 (CB Pos 'closed'): {widget._format_value(sig4)} (Expected: 0x2 (2) closed)")
    assert "0x2 (2) closed" in widget._format_value(sig4)

    # Test 5: Plain String (Should remain string if no mapping)
    sig5 = Signal(value="Hello")
    print(f"Test 5 (String 'Hello'): {widget._format_value(sig5)} (Expected: Hello)")
    assert widget._format_value(sig5) == "Hello"

    # Test 6: Float (Should remain string)
    sig6 = Signal(value=12.34)
    print(f"Test 6 (Float 12.34): {widget._format_value(sig6)} (Expected: 12.34)")
    assert widget._format_value(sig6) == "12.34"

    print("\nAll tests passed!")

if __name__ == "__main__":
    run_tests()
