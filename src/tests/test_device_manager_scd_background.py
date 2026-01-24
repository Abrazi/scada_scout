import os
import time
import xml.etree.ElementTree as ET
from concurrent.futures import TimeoutError

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType


def _make_minimal_scd(path):
    content = '''<?xml version="1.0"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
  <DataTypeTemplates>
    <LNodeType id="LN1" lnClass="XCBR">
      <DO name="Beh" type="DO1"/>
    </LNodeType>
    <DOType id="DO1">
      <DA name="stVal" bType="Enum" fc="ST" type="E1"/>
    </DOType>
    <EnumType id="E1"><EnumVal ord="1">ON</EnumVal></EnumType>
  </DataTypeTemplates>
  <IED name="IED1"><AccessPoint><Server><LDevice inst="LD1"><LN lnClass="XCBR" lnType="LN1" inst="1"/></LDevice></Server></AccessPoint></IED>
</SCL>'''
    with open(path, 'w') as f:
        f.write(content)


def test_load_offline_scd_is_non_blocking_and_populates(tmp_path, monkeypatch):
    # Prepare minimal SCD file
    scd = tmp_path / "minimal.scd"
    _make_minimal_scd(scd)

    # Replace the worker parser with a short sleep wrapper that returns the real parse
    import time as _time
    from src.core import workers as _workers

    # Save original and wrap it so we can simulate delay without breaking behavior
    _orig = _workers._parse_scd_file

    def fake_parse(p):
        # simulate expensive parse
        _time.sleep(0.12)
        return _orig(p)

    monkeypatch.setattr(_workers, '_parse_scd_file', fake_parse)

    dm = DeviceManagerCore(config_path=str(tmp_path / 'devices.json'))
    # Use IED name that exists in the SCD so discover() can match it
    config = DeviceConfig(name='IED1', ip_address='127.0.0.1', port=102, scd_file_path=str(scd))

    # Add device (this will call load_offline_scd internally)
    t0 = time.perf_counter()
    dev = dm.add_device(config, save=False)
    took = (time.perf_counter() - t0)

    # Fast return (non-blocking) — should be well under the fake parse sleep
    assert took < 0.05, f"load_offline_scd blocked the caller (took {took:.3f}s)"

    # Wait for background parsing to complete (give generous timeout)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if dev.root_node is not None:
            break
        time.sleep(0.02)

    assert dev.root_node is not None
    assert any(c.name and 'LD1' in c.name for c in dev.root_node.children)
