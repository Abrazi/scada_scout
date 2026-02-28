import os
import sys
import ctypes

# Add src to path
sys.path.insert(0, os.path.abspath('src'))

from protocols.iec61850.server_adapter import IEC61850ServerAdapter
from models.device_models import DeviceConfig, DeviceType
from protocols.iec61850 import lib61850 as lib

def dump_node(node_ptr, depth=0):
    if not node_ptr: return
    
    # Try to get object reference if available
    if hasattr(lib, "ModelNode_getObjectReference"):
        try:
            ref = lib.ModelNode_getObjectReference(node_ptr)
            if ref:
                print("  " * depth + str(ref.decode('utf-8')))
        except Exception as e:
            print("  " * depth + f"Error getting ref: {e}")
    else:
        print("  " * depth + "Node")
        
    # Recurse to children
    if hasattr(lib, "ModelNode_getChild"):
        if hasattr(lib, "ModelNode_getChildren"):
            ll = lib.ModelNode_getChildren(node_ptr)
            if ll:
                # Need LinkedList traversal - let's keep it simple for now
                pass

def test_dump():
    scd_path = "/home/majid/Documents/scada_scout/dubgg/DUBGG.scd"
    
    # Wait, let's just use the server_adapter on a simple ICD extraction
    config = DeviceConfig(
        name="UPM02ADMIN",
        ip_address="0.0.0.0",
        port=10102,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path=scd_path
    )

    adapter = IEC61850ServerAdapter(config)
    adapter._filtered_scd_path = None # Do extraction!
    
    # Let's bypass the normal connect and just load the raw SCD directly
    adapter.connect()
    model = adapter.model
    if not model:
        print("Failed to load model from adapter.")

    # We want to see how the SBO registration traverses the model
    # Look at how SBO register finds nodes:
    # `IedModel_getDeviceModel` -> iterates the linked list!
    
    if model and hasattr(lib, "IedModel_getDeviceModel"):
        ld_ptr = lib.IedModel_getDeviceModel(model)
        while ld_ptr:
            print(f"LD Name: {ld_ptr}")
            if hasattr(lib, "ModelNode_getObjectReference"):
                ref = lib.ModelNode_getObjectReference(ctypes.cast(ld_ptr, ctypes.POINTER(lib.ModelNode)))
                if ref:
                    print(f"  LD Ref: {ref.decode('utf-8')}")
                    
                # Let's find DCCILO1 inside CTRL using getChild
                if b"CTRL" in ref:
                    ln_ptr = lib.ModelNode_getChild(ctypes.cast(ld_ptr, ctypes.POINTER(lib.ModelNode)), b"DCCILO1")
                    if ln_ptr:
                        ln_ref = lib.ModelNode_getObjectReference(ln_ptr)
                        print(f"    LN Ref: {ln_ref.decode('utf-8')}")
                        
                        do_ptr = lib.ModelNode_getChild(ln_ptr, b"EnaOpn")
                        if do_ptr:
                            do_ref = lib.ModelNode_getObjectReference(do_ptr)
                            print(f"      DO Ref: {do_ref.decode('utf-8')}")
                            
                            da_ptr = lib.ModelNode_getChild(do_ptr, b"stVal")
                            if da_ptr:
                                da_ref = lib.ModelNode_getObjectReference(da_ptr)
                                print(f"        DA Ref: {da_ref.decode('utf-8')}")

            # Get next LD
            # We don't have python bindings for next LD easily without LinkedList traversal...
            break # Just do first one for now

if __name__ == '__main__':
    test_dump()
