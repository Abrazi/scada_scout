import os
import time
import xml.etree.ElementTree as ET

from src.core.scd_parser import SCDParser

SCD_MINIMAL = '''<?xml version="1.0"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
  <DataTypeTemplates>
    <EnumType id="E1">
      <EnumVal ord="1">ON</EnumVal>
      <EnumVal ord="0">OFF</EnumVal>
    </EnumType>
    <LNodeType id="LN1" lnClass="XCBR">
      <DO name="Beh" type="DO1"/>
    </LNodeType>
    <DOType id="DO1">
      <DA name="stVal" bType="Enum" fc="ST" type="E1"/>
    </DOType>
  </DataTypeTemplates>
  <IED name="IED1">
    <AccessPoint>
      <Server>
        <LDevice inst="LD1">
          <LN lnClass="XCBR" lnType="LN1" inst="1"/>
        </LDevice>
      </Server>
    </AccessPoint>
  </IED>
</SCL>
'''


def test_scdparser_works_with_legacy_4tuple_cache(tmp_path):
    """Ensure SCDParser tolerates legacy 4-tuple cache entries and normalizes them.

    Regression for: "not enough values to unpack (expected 5, got 4)" when a
    background worker had cached a 4-tuple result.
    """
    p = tmp_path / "minimal.scd"
    p.write_text(SCD_MINIMAL)

    # Pre-parse using ET to simulate the old worker result (mtime, tree, root, ns)
    tree = ET.parse(str(p))
    root = tree.getroot()
    mtime = os.path.getmtime(str(p))
    ns = {'scl': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

    # Insert legacy 4-tuple into cache
    SCDParser._cache[str(p)] = (mtime, tree, root, ns)

    # Constructing SCDParser must not raise and should populate templates
    parser = SCDParser(str(p))
    assert parser.root is not None
    assert isinstance(parser._templates, dict)

    # Cache may be a legacy 4-tuple (templates deferred) or a normalized 5-tuple.
    cached = SCDParser._cache.get(str(p))
    assert isinstance(cached, tuple) and len(cached) in (4, 5)
    assert cached[0] == mtime

    # If templates were deferred, they must be created on-demand when required
    if len(cached) == 4:
        # Request a full structure expansion which requires templates
        root = parser.get_structure(ied_name="IED1")
        assert root is not None and any(c.name == 'LD1' or 'LD1' in c.name for c in root.children)
        # Cache should now be normalized to include templates
        cached2 = SCDParser._cache.get(str(p))
        assert isinstance(cached2, tuple) and len(cached2) == 5
