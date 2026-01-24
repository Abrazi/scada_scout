import os
import time
import xml.etree.ElementTree as ET

from src.core.device_manager_core import DeviceManagerCore
from src.core.workers import SCDImportWorker
from src.models.device_models import DeviceConfig

SCD_MINIMAL = '''<?xml version="1.0"?>
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
</SCL>
'''


def test_scdimport_worker_expand_now_populates_tree(tmp_path):
    p = tmp_path / 'minimal.scd'
    p.write_text(SCD_MINIMAL)

    dm = DeviceManagerCore(config_path=str(tmp_path / 'devices.json'))
    cfg = DeviceConfig(name='IED1', ip_address='127.0.0.1', port=102, scd_file_path=str(p))

    # Run import worker synchronously with expand-now (defer_full_expansion=False)
    worker = SCDImportWorker(dm, [cfg], defer_full_expansion=False)
    # call run() directly to execute in-test thread
    worker.run()

    dev = dm.get_device('IED1')
    assert dev is not None
    # Because expand-now was requested, the device tree should be populated
    assert dev.root_node is not None
    assert any('LD1' in c.name for c in dev.root_node.children)


def test_scdimport_worker_defer_does_not_block_and_populates_later(tmp_path):
    p = tmp_path / 'minimal.scd'
    p.write_text(SCD_MINIMAL)

    dm = DeviceManagerCore(config_path=str(tmp_path / 'devices.json'))
    cfg = DeviceConfig(name='IED1', ip_address='127.0.0.1', port=102, scd_file_path=str(p))

    worker = SCDImportWorker(dm, [cfg], defer_full_expansion=True)
    t0 = time.perf_counter()
    worker.run()
    elapsed = time.perf_counter() - t0

    # Should return quickly (did not block on expansion)
    assert elapsed < 0.05

    dev = dm.get_device('IED1')
    assert dev is not None

    # Background parse should populate the tree eventually; wait a short while
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if dev.root_node is not None:
            break
        time.sleep(0.02)

    assert dev.root_node is not None
    assert any('LD1' in c.name for c in dev.root_node.children)
