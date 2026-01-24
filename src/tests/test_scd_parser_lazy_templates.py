import xml.etree.ElementTree as ET
import os

from src.core.scd_parser import SCDParser

SCD_MINIMAL = '''<?xml version="1.0"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
  <IED name="IED1"/>
</SCL>
'''


def test_init_does_not_parse_templates_by_default(tmp_path, monkeypatch):
    p = tmp_path / "minimal.scd"
    p.write_text(SCD_MINIMAL)

    # Monkeypatch _parse_templates to raise if called during __init__
    def _boom(self):
        raise RuntimeError("_parse_templates called during __init__")

    monkeypatch.setattr(SCDParser, '_parse_templates', _boom)

    # Should NOT raise
    parser = SCDParser(str(p))
    assert parser.root is not None
    # Templates remain uninitialized until requested
    assert getattr(parser, '_templates', None) in (None, {})

    # When templates are requested, _parse_templates() will be invoked via _ensure_templates()
    monkeypatch.setattr(SCDParser, '_parse_templates', lambda self: {})
    parser._ensure_templates()
    assert isinstance(parser._templates, dict)
