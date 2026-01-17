#!/usr/bin/env python3
"""
Simple test script for the IEC 61850 minimal simulator functionality.
This tests the server adapter with a minimal model creation without Qt dependencies.
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_library_loading():
    """Test if libiec61850 can be loaded"""
    print("Testing libiec61850 library loading...")
    
    try:
        from protocols.iec61850 import iec61850_wrapper as iec61850
        print("✅ iec61850_wrapper loaded successfully")
        
        # Test basic function
        if iec61850.is_library_loaded():
            print("✅ libiec61850 native library loaded successfully")
            return True
        else:
            print("❌ libiec61850 native library not available")
            return False
        
    except Exception as e:
        print(f"❌ Failed to load iec61850_wrapper: {e}")
        return False

def test_minimal_icd_creation():
    """Test creating a minimal ICD file"""
    print("\nTesting minimal ICD creation...")
    
    try:
        from protocols.iec61850 import lib61850 as lib
        import tempfile
        
        print("libiec61850 library loaded via lib61850")
        
        # Create minimal ICD content
        ied_name = "TestIED"
        minimal_icd_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
    <Header id="TestSCL" version="1.0" revision="A"/>
    <DataTypeTemplates>
        <LNodeType id="LLN01" lnClass="LLN0">
            <DO name="Mod" type="INC_1"/>
        </LNodeType>
        <LNodeType id="MMXU1" lnClass="MMXU">
            <DO name="Mod" type="INC_1"/>
        </LNodeType>
        <DOType id="INC_1" cdc="INC">
            <DA name="ctlModel" fc="CF" dchg="true" type="Enum" valKind="RO">
                <Val>status-only</Val>
            </DA>
        </DOType>
    </DataTypeTemplates>
    <IED name="{ied_name}">
        <Services>
            <DynAssociation />
            <GetDirectory />
            <GetDataObjectDefinition />
            <GetDataSetValue />
            <DataSetDirectory />
            <ReadWrite />
        </Services>
        <AccessPoint name="AP1">
            <Server>
                <Authentication none="true"/>
                <LDevice inst="CTRL">
                    <LN0 lnClass="LLN0" inst="" lnType="LLN01"/>
                    <LN lnClass="MMXU" inst="1" lnType="MMXU1"/>
                </LDevice>
            </Server>
        </AccessPoint>
    </IED>
</SCL>'''

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.icd', delete=False) as f:
            f.write(minimal_icd_content)
            temp_icd_path = f.name
        
        print(f"Created temporary ICD: {temp_icd_path}")
        
        # Try to create model
        print(f"Attempting to create model from ICD file")
        try:
            model = lib.ConfigFileParser_createModelFromConfigFileEx(temp_icd_path.encode('utf-8'))
            print(f"Model result: {model}")
        except Exception as e:
            print(f"Exception during model creation: {e}")
            model = None
        
        if model:
            print(f"Model object: {model}")
            print(f"Model has value attr: {hasattr(model, 'value')}")
            if hasattr(model, 'value'):
                print(f"Model value: {model.value}")
                print(f"Model value type: {type(model.value)}")
            
            # Let's just try to use the model regardless
            print("✅ Successfully created model from minimal ICD!")
            
            # Try to create server
            server = lib.IedServer_create(model)
            print(f"Server object: {server}")
            if hasattr(server, 'value'):
                print(f"Server value: {server.value}")
            
            if server:
                print("✅ Successfully created IED server!")
                
                # Try to start server on a test port
                try:
                    result = lib.IedServer_start(server, 10002)
                    print(f"Server start result: {result}")
                    if result == 0:
                        print("✅ Server started successfully on port 10002!")
                        print("Stopping server...")
                        lib.IedServer_stop(server)
                        print("✅ Server stopped")
                        success = True
                    else:
                        print(f"❌ Server failed to start (error code: {result})")
                        success = False
                        
                    lib.IedServer_destroy(server)
                    return success
                except Exception as e:
                    print(f"❌ Error starting/stopping server: {e}")
                    return False
            else:
                print("❌ Failed to create IED server")
                return False
                
        else:
            print("❌ Model is None or falsy")
            return False
        
        # Clean up temp file
        try:
            os.unlink(temp_icd_path)
        except:
            pass
            
        return model is not None
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("IEC 61850 Minimal Simulator Test")
    print("=" * 60)
    
    # Test 1: Library loading
    if not test_library_loading():
        print("\nStopping tests - library loading failed")
        return False
    
    # Test 2: Minimal ICD creation
    icd_result = test_minimal_icd_creation()
    if icd_result:
        print("\n✅ All tests passed!")
        print("The minimal IEC61850 simulator should work now.")
        return True
    else:
        print("\n❌ Minimal ICD test failed")
        print("libiec61850 model creation from minimal ICD is not working")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)