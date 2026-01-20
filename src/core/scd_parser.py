import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
import os
import logging

from src.models.device_models import Node, Signal, SignalType, SignalQuality

logger = logging.getLogger(__name__)

class SCDParser:
    """
    Parses SCL/SCD/CID/ICD files to extract IEC 61850 structure.
    Mimics the logic from the reference 'IEC61850DiscoverIED'.
    """
    
    # Class-level cache for parsed trees: {file_path: (mtime, tree, root, ns)}
    _cache = {}

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None
        self.ns = {}
        self._parse()

    def _parse(self):
        if not os.path.exists(self.file_path):
            logger.error(f"SCD file not found: {self.file_path}")
            return
        
        try:
            mtime = os.path.getmtime(self.file_path)
            file_size = os.path.getsize(self.file_path)
            
            # Check cache
            if self.file_path in self._cache:
                cached_mtime, tree, root, ns = self._cache[self.file_path]
                if cached_mtime == mtime:
                    self.tree = tree
                    self.root = root
                    self.ns = ns
                    # logger.debug(f"Using cached SCD parse for {self.file_path}")
                    return

            # For large files (>10MB), log progress
            if file_size > 10 * 1024 * 1024:
                logger.info(f"Parsing large SCD file ({file_size / (1024*1024):.1f} MB)...")
            
            # Parse with iterparse for better memory handling on large files
            # But still build full tree for compatibility
            self.tree = ET.parse(self.file_path)
            self.root = self.tree.getroot()
            
            # Detect Namespace
            if '}' in self.root.tag:
                ns_uri = self.root.tag.split('}')[0].strip('{')
                self.ns = {'scl': ns_uri}
            else:
                self.ns = {}
            
            # Update cache
            self._cache[self.file_path] = (mtime, self.tree, self.root, self.ns)
            
            if file_size > 10 * 1024 * 1024:
                logger.info(f"SCD parsing complete")
                
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
        ied_desc = ied_element.get("desc", "Offline IED from SCL")
        root_node = Node(name=parsed_ied_name, description=ied_desc)

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

            ln0_element = None
            for ln in ln_elements:
                if ln.tag.split('}')[-1] == "LN0":
                    ln0_element = ln
                    break

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
                        buf_tm = rpt.get("bufTm", "")
                        intg_pd = rpt.get("intgPd", "")
                        trg_ops = self._attributes_to_kv(rpt.find("scl:TrgOps", self.ns) or rpt.find("TrgOps"))
                        opt_flds = self._attributes_to_kv(rpt.find("scl:OptFields", self.ns) or rpt.find("OptFields"))
                        
                        desc = f"RptID={rpt_id} DataSet={ds_ref} Buf={buffered} Type=Report"
                        rpt_node = Node(name=rpt_name, description=desc)

                        # Details
                        self._add_detail_leaf(rpt_node, "RptID", rpt_id)
                        self._add_detail_leaf(rpt_node, "DataSet", ds_ref)
                        self._add_detail_leaf(rpt_node, "Buffered", buffered)
                        self._add_detail_leaf(rpt_node, "BufTm", buf_tm)
                        self._add_detail_leaf(rpt_node, "IntgPd", intg_pd)
                        if trg_ops:
                            self._add_detail_leaf(rpt_node, "TrgOps", trg_ops)
                        if opt_flds:
                            self._add_detail_leaf(rpt_node, "OptFields", opt_flds)

                        # DataSet Entries
                        self._append_dataset_entries(rpt_node, ln, ds_ref, ln0_element)

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
                        conf_rev = gse.get("confRev", "")
                        go_id = gse.get("goID", "")
                        fixed_offs = gse.get("fixedOffs", "")
                        
                        desc = f"AppID={app_id} DataSet={ds_ref} Type=GOOSE"
                        gse_node = Node(name=gse_name, description=desc)

                        # Details
                        self._add_detail_leaf(gse_node, "AppID", app_id)
                        self._add_detail_leaf(gse_node, "DataSet", ds_ref)
                        self._add_detail_leaf(gse_node, "ConfRev", conf_rev)
                        self._add_detail_leaf(gse_node, "GoID", go_id)
                        self._add_detail_leaf(gse_node, "FixedOffs", fixed_offs)

                        # DataSet Entries
                        self._append_dataset_entries(gse_node, ln, ds_ref, ln0_element)

                        goose_root.children.append(gse_node)
                    
                    ln_node.children.append(goose_root)

        return root_node

    def _add_detail_leaf(self, parent_node: Node, label: str, value: Any) -> None:
        """Add a detail leaf node with optional value."""
        if value is None or value == "":
            parent_node.children.append(Node(name=label, description="Detail"))
        else:
            parent_node.children.append(Node(name=f"{label}={value}", description="Detail"))

    def _attributes_to_kv(self, element) -> str:
        """Convert XML element attributes to key=value string."""
        if element is None:
            return ""
        attrs = []
        for k, v in element.attrib.items():
            attrs.append(f"{k}={v}")
        return " ".join(attrs)

    def _append_dataset_entries(self, parent_node: Node, ln_element, dataset_name: str, ln0_element=None) -> None:
        """Append DataSet FCDA entries as leaf nodes."""
        if not dataset_name:
            return

        entries = self._get_dataset_entries(ln_element, dataset_name)
        if not entries and ln0_element is not None and ln0_element is not ln_element:
            entries = self._get_dataset_entries(ln0_element, dataset_name)

        if not entries:
            return

        entries_root = Node(name="DataSetEntries", description="FCDA members")
        for entry in entries:
            ln = entry.get('ln', '')
            do = entry.get('do', '')
            da = entry.get('da', '')
            fc = entry.get('fc', '')

            name_parts = [ln, do, da]
            name = ".".join([p for p in name_parts if p])
            if fc:
                name = f"{name} [{fc}]"
            entries_root.children.append(Node(name=name, description="FCDA"))

        parent_node.children.append(entries_root)

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
                
        enum_types = {}
        for et in templates_root.findall("scl:EnumType", self.ns) + templates_root.findall("EnumType"):
            eid = et.get("id")
            if eid:
                enums = {}
                for enum_val in et.findall("scl:EnumVal", self.ns) + et.findall("EnumVal"):
                     ord_val = enum_val.get("ord")
                     text_val = enum_val.text
                     if ord_val is not None:
                         try:
                             enums[int(ord_val)] = text_val
                         except: pass
                enum_types[eid] = enums
                logger.debug(f"Parsed EnumType '{eid}' with {len(enums)} values: {enums}")

        logger.debug(f"Total EnumTypes found: {len(enum_types)}")
        templates = {**lnode_types, **do_types, **da_types, **enum_types} # Include enums in templates for easy lookup if needed (though we separate them mostly)
        # Store enums separately or mix them? 
        # _expand_do_type receives `templates`. Let's assume we can lookup enums by ID in `templates`.
        # Since ids are unique across types usually, this should be fine.

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
        if btype == "Timestamp":
            return SignalType.TIMESTAMP
        if btype in ["Enum", "Dbpos"]:
             return SignalType.BINARY
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
                
                if elem_name.lower().endswith(".t") or elem_name == "T":
                    sig_type = SignalType.TIMESTAMP

                # Control Check
                access = "RO"
                if fc == "CO" or elem_name == "ctVal":
                     sig_type = SignalType.COMMAND
                     access = "RW"

                # Build full address with LD prefix
                # Fix: Check if path_prefix already starts with ld_name to avoid duplication
                # Although path_prefix usually is LN.DO...
                # The user reported "GPS...CB1/GPS...CB1/XCBR1.Beh.stVal"
                # This suggests ld_name was added, and maybe path_prefix also contained it?
                # Or maybe ld_name itself contained the slash?
                
                # Standard check:
                if ld_name and not path_prefix.startswith(ld_name + "/"):
                    full_address = f"{ld_name}/{path_prefix}.{elem_name}"
                else:
                    # If path_prefix already has the LD (unlikely but safe)
                    full_address = f"{path_prefix}.{elem_name}"
                
                signal = Signal(
                    name=elem_name,
                    address=full_address,
                    signal_type=sig_type,
                    description=f"FC:{fc} Type:{btype}",
                    access=access,
                    fc=fc
                )
                
                # Check for Enum Mapping
                type_id = sdo_or_da.get("type")
                logger.debug(f"DA '{elem_name}': bType={btype}, fc={fc}, type={type_id}")
                
                if type_id:
                     # Check if it's an EnumType (dict)
                     # In our parsing above, enum_types entries are Dicts, while others are xml Elements.
                     # We stored enums in templates, but they're dicts while LNodeTypes/DOTypes/DATypes are Elements
                     if type_id in templates:
                         possible_enum = templates[type_id]
                         if isinstance(possible_enum, dict):
                             logger.debug(f"✓ Enum mapping for {full_address} ({elem_name}): {possible_enum}")
                             signal.enum_map = possible_enum
                             if sig_type == SignalType.ANALOG:
                                 # Optionally convert to State type for enum values
                                 pass
                         else:
                             # It's a DAType or other complex type, not an enum
                             logger.debug(f"  Type '{type_id}' is not an EnumType (it's {type(possible_enum).__name__})")
                     else:
                         logger.warning(f"  Type '{type_id}' not found in templates for DA '{elem_name}'")
                
                parent_node.signals.append(signal)
                
            elif tag == "SDO":  # Sub Data Object
                sdo_type_id = sdo_or_da.get("type")
                sdo_node = Node(name=elem_name, description="Sub Data Object")
                parent_node.children.append(sdo_node)
                if sdo_type_id:
                    new_path = f"{path_prefix}.{elem_name}"
                    self._expand_do_type(sdo_node, sdo_type_id, templates, new_path, ld_name)

    def extract_ieds_info(self) -> List[Dict[str, Any]]:
        """
        Parses the Communication section to find all IEDs and all their IP addresses.
        Returns a list of dicts: 
        {
            'name': 'IED1', 
            'ips': [
                {'ip': '1.2.3.4', 'ap': 'S1', 'subnetwork': 'WA1', 'desc': 'Station Bus'},
                {'ip': '10.0.0.1', 'ap': 'S2', 'subnetwork': 'WA2', 'desc': 'Process Bus'}
            ]
        }
        """
        if self.root is None:
            return []

        ieds_map = {} # name -> {name: str, description: str, ips: []}
        
        # Pre-scan IED descriptions
        ied_descs = {}
        all_ied_elements = self.root.findall(".//scl:IED", self.ns) + self.root.findall(".//IED")
        for ied in all_ied_elements:
            name = ied.get("name")
            if name:
                ied_descs[name] = ied.get("desc", "")

        # Strategy 1: Communication Section
        communication = self.root.find("scl:Communication", self.ns)
        if not communication:
            communication = self.root.find("Communication")

        if communication:
            # Scan SubNetworks
            for sub_net in communication.findall("scl:SubNetwork", self.ns) + communication.findall("SubNetwork"):
                subnet_name = sub_net.get("name", "Unknown")
                subnet_desc = sub_net.get("desc", "")
                
                for conn_ap in sub_net.findall("scl:ConnectedAP", self.ns) + sub_net.findall("ConnectedAP"):
                    ied_name = conn_ap.get("iedName")
                    if not ied_name: continue
                    
                    ap_name = conn_ap.get("apName", "")
                    
                    # Get Address
                    address = conn_ap.find("scl:Address", self.ns)
                    if not address:
                        address = conn_ap.find("Address")
                    
                    ip = None
                    gateway = None
                    subnet_mask = None
                    port = None
                    vlan = None
                    vlan_priority = None
                    mac_address = None
                    
                    if address:
                        for p in address.findall("scl:P", self.ns) + address.findall("P"):
                            ptype = p.get("type")
                            ptype_norm = ptype.lower() if ptype else ""
                            if ptype == "IP":
                                ip = p.text
                            elif ptype == "IP-SUBNET":
                                subnet_mask = p.text
                            elif ptype == "IP-GATEWAY":
                                gateway = p.text
                            elif ptype == "VLAN-ID":
                                vlan = p.text
                            elif ptype == "VLAN-PRIORITY":
                                vlan_priority = p.text
                            elif ptype == "MAC-Address":
                                mac_address = p.text
                            elif "port" in ptype_norm and p.text:
                                try:
                                    port = int(p.text)
                                except Exception:
                                    pass

                    if ip:
                        if ied_name not in ieds_map:
                            ieds_map[ied_name] = {
                                'name': ied_name, 
                                'description': ied_descs.get(ied_name, ""),
                                'ips': []
                            }
                        
                        ieds_map[ied_name]['ips'].append({
                            'ip': ip,
                            'ap': ap_name,
                            'subnetwork': subnet_name,
                            'mask': subnet_mask,
                            'gateway': gateway,
                            'port': port or 102,
                            'vlan': vlan,
                            'vlan_priority': vlan_priority,
                            'mac_address': mac_address
                        })

        # Strategy 2: IED Section (Fallback for IEDs with no Communication info)
        for name, desc in ied_descs.items():
            if name not in ieds_map:
                # Default to localhost if not found in Communication
                ieds_map[name] = {
                    'name': name, 
                    'description': desc,
                    'ips': [{
                        'ip': '127.0.0.1', 
                        'ap': 'Default', 
                        'subnetwork': 'Local',
                        'mask': '255.255.255.0',
                        'gateway': '0.0.0.0'
                    }]
                }
        
        return list(ieds_map.values())

    def extract_goose_map(self) -> List[Dict]:
        """
        Extracts detailed GOOSE configuration map.
        Returns list of dicts suitable for CSV export.
        """
        goose_entries = []
        
        if self.root is None:
            return []

        # Find all IEDs
        ied_elements = self.root.findall("scl:IED", self.ns) + self.root.findall("IED")
        
        for ied in ied_elements:
            ied_name = ied.get("name")
            
            # Search all Access Points (simplified: search all LDevices)
            ap_elements = ied.findall(".//scl:AccessPoint", self.ns) + ied.findall(".//AccessPoint")
            if not ap_elements:
                # Fallback: search LDevices directly under IED if structure is flat
                ld_elements = ied.findall("scl:LDevice", self.ns) + ied.findall("LDevice")
                if ld_elements:
                    # Mock AP wrapper
                    ap_elements = [{'name': 'Default', 'lds': ld_elements}]
                else:
                    continue
            else:
                 # Real APs
                 pass # We iterate below

            for ap in ap_elements:
                if isinstance(ap, dict):
                     ap_name = ap['name']
                     lds = ap['lds']
                else:
                     ap_name = ap.get("name")
                     lds = ap.findall("scl:LDevice", self.ns) + ap.findall("LDevice")

                for ld in lds:
                    ld_inst = ld.get("inst")
                    
                    ln0 = ld.find("scl:LN0", self.ns)
                    if not ln0:
                        ln0 = ld.find("LN0")
                    
                    if not ln0: continue
                    
                    # Find GSE Controls
                    gse_controls = ln0.findall("scl:GSEControl", self.ns) + ln0.findall("GSEControl")
                    
                    for gse in gse_controls:
                        gse_name = gse.get("name")
                        app_id = gse.get("appID")
                        dat_set = gse.get("datSet")
                        conf_rev = gse.get("confRev")
                        
                        # Find GSE element in Communication section to get MAC, VLAN etc
                        # This requires cross-referencing Communication section which is tricky
                        # We need <GSE ldInst="..." cbName="...">
                        comm_info = self._find_gse_comm_info(ied_name, ap_name, ld_inst, gse_name)
                        
                        # Find DataSet content
                        dataset_entries = self._get_dataset_entries(ln0, dat_set)
                        
                        for ds_entry in dataset_entries:
                            entry = {
                                "Source IED Name": ied_name,
                                "Source AP": ap_name,
                                "Source LDevice": ld_inst,
                                "Source IP Address": comm_info.get('ip', ''), # Optional for GOOSE
                                "Source Subnet": comm_info.get('subnetwork', ''),
                                "Source MAC Address": comm_info.get('mac', ''),
                                "Source VLAN-ID": comm_info.get('vlan', ''),
                                "Source APPID": app_id,
                                "Source MinTime": comm_info.get('minTime', ''),
                                "Source MaxTime": comm_info.get('maxTime', ''),
                                "Source DataSet": dat_set,
                                "Source ConfRev": conf_rev,
                                "Source ControlBlock": gse_name,
                                "Source LogicalNode": ds_entry.get('ln', ''),
                                "Source DataAttribute": ds_entry.get('da', ""),
                                "Source Tag": f"{ied_name}{ld_inst}/{ds_entry.get('ln','')}.{ds_entry.get('do','')}.{ds_entry.get('da','')}"
                            }
                            goose_entries.append(entry)

        return goose_entries

    def _find_gse_comm_info(self, ied_name, ap_name, ld_inst, cb_name) -> Dict:
        """Helper to find GSE address info in Communication section."""
        info = {'mac': '', 'vlan': '', 'priority': '', 'appid': '', 'subnetwork': '', 'minTime': '', 'maxTime': ''}
        
        if self.root is None: return info
        comm = self.root.find("scl:Communication", self.ns)
        if not comm: comm = self.root.find("Communication")
        if not comm: return info

        # Locate ConnectedAP
        # Search path: SubNetwork -> ConnectedAP(iedName, apName) -> GSE(ldInst, cbName)
        for subnet in comm.findall("scl:SubNetwork", self.ns) + comm.findall("SubNetwork"):
            subnet_name = subnet.get("name")
            
            for conn_ap in subnet.findall("scl:ConnectedAP", self.ns) + subnet.findall("ConnectedAP"):
                if conn_ap.get("iedName") == ied_name and conn_ap.get("apName") == ap_name:
                    
                    # Find GSE
                    for gse in conn_ap.findall("scl:GSE", self.ns) + conn_ap.findall("GSE"):
                         if gse.get("ldInst") == ld_inst and gse.get("cbName") == cb_name:
                             info['subnetwork'] = subnet_name
                             
                             address = gse.find("scl:Address", self.ns)
                             if not address: address = gse.find("Address")
                             
                             if address:
                                 for p in address.findall("scl:P", self.ns) + address.findall("P"):
                                     ptype = p.get("type")
                                     if ptype == "MAC-Address":
                                         info['mac'] = p.text
                                     elif ptype == "VLAN-ID":
                                         info['vlan'] = p.text
                                     elif ptype == "APPID":
                                         info['appid'] = p.text
                                     elif ptype == "VLAN-PRIORITY":
                                         info['priority'] = p.text
                                         
                             min_time = gse.find("scl:MinTime", self.ns)
                             if min_time is not None: info['minTime'] = min_time.text
                             
                             max_time = gse.find("scl:MaxTime", self.ns)
                             if max_time is not None: info['maxTime'] = max_time.text
                             
                             return info
        return info

    def _get_dataset_entries(self, ln_node, dataset_name) -> List[Dict]:
        """Parses FCDAs from a DataSet."""
        entries = []
        ds = ln_node.find(f"scl:DataSet[@name='{dataset_name}']", self.ns)
        if not ds:
             ds = ln_node.find(f"DataSet[@name='{dataset_name}']")
        
        if ds:
            for fcda in ds.findall("scl:FCDA", self.ns) + ds.findall("FCDA"):
                entries.append({
                    'ln': f"{fcda.get('prefix','')}{fcda.get('lnClass')}{fcda.get('lnInst','')}",
                    'do': fcda.get('doName'),
                    'da': fcda.get('daName'),
                    'fc': fcda.get('fc')
                })
        return entries
