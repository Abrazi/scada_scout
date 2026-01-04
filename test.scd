<?xml version="1.0" encoding="UTF-8"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
    <Header id="TestConfig"/>
    <IED name="TestIED_ABB_Relion">
        <AccessPoint name="AP1">
            <Server>
                <LDevice inst="LD0">
                    <LN0 lnClass="LLN0" inst="" lnType="LNT_LLN0"/>
                    <LN lnClass="MMXU" inst="1" prefix="" lnType="LNT_MMXU"/>
                </LDevice>
            </Server>
        </AccessPoint>
    </IED>
    <DataTypeTemplates>
        <LNodeType id="LNT_LLN0" lnClass="LLN0">
            <DO name="NamPlt" type="DOT_NamPlt"/>
            <DO name="Health" type="DOT_ENS"/>
        </LNodeType>
        <LNodeType id="LNT_MMXU" lnClass="MMXU">
            <DO name="TotW" type="DOT_MV"/>
            <DO name="PhV" type="DOT_WYE"/>
        </LNodeType>
        <DOType id="DOT_NamPlt" cdc="LPL">
            <DA name="vendor" bType="VisString255" fc="DC"/>
            <DA name="swRev" bType="VisString255" fc="DC"/>
        </DOType>
        <DOType id="DOT_ENS" cdc="ENS">
            <DA name="stVal" bType="Enum" fc="ST"/>
            <DA name="q" bType="Quality" fc="ST"/>
        </DOType>
        <DOType id="DOT_MV" cdc="MV">
            <DA name="mag" bType="Struct" type="DAT_AnalogueValue" fc="MX"/>
            <DA name="q" bType="Quality" fc="MX"/>
        </DOType>
        <DOType id="DOT_WYE" cdc="WYE">
            <SDO name="phsA" type="DOT_MV"/>
            <SDO name="phsB" type="DOT_MV"/>
        </DOType>
    </DataTypeTemplates>
</SCL>
