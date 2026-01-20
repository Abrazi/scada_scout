import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
import os
import logging
import re

from src.models.device_models import Node, Signal, SignalType, SignalQuality

logger = logging.getLogger(__name__)

class SCDParser:
    """
    Parses SCL/SCD/CID/ICD files to extract IEC 61850 structure.
    Mimics the logic from the reference 'IEC61850DiscoverIED'.
    """
    
    # Class-level cache for parsed trees: {file_path: (mtime, tree, root, ns)}
    _cache = {}
    # Class-level cache for parsed structures: {(file_path, mtime, ied_name): Node}
    _structure_cache = {}

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None
        self.ns = {}
        self.mtime = None
        self._templates = None  # Cache for parsed data type templates
        self._parse()

    def _normalize_ptype(self, ptype: Optional[str]) -> str:
        if not ptype:
            return ""
        return re.sub(r"[^a-z0-9]", "", ptype.strip().lower())

    def _parse_address_params(self, address) -> Dict[str, Any]:
        params = {
            "ip": None,
            "subnet_mask": None,
            "gateway": None,
            "port": None,
            "vlan": None,
            "vlan_priority": None,
            "mac_address": None,
            "appid": None
        }
        if not address:
            return params

        for p in address.findall("scl:P", self.ns) + address.findall("P"):
            ptype = p.get("type")
            ptype_norm = self._normalize_ptype(ptype)
            text = (p.text or "").strip()
            if text == "":
                continue

            if ptype_norm in {"ip", "ipaddress", "ipaddr", "ipv4", "ipv4address"}:
                if params["ip"] is None:
                    params["ip"] = text
            elif ptype_norm in {"ipsubnet", "ipsubnetmask", "subnet", "subnetmask", "netmask"}:
                if params["subnet_mask"] is None:
                    params["subnet_mask"] = text
            elif ptype_norm in {"ipgateway", "gateway", "defaultgateway", "defaultgw"}:
                if params["gateway"] is None:
                    params["gateway"] = text
            elif "vlan" in ptype_norm and ("prio" in ptype_norm or "priority" in ptype_norm):
                if params["vlan_priority"] is None:
                    params["vlan_priority"] = text
            elif "vlan" in ptype_norm and ("id" in ptype_norm or ptype_norm == "vlan"):
                if params["vlan"] is None:
                    params["vlan"] = text
            elif ptype_norm in {"mac", "macaddress", "macaddr", "hwaddr", "hwaddress"}:
                if params["mac_address"] is None:
                    params["mac_address"] = text
            elif "port" in ptype_norm:
                if params["port"] is None:
                    try:
                        params["port"] = int(text)
                    except Exception:
                        pass
            elif ptype_norm in {"appid", "app"}:
                if params["appid"] is None:
                    params["appid"] = text

        return params

    def _find_vlan_info_in_connectedap(self, conn_ap) -> Dict[str, Any]:
        info = {"vlan": None, "vlan_priority": None, "mac_address": None, "appid": None}
        if conn_ap is None:
            return info

        comm_tags = ["GSE", "SMV", "SampledValue", "SampledValues", "SV"]
        for tag in comm_tags:
            for elem in conn_ap.findall(f"scl:{tag}", self.ns) + conn_ap.findall(tag):
                address = elem.find("scl:Address", self.ns)
                if not address:
                    address = elem.find("Address")
                params = self._parse_address_params(address)
                for key in ("vlan", "vlan_priority", "mac_address", "appid"):
                    if info[key] is None and params.get(key) is not None:
                        info[key] = params.get(key)
                if all(info[k] is not None for k in ("vlan", "vlan_priority", "mac_address")):
                    return info
        return info

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
                    self.mtime = cached_mtime
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
            self.mtime = mtime
            self._cache[self.file_path] = (mtime, self.tree, self.root, self.ns)
            self._templates = None # Reset templates cache on new parse
            
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

        # Check structure cache first
        cache_key = (self.file_path, self.mtime, ied_name if ied_name else "__first__")
        if cache_key in self._structure_cache:
            logger.debug(f"Using cached structure for {ied_name or 'first IED'}")
            return self._structure_cache[cache_key]

        # Find IED element
        ied_element = None
        if ied_name:
            ied_element = self.root.find(f".//scl:IED[@name='{ied_name}']", self.ns)
            if ied_element is None:
                ied_element = self.root.find(f".//IED[@name='{ied_name}']")
        else:
            # Prefer the first IED that actually contains LDevices
            ied_candidates = self.root.findall(".//scl:IED", self.ns) + self.root.findall(".//IED")
            for candidate in ied_candidates:
                if candidate.findall(".//scl:LDevice", self.ns) or candidate.findall(".//LDevice"):
                    ied_element = candidate
                    break
            if ied_element is None and ied_candidates:
                ied_element = ied_candidates[0]

        if ied_element is None:
            result = Node(name="IED_Not_Found")
            self._structure_cache[cache_key] = result
            return result

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

        # Cache the completed structure before returning
        self._structure_cache[cache_key] = root_node
        logger.debug(f"Cached structure for {parsed_ied_name}")
        
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
            ld_inst = entry.get('ld_inst', '')
            ln = entry.get('ln', '')
            do = entry.get('do', '')
            da = entry.get('da', '')
            bda = entry.get('bda', '')
            fc = entry.get('fc', '')

            name_parts = [ln, do]
            if da:
                name_parts.append(da)
                if bda:
                    name_parts.append(bda)
            elif bda:
                name_parts.append(bda)

            name = ".".join([p for p in name_parts if p])
            if ld_inst:
                name = f"{ld_inst}/{name}" if name else ld_inst
            if fc:
                name = f"{name} [{fc}]"
            entries_root.children.append(Node(name=name, description="FCDA"))

        parent_node.children.append(entries_root)


    def _get_templates(self):
        """Lazy load and cache DataTypeTemplates."""
        if self._templates is not None:
            return self._templates
            
        if self.root is None:
            return {}

        # Find DataTypeTemplates (not DataModelDirectory!)
        templates_root = self.root.find("scl:DataTypeTemplates", self.ns)
        if not templates_root:
            templates_root = self.root.find("DataTypeTemplates")
        if not templates_root:
            self._templates = {}
            return {}

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
        
        # Combine all into one lookup (IDs should be unique across types mostly, or context aware)
        # Storing combined for simplicity as per original design
        self._templates = {**lnode_types, **do_types, **da_types, **enum_types}
        logger.debug(f"Cached {len(self._templates)} templates")
        return self._templates

    def _expand_ln_type_with_path(self, ln_node: Node, ln_type_id: str, path_prefix: str, ld_name: str = ""):
        """
        Recursively expand an LN Type into DOs and DAs.
        path_prefix is typically 'LD_NAME/LN_NAME' (e.g., 'GPS01ECB01/XCBR1')
        """
        templates = self._get_templates()

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

    def _build_full_address(self, path_prefix: str, elem_name: str, ld_name: str = "") -> str:
        """Builds a full address with LD prefix if needed."""
        if ld_name and not path_prefix.startswith(ld_name + "/"):
            return f"{ld_name}/{path_prefix}.{elem_name}"
        return f"{path_prefix}.{elem_name}"

    def _is_da_type(self, type_def) -> bool:
        """Check if a template definition is a DAType element."""
        return hasattr(type_def, "tag") and type_def.tag.split('}')[-1] == "DAType"

    def _expand_da_type(self, parent_node: Node, da_type_id: str, templates: dict, path_prefix: str, ld_name: str = "", parent_fc: str = ""):
        """Recursively expand DAType (BDA elements) into signals/children."""
        da_def = templates.get(da_type_id)
        if not da_def or not self._is_da_type(da_def):
            return

        for bda in da_def.findall("scl:BDA", self.ns) + da_def.findall("BDA"):
            bda_name = bda.get("name")
            if not bda_name:
                continue

            bda_btype = bda.get("bType")
            bda_type_id = bda.get("type")
            bda_fc = bda.get("fc") or parent_fc

            type_def = templates.get(bda_type_id) if bda_type_id else None
            is_struct = bda_btype == "Struct" or self._is_da_type(type_def)

            if is_struct:
                sub_node = Node(name=bda_name, description="Data Attribute")
                parent_node.children.append(sub_node)
                new_path = f"{path_prefix}.{bda_name}"
                self._expand_da_type(sub_node, bda_type_id, templates, new_path, ld_name, bda_fc)

                if not sub_node.children and not sub_node.signals:
                    parent_node.children.remove(sub_node)
                    full_address = self._build_full_address(path_prefix, bda_name, ld_name)
                    sig_type = self._map_btype_to_signal_type(bda_btype)
                    access = "RW" if bda_fc == "CO" or bda_name == "ctlVal" else "RO"
                    parent_node.signals.append(Signal(
                        name=bda_name,
                        address=full_address,
                        signal_type=sig_type,
                        description=f"FC:{bda_fc} Type:{bda_btype}",
                        access=access,
                        fc=bda_fc
                    ))
                continue

            full_address = self._build_full_address(path_prefix, bda_name, ld_name)
            sig_type = self._map_btype_to_signal_type(bda_btype)
            access = "RW" if bda_fc == "CO" or bda_name == "ctlVal" else "RO"
            signal = Signal(
                name=bda_name,
                address=full_address,
                signal_type=sig_type,
                description=f"FC:{bda_fc} Type:{bda_btype}",
                access=access,
                fc=bda_fc
            )

            # Enum mapping for BDA
            if bda_type_id and bda_type_id in templates:
                possible_enum = templates[bda_type_id]
                if isinstance(possible_enum, dict):
                    signal.enum_map = possible_enum

            parent_node.signals.append(signal)

    def _expand_do_type(self, parent_node: Node, do_type_id: str, templates: dict, path_prefix: str, ld_name: str = ""):
        """Recursively expand a DO Type into DAs, using path_prefix for full address."""
        dotype_def = templates.get(do_type_id)
        if not dotype_def:
            return
        
        for sdo_or_da in list(dotype_def):
            tag = sdo_or_da.tag.split('}')[-1]  # Strip namespace
            elem_name = sdo_or_da.get("name")
            
            if tag == "DA":  # Data Attribute
                fc = sdo_or_da.get("fc")
                btype = sdo_or_da.get("bType")
                type_id = sdo_or_da.get("type")

                type_def = templates.get(type_id) if type_id else None
                is_struct = btype == "Struct" or self._is_da_type(type_def)

                if is_struct:
                    da_node = Node(name=elem_name, description="Data Attribute")
                    parent_node.children.append(da_node)
                    new_path = f"{path_prefix}.{elem_name}"
                    self._expand_da_type(da_node, type_id, templates, new_path, ld_name, fc)

                    if not da_node.children and not da_node.signals:
                        parent_node.children.remove(da_node)
                        full_address = self._build_full_address(path_prefix, elem_name, ld_name)
                        sig_type = self._map_btype_to_signal_type(btype)
                        access = "RW" if fc == "CO" or elem_name == "ctVal" else "RO"
                        parent_node.signals.append(Signal(
                            name=elem_name,
                            address=full_address,
                            signal_type=sig_type,
                            description=f"FC:{fc} Type:{btype}",
                            access=access,
                            fc=fc
                        ))
                    continue

                sig_type = self._map_btype_to_signal_type(btype)

                if elem_name and (elem_name.lower().endswith(".t") or elem_name == "T"):
                    sig_type = SignalType.TIMESTAMP

                # Control Check
                access = "RO"
                if fc == "CO" or elem_name == "ctVal":
                    sig_type = SignalType.COMMAND
                    access = "RW"

                full_address = self._build_full_address(path_prefix, elem_name, ld_name)
                signal = Signal(
                    name=elem_name,
                    address=full_address,
                    signal_type=sig_type,
                    description=f"FC:{fc} Type:{btype}",
                    access=access,
                    fc=fc
                )

                # Check for Enum Mapping
                logger.debug(f"DA '{elem_name}': bType={btype}, fc={fc}, type={type_id}")

                if type_id:
                    # Check if it's an EnumType (dict)
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
                        params = self._parse_address_params(address)
                        ip = params.get("ip")
                        gateway = params.get("gateway")
                        subnet_mask = params.get("subnet_mask")
                        port = params.get("port")
                        vlan = params.get("vlan")
                        vlan_priority = params.get("vlan_priority")
                        mac_address = params.get("mac_address")

                    if vlan is None or vlan_priority is None or mac_address is None:
                        vlan_info = self._find_vlan_info_in_connectedap(conn_ap)
                        if vlan is None and vlan_info.get("vlan") is not None:
                            vlan = vlan_info.get("vlan")
                        if vlan_priority is None and vlan_info.get("vlan_priority") is not None:
                            vlan_priority = vlan_info.get("vlan_priority")
                        if mac_address is None and vlan_info.get("mac_address") is not None:
                            mac_address = vlan_info.get("mac_address")

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

        def _ln_name(ln_element) -> str:
            if ln_element is None:
                return ""
            prefix = ln_element.get("prefix", "")
            ln_class = ln_element.get("lnClass", "")
            inst = ln_element.get("inst", "")
            return f"{prefix}{ln_class}{inst}"

        def _build_tag(ied: str, ld_inst: str, ln: str, do: str, data_attr: str) -> str:
            tag_ld = f"{ied}{ld_inst}" if ld_inst else ied
            tag_parts = [ln, do, data_attr]
            tag_parts = [p for p in tag_parts if p]
            tag_ref = ".".join(tag_parts)
            return f"{tag_ld}/{tag_ref}" if tag_ref else tag_ld

        def _data_attr(da: str, bda: str) -> str:
            if da and bda:
                return f"{da}.{bda}"
            if da:
                return da
            return bda

        def _find_ied_comm_info(ied_name: str, ap_name: str) -> Dict[str, Any]:
            info = {'ip': '', 'subnetwork': '', 'mac': ''}
            if self.root is None:
                return info
            comm = self.root.find("scl:Communication", self.ns)
            if not comm:
                comm = self.root.find("Communication")
            if not comm:
                return info
            for subnet in comm.findall("scl:SubNetwork", self.ns) + comm.findall("SubNetwork"):
                subnet_name = subnet.get("name")
                for conn_ap in subnet.findall("scl:ConnectedAP", self.ns) + subnet.findall("ConnectedAP"):
                    if conn_ap.get("iedName") == ied_name and conn_ap.get("apName") == ap_name:
                        info['subnetwork'] = subnet_name
                        address = conn_ap.find("scl:Address", self.ns)
                        if not address:
                            address = conn_ap.find("Address")
                        if address:
                            params = self._parse_address_params(address)
                            if params.get("ip") is not None:
                                info['ip'] = params.get("ip")
                            if params.get("mac_address") is not None:
                                info['mac'] = params.get("mac_address")
                        return info
            return info

        # Find all IEDs
        ied_elements = self.root.findall("scl:IED", self.ns) + self.root.findall("IED")

        # Build publisher map from GSEControl
        publisher_map: Dict[tuple, Dict[str, Any]] = {}
        publisher_dataset_entries: Dict[tuple, List[Dict[str, Any]]] = {}
        
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
                    lds = ap.findall(".//scl:LDevice", self.ns) + ap.findall(".//LDevice")

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
                        go_id = gse.get("goID")
                        fixed_offs = gse.get("fixedOffs")
                        
                        # Find GSE element in Communication section to get MAC, VLAN etc
                        # This requires cross-referencing Communication section which is tricky
                        # We need <GSE ldInst="..." cbName="...">
                        comm_info = self._find_gse_comm_info(ied_name, ap_name, ld_inst, gse_name)
                        
                        # Find DataSet content
                        dataset_entries = self._get_dataset_entries(ln0, dat_set)
                        pub_key = (ied_name, ld_inst, gse_name)
                        publisher_map[pub_key] = {
                            "Source IED Name": ied_name,
                            "Source AP": ap_name,
                            "Source LDevice": ld_inst,
                            "Source IP Address": comm_info.get('ip', ''),
                            "Source Subnet": comm_info.get('subnetwork', ''),
                            "Source MAC Address": comm_info.get('mac', ''),
                            "Source VLAN-ID": comm_info.get('vlan', ''),
                            "Source VLAN Priority": comm_info.get('priority', ''),
                            "Source APPID": comm_info.get('appid') or app_id,
                            "Source MinTime": comm_info.get('minTime', ''),
                            "Source MaxTime": comm_info.get('maxTime', ''),
                            "Source DataSet": dat_set,
                            "DataSet Size": len(dataset_entries) if dataset_entries else 0,
                            "Source ConfRev": conf_rev,
                            "Source ControlBlock": gse_name,
                            "Source GoID": go_id,
                            "Source FixedOffs": fixed_offs
                        }
                        publisher_dataset_entries[pub_key] = dataset_entries or []
                        
                        for ds_entry in dataset_entries:
                            source_ld_inst = ds_entry.get('ld_inst') or ld_inst or ""
                            data_attr = _data_attr(ds_entry.get('da', ''), ds_entry.get('bda', ''))
                            tag = _build_tag(ied_name, source_ld_inst, ds_entry.get('ln', ''), ds_entry.get('do', ''), data_attr)
                            entry = {
                                "Mapping Type": "Publisher",
                                "Source IED Name": ied_name,
                                "Source AP": ap_name,
                                "Source LDevice": source_ld_inst,
                                "Source IP Address": comm_info.get('ip', ''),
                                "Source Subnet": comm_info.get('subnetwork', ''),
                                "Source MAC Address": comm_info.get('mac', ''),
                                "Source VLAN-ID": comm_info.get('vlan', ''),
                                "Source VLAN Priority": comm_info.get('priority', ''),
                                "Source APPID": comm_info.get('appid') or app_id,
                                "Source MinTime": comm_info.get('minTime', ''),
                                "Source MaxTime": comm_info.get('maxTime', ''),
                                "Source DataSet": dat_set,
                                "DataSet Size": len(dataset_entries) if dataset_entries else 0,
                                "Source ConfRev": conf_rev,
                                "Source ControlBlock": gse_name,
                                "Source GoID": go_id,
                                "Source FixedOffs": fixed_offs,
                                "Source LogicalNode": ds_entry.get('ln', ''),
                                "Source DataAttribute": data_attr,
                                "Source Tag": tag
                            }
                            goose_entries.append(entry)

        # Build subscriber rows from ExtRef (GOOSE subscriptions)
        subscription_entries = []
        for ied in ied_elements:
            ied_name = ied.get("name")
            ap_elements = ied.findall(".//scl:AccessPoint", self.ns) + ied.findall(".//AccessPoint")
            if not ap_elements:
                ld_elements = ied.findall("scl:LDevice", self.ns) + ied.findall("LDevice")
                if ld_elements:
                    ap_elements = [{'name': 'Default', 'lds': ld_elements}]
                else:
                    continue

            for ap in ap_elements:
                if isinstance(ap, dict):
                    ap_name = ap['name']
                    lds = ap['lds']
                else:
                    ap_name = ap.get("name")
                    lds = ap.findall(".//scl:LDevice", self.ns) + ap.findall(".//LDevice")

                dest_comm = _find_ied_comm_info(ied_name, ap_name)

                for ld in lds:
                    ld_inst = ld.get("inst")
                    ln_elements = ld.findall("scl:LN", self.ns) + ld.findall("scl:LN0", self.ns)
                    if not ln_elements:
                        ln_elements = ld.findall("LN") + ld.findall("LN0")

                    for ln in ln_elements:
                        dest_ln = _ln_name(ln)
                        inputs = ln.find("scl:Inputs", self.ns)
                        if not inputs:
                            inputs = ln.find("Inputs")
                        if inputs is None:
                            continue

                        extrefs = inputs.findall("scl:ExtRef", self.ns) + inputs.findall("ExtRef")
                        for extref in extrefs:
                            service_type = extref.get("serviceType") or ""
                            if service_type.upper() != "GOOSE":
                                continue

                            source_ied = extref.get("iedName") or ""
                            source_ld = extref.get("srcLDInst") or extref.get("ldInst") or ""
                            source_cb = extref.get("srcCBName") or ""
                            source_ln = f"{extref.get('prefix','')}{extref.get('lnClass','')}{extref.get('lnInst','')}"
                            source_do = extref.get("doName") or ""
                            source_da = extref.get("daName") or ""
                            source_bda = extref.get("bdaName") or ""
                            data_attr = _data_attr(source_da, source_bda)
                            source_tag = _build_tag(source_ied, source_ld, source_ln, source_do, data_attr)

                            pub_key = (source_ied, source_ld, source_cb)
                            pub_info = publisher_map.get(pub_key, {})

                            dest_tag = _build_tag(ied_name, ld_inst or "", dest_ln, "", "")

                            entry = {
                                "Mapping Type": "Subscription",
                                "Source IED Name": source_ied or pub_info.get("Source IED Name", ""),
                                "Source AP": pub_info.get("Source AP", ""),
                                "Source LDevice": source_ld or pub_info.get("Source LDevice", ""),
                                "Source IP Address": pub_info.get("Source IP Address", ""),
                                "Source Subnet": pub_info.get("Source Subnet", ""),
                                "Source MAC Address": pub_info.get("Source MAC Address", ""),
                                "Source VLAN-ID": pub_info.get("Source VLAN-ID", ""),
                                "Source VLAN Priority": pub_info.get("Source VLAN Priority", ""),
                                "Source APPID": pub_info.get("Source APPID", ""),
                                "Source MinTime": pub_info.get("Source MinTime", ""),
                                "Source MaxTime": pub_info.get("Source MaxTime", ""),
                                "Source DataSet": pub_info.get("Source DataSet", ""),
                                "DataSet Size": pub_info.get("DataSet Size", ""),
                                "Source ConfRev": pub_info.get("Source ConfRev", ""),
                                "Source ControlBlock": source_cb or pub_info.get("Source ControlBlock", ""),
                                "Source GoID": pub_info.get("Source GoID", ""),
                                "Source FixedOffs": pub_info.get("Source FixedOffs", ""),
                                "Source LogicalNode": source_ln,
                                "Source DataAttribute": data_attr,
                                "Source Tag": source_tag,
                                "Destination IED Name": ied_name,
                                "Destination AP": ap_name,
                                "Destination LDevice": ld_inst,
                                "Destination IP Address": dest_comm.get('ip', ''),
                                "Destination Subnet": dest_comm.get('subnetwork', ''),
                                "Destination MAC Address": dest_comm.get('mac', ''),
                                "Destination LogicalNode": dest_ln,
                                "Destination ServiceType": service_type,
                                "Destination IntAddr": extref.get("intAddr") or "",
                                "Destination Tag": dest_tag
                            }
                            subscription_entries.append(entry)

        if subscription_entries:
            return subscription_entries

        return goose_entries

    def _find_gse_comm_info(self, ied_name, ap_name, ld_inst, cb_name) -> Dict:
        """Helper to find GSE address info in Communication section."""
        info = {'ip': '', 'mac': '', 'vlan': '', 'priority': '', 'appid': '', 'subnetwork': '', 'minTime': '', 'maxTime': ''}
        
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

                    info['subnetwork'] = subnet_name

                    # Fallback: ConnectedAP address (often used by Siemens)
                    ap_address = conn_ap.find("scl:Address", self.ns)
                    if not ap_address:
                        ap_address = conn_ap.find("Address")
                    if ap_address:
                        ap_params = self._parse_address_params(ap_address)
                        if ap_params.get("ip") is not None:
                            info['ip'] = ap_params.get("ip")
                        if ap_params.get("mac_address") is not None:
                            info['mac'] = ap_params.get("mac_address")
                        if ap_params.get("vlan") is not None:
                            info['vlan'] = ap_params.get("vlan")
                        if ap_params.get("vlan_priority") is not None:
                            info['priority'] = ap_params.get("vlan_priority")

                    # Find GSE (strict match first, then relaxed by ldInst)
                    matched = False
                    for gse in conn_ap.findall("scl:GSE", self.ns) + conn_ap.findall("GSE"):
                        gse_ld = gse.get("ldInst")
                        gse_cb = gse.get("cbName")
                        if gse_ld == ld_inst and gse_cb == cb_name:
                            matched = True
                        elif gse_ld == ld_inst and not matched and not gse_cb:
                            matched = True
                        elif gse_ld == ld_inst and not matched and gse_cb == cb_name:
                            matched = True

                        if not matched:
                            continue

                        address = gse.find("scl:Address", self.ns)
                        if not address:
                            address = gse.find("Address")

                        if address:
                            params = self._parse_address_params(address)
                            if params.get("ip") is not None:
                                info['ip'] = params.get("ip")
                            if params.get("mac_address") is not None:
                                info['mac'] = params.get("mac_address")
                            if params.get("vlan") is not None:
                                info['vlan'] = params.get("vlan")
                            if params.get("appid") is not None:
                                info['appid'] = params.get("appid")
                            if params.get("vlan_priority") is not None:
                                info['priority'] = params.get("vlan_priority")

                        min_time = gse.find("scl:MinTime", self.ns)
                        if min_time is not None:
                            info['minTime'] = min_time.text

                        max_time = gse.find("scl:MaxTime", self.ns)
                        if max_time is not None:
                            info['maxTime'] = max_time.text

                        return info

                    # If no GSE matched, return ConnectedAP info when available
                    if info.get('ip') or info.get('mac') or info.get('vlan') or info.get('priority'):
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
                ln_ref = fcda.get('lnRef') or ""
                ln = ln_ref if ln_ref else f"{fcda.get('prefix','')}{fcda.get('lnClass','')}{fcda.get('lnInst','')}"
                entries.append({
                    'ld_inst': fcda.get('ldInst', ''),
                    'ln': ln,
                    'do': fcda.get('doName') or "",
                    'da': fcda.get('daName') or "",
                    'bda': fcda.get('bdaName') or "",
                    'fc': fcda.get('fc') or ""
                })
        return entries
