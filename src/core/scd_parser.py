import xml.etree.ElementTree as ET
from typing import Optional, List, Dict
import os
import logging

from src.models.device_models import Node, Signal, SignalType, SignalQuality

logger = logging.getLogger(__name__)

class SCDParser:
    """
    Parses SCL/SCD/CID/ICD files to extract IEC 61850 structure.
    Mimics the logic from the reference 'IEC61850DiscoverIED'.
    """
    
    NS = {'scl': 'http://www.iec.ch/61850/2003/SCL'}

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None
        self._parse()

    def _parse(self):
        if not os.path.exists(self.file_path):
            logger.error(f"SCD file not found: {self.file_path}")
            return
        
        try:
            self.tree = ET.parse(self.file_path)
            self.root = self.tree.getroot()
            # Handle namespaced XML
            # If the root tag has the namespace, we need to use it for queries
            if 'http://www.iec.ch/61850/2003/SCL' in self.root.tag:
                self.ns = self.NS
            else:
                self.ns = {} # No namespace or different one, try to detect or fallback
                
        except Exception as e:
            logger.error(f"Failed to parse SCD file: {e}")

    def get_structure(self, ied_name: Optional[str] = None) -> Node:
        """
        Builds a Node hierarchy (IED -> LD -> LN -> DO) from the file.
        If ied_name is None, picks the first IED found.
        """
        if self.root is None:
            return Node(name="Error_No_SCD")

        # Find IED element
        ied_element = None
        if ied_name:
            ied_element = self.root.find(f".//scl:IED[@name='{ied_name}']", self.ns)
        else:
            ied_element = self.root.find(".//scl:IED", self.ns)
            
        if ied_element is None:
            # Try without namespace if failed
            if ied_name:
               ied_element = self.root.find(f".//IED[@name='{ied_name}']")
            else:
               ied_element = self.root.find(".//IED")

        if ied_element is None:
            return Node(name="IED_Not_Found")

        parsed_ied_name = ied_element.get("name", "Unknown_IED")
        root_node = Node(name=parsed_ied_name, description="Offline IED from SCL")

        # Browse AccessPoints -> Server -> LDevice
        # Note: Structure is usually IED -> AccessPoint -> Server -> LDevice
        # But some might be simpler. We'll search for LDevice everywhere under IED.
        
        ld_elements = ied_element.findall(".//scl:LDevice", self.ns)
        if not ld_elements:
             ld_elements = ied_element.findall(".//LDevice")

        for ld in ld_elements:
            ld_inst = ld.get("inst")
            ld_name = f"{parsed_ied_name}{ld_inst}"
            ld_node = Node(name=ld_name, description="Logical Device")
            root_node.children.append(ld_node)

            # LNs
            ln_elements = ld.findall("scl:LN", self.ns) + ld.findall("scl:LN0", self.ns)
            if not ln_elements:
                ln_elements = ld.findall("LN") + ld.findall("LN0")

            for ln in ln_elements:
                prefix = ln.get("prefix", "")
                ln_class = ln.get("lnClass", "")
                inst = ln.get("inst", "")
                ln_class_or_inst = f"{prefix}{ln_class}{inst}"
                
                ln_node = Node(name=ln_class_or_inst, description=f"Logical Node ({ln_class})")
                ld_node.children.append(ln_node)
                
                # Get LN Type for expansion
                ln_type_id = ln.get("lnType")
                
                if ln_type_id:
                    # Build the path prefix for this LN: "LD_NAME/LN_NAME"
                    ln_path = f"{ld_name}/{ln_class_or_inst}"
                    
                    # Expand the LN Type to get DOs and DAs, passing ld_name
                    self._expand_ln_type_with_path(ln_node, ln_type_id, ln_path, ld_name)
                    
                # --- Advanced Features: DataSets, Reporting, GOOSE ---
                
                # 1. DataSets Branch
                dataset_elements = ln.findall("scl:DataSet", self.ns) + ln.findall("DataSet")
                if dataset_elements:
                    datasets_root = Node(name="DataSets", description="Container")
                    
                    for ds in dataset_elements:
                        ds_name = ds.get("name")
                        ds_node = Node(name=ds_name, description=f"Type=DataSet")
                        datasets_root.children.append(ds_node)
                        
                        # Parse FCDAs (Entries)
                        for fcda in ds.findall("scl:FCDA", self.ns) + ds.findall("FCDA"):
                            ld_inst = fcda.get("ldInst", "")
                            prefix = fcda.get("prefix", "")
                            ln_class = fcda.get("lnClass", "")
                            ln_inst = fcda.get("lnInst", "")
                            do_name = fcda.get("doName", "")
                            da_name = fcda.get("daName", "")
                            fc = fcda.get("fc", "")
                            
                            # Construct a readable name
                            entry_name = f"{prefix}{ln_class}{ln_inst}.{do_name}.{da_name} [{fc}]"
                            if ld_inst:
                                entry_name = f"{ld_inst}/{entry_name}"
                                
                            ds_entry_node = Node(name=entry_name, description="Type=FCDA")
                            ds_node.children.append(ds_entry_node)
                    
                    ln_node.children.append(datasets_root)

                # 2. Reports Branch
                report_elements = ln.findall("scl:ReportControl", self.ns) + ln.findall("ReportControl")
                if report_elements:
                    reports_root = Node(name="Reports", description="Container")
                    
                    for rpt in report_elements:
                        rpt_name = rpt.get("name")
                        rpt_id = rpt.get("rptID", "")
                        ds_ref = rpt.get("datSet", "")
                        buffered = rpt.get("buffered", "false")
                        
                        desc = f"RptID={rpt_id} DataSet={ds_ref} Buf={buffered} Type=Report"
                        rpt_node = Node(name=rpt_name, description=desc)
                        reports_root.children.append(rpt_node)
                    
                    ln_node.children.append(reports_root)

                # 3. GOOSE Branch
                goose_elements = ln.findall("scl:GSEControl", self.ns) + ln.findall("GSEControl")
                if goose_elements:
                    goose_root = Node(name="GOOSE", description="Container")
                    
                    for gse in goose_elements:
                        gse_name = gse.get("name")
                        app_id = gse.get("appID", "")
                        ds_ref = gse.get("datSet", "")
                        
                        desc = f"AppID={app_id} DataSet={ds_ref} Type=GOOSE"
                        gse_node = Node(name=gse_name, description=desc)
                        goose_root.children.append(gse_node)
                    
                    ln_node.children.append(goose_root)

        return root_node

    def _expand_ln_type_with_path(self, ln_node: Node, ln_type_id: str, path_prefix: str, ld_name: str = ""):
        """
        Recursively expand an LN Type into DOs and DAs.
        path_prefix is typically 'LD_NAME/LN_NAME' (e.g., 'GPS01ECB01/XCBR1')
        """
        # Find DataTypeTemplates (not DataModelDirectory!)
        templates_root = self.root.find("scl:DataTypeTemplates", self.ns)
        if not templates_root:
            templates_root = self.root.find("DataTypeTemplates")
        if not templates_root:
            return

        # Build template dictionaries
        lnode_types = {}
        for lnt in templates_root.findall("scl:LNodeType", self.ns) + templates_root.findall("LNodeType"):
            lid = lnt.get("id")
            if lid:
                lnode_types[lid] = lnt

        do_types = {}
        for dot in templates_root.findall("scl:DOType", self.ns) + templates_root.findall("DOType"):
            did = dot.get("id")
            if did:
                do_types[did] = dot

        da_types = {}
        for dat in templates_root.findall("scl:DAType", self.ns) + templates_root.findall("DAType"):
            daid = dat.get("id")
            if daid:
                da_types[daid] = dat

        templates = {**lnode_types, **do_types, **da_types}

        # Lookup LNType
        lntype_def = templates.get(ln_type_id)
        if not lntype_def:
            logger.warning(f"LNType {ln_type_id} not found in templates")
            return

        # Iterate DOs in LNType
        for do in lntype_def.findall("scl:DO", self.ns) + lntype_def.findall("DO"):
            do_name = do.get("name")
            do_type_id = do.get("type")

            do_node = Node(name=do_name, description="Data Object")
            ln_node.children.append(do_node)

            if do_type_id:
                # Build path for this DO
                do_path = f"{path_prefix}.{do_name}"
                # Expand recursively, passing LD name
                self._expand_do_type(do_node, do_type_id, templates, do_path, ld_name)

    def _expand_ln_type(self, ln_node: Node, ln_type_id: str):
        """Legacy wrapper for backward compatibility or direct calls."""
        # This method is now deprecated as it cannot provide the necessary ld_name for full addresses.
        # It will call the new method with an empty ld_name and a simplified path.
        self._expand_ln_type_with_path(ln_node, ln_type_id, ln_node.name, "")

    def _map_btype_to_signal_type(self, btype: str) -> SignalType:
        """Maps SCL bType to internal SignalType."""
        if btype == "BOOLEAN":
            return SignalType.DOUBLE_BINARY
        # Add more mappings as needed
        return SignalType.ANALOG # Default

    def _expand_do_type(self, parent_node: Node, do_type_id: str, templates: dict, path_prefix: str, ld_name: str = ""):
        """Recursively expand a DO Type into DAs, using path_prefix for full address."""
        dotype_def = templates.get(do_type_id)
        if not dotype_def:
            return
        
        for sdo_or_da in list(dotype_def):
            tag = sdo_or_da.tag.split('}')[-1]  # Strip namespace
            elem_name = sdo_or_da.get("name")
            
            if tag == "DA":  # Data Attribute - this is a signal
                fc = sdo_or_da.get("fc")
                btype = sdo_or_da.get("bType")
                sig_type = self._map_btype_to_signal_type(btype)
                
                # Build full address with LD prefix
                full_address = f"{ld_name}/{path_prefix}.{elem_name}" if ld_name else f"{path_prefix}.{elem_name}"
                
                signal = Signal(
                    name=elem_name,
                    address=full_address,
                    signal_type=sig_type,
                    description=f"FC:{fc} Type:{btype}"
                )
                parent_node.signals.append(signal)
                
            elif tag == "SDO":  # Sub Data Object
                sdo_type_id = sdo_or_da.get("type")
                sdo_node = Node(name=elem_name, description="Sub Data Object")
                parent_node.children.append(sdo_node)
                if sdo_type_id:
                    new_path = f"{path_prefix}.{elem_name}"
                    self._expand_do_type(sdo_node, sdo_type_id, templates, new_path, ld_name)

    def extract_ieds_info(self) -> List[Dict[str, str]]:
        """
        Parses the Communication section to find all IEDs and their IP addresses.
        Returns a list of dicts: {'name': 'IED1', 'ip': '1.2.3.4', 'port': '102'}
        """
        if self.root is None:
            return []

        ieds = []
        
        # Strategy 1: Communication Section (Best for IPs)
        communication = self.root.find("scl:Communication", self.ns)
        if not communication:
            communication = self.root.find("Communication")

        found_ied_names = set()

        if communication:
            # Scan SubNetworks
            for sub_net in communication.findall("scl:SubNetwork", self.ns) + communication.findall("SubNetwork"):
                for conn_ap in sub_net.findall("scl:ConnectedAP", self.ns) + sub_net.findall("ConnectedAP"):
                    ied_name = conn_ap.get("iedName")
                    if not ied_name: continue

                    address = conn_ap.find("scl:Address", self.ns)
                    if not address:
                        address = conn_ap.find("Address")
                    
                    ip = "127.0.0.1"
                    port = "102"
                    
                    if address:
                        for p in address.findall("scl:P", self.ns) + address.findall("P"):
                            ptype = p.get("type")
                            if ptype == "IP":
                                ip = p.text
                            elif ptype == "IP-SUBNET":
                                # Handle IP-SUBNET mask ?? 
                                pass

                    ieds.append({
                        "name": ied_name,
                        "ip": ip,
                        "port": port,
                        "ap": conn_ap.get("apName")
                    })
                    found_ied_names.add(ied_name)

        # Strategy 2: IED Section (Best if Communication missing or as fallback)
        # Check for IEDs that were NOT found in Communication section
        all_ied_elements = self.root.findall("scl:IED", self.ns) + self.root.findall("IED")
        for ied in all_ied_elements:
            name = ied.get("name")
            if name and name not in found_ied_names:
                # We don't know the IP if it's not in Communication, so default to localhost
                # User can edit it later
                ieds.append({
                    "name": name,
                    "ip": "127.0.0.1", 
                    "port": "102",
                    "ap": "Unknown"
                })
        
        return ieds
