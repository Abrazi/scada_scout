import os
from tempfile import NamedTemporaryFile

from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter


def _write_scd(contents: str) -> str:
    with NamedTemporaryFile(delete=False, suffix=".scd") as handle:
        handle.write(contents.encode("utf-8"))
        return handle.name


def _make_adapter() -> IEC61850ServerAdapter:
    config = DeviceConfig(
        name="ABBK3A03A1",
        ip_address="127.0.0.1",
        port=10200,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path="",
        protocol_params={"ied_name": "ABBK3A03A1"},
    )
    return IEC61850ServerAdapter(config)


def test_parse_sbo_enhanced_valid():
    scd = """
<SCL>
  <IED name="ABBK3A03A1">
    <LDevice inst="LD0">
      <LN lnClass="CSWI" inst="1">
        <DOI name="Pos">
          <DAI name="ctlModel"><Val>sbo-with-enhanced-security</Val></DAI>
          <DAI name="SBO" />
          <DAI name="SBOw" />
          <DAI name="Oper" />
          <DAI name="Cancel" />
        </DOI>
      </LN>
    </LDevice>
  </IED>
</SCL>
"""
    path = _write_scd(scd)
    try:
        adapter = _make_adapter()
        items = adapter._parse_scd_control_dois(path, "ABBK3A03A1")
        assert len(items) == 1
        dai_names = items[0]["dai_names"]
        missing = adapter._required_sbo_dais(items[0]["ctl_model"]) - dai_names
        assert not missing
    finally:
        os.unlink(path)


def test_parse_sbo_enhanced_missing_oper():
    scd = """
<SCL>
  <IED name="ABBK3A03A1">
    <LDevice inst="LD0">
      <LN lnClass="CSWI" inst="1">
        <DOI name="Pos">
          <DAI name="ctlModel"><Val>sbo-with-enhanced-security</Val></DAI>
          <DAI name="SBO" />
          <DAI name="SBOw" />
          <DAI name="Cancel" />
        </DOI>
      </LN>
    </LDevice>
  </IED>
</SCL>
"""
    path = _write_scd(scd)
    try:
        adapter = _make_adapter()
        items = adapter._parse_scd_control_dois(path, "ABBK3A03A1")
        assert len(items) == 1
        dai_names = items[0]["dai_names"]
        missing = adapter._required_sbo_dais(items[0]["ctl_model"]) - dai_names
        assert "Oper" in missing
    finally:
        os.unlink(path)


def test_parse_sbo_enhanced_missing_sbo_allowed():
    scd = """
<SCL>
  <IED name="ABBK3A03A1">
    <LDevice inst="LD0">
      <LN lnClass="CSWI" inst="1">
        <DOI name="Pos">
          <DAI name="ctlModel"><Val>sbo-with-enhanced-security</Val></DAI>
          <DAI name="SBOw" />
          <DAI name="Oper" />
          <DAI name="Cancel" />
        </DOI>
      </LN>
    </LDevice>
  </IED>
</SCL>
"""
    path = _write_scd(scd)
    try:
        adapter = _make_adapter()
        items = adapter._parse_scd_control_dois(path, "ABBK3A03A1")
        assert len(items) == 1
        dai_names = items[0]["dai_names"]
        missing = adapter._required_sbo_dais(items[0]["ctl_model"]) - dai_names
        assert not missing
    finally:
        os.unlink(path)
