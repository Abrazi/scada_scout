#!/usr/bin/env python3
"""
Test script to verify compressed SCD file import functionality
Specifically tests the dubgg.sz file extraction
"""

import os
import sys
import tempfile
import logging

# Setup path to import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.archive_utils import ArchiveExtractor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_dubgg_sz_extraction():
    """Test extracting SCD file from dubgg.sz"""
    
    print("="*70)
    print("Testing dubgg.sz SCD File Extraction")
    print("="*70)
    
    # Path to dubgg.sz file
    sz_file_path = os.path.join(os.path.dirname(__file__), "dubgg.sz")
    
    # Check if file exists
    if not os.path.exists(sz_file_path):
        print(f"❌ ERROR: dubgg.sz not found at {sz_file_path}")
        return False
    
    print(f"✓ Found dubgg.sz at: {sz_file_path}")
    print(f"  File size: {os.path.getsize(sz_file_path)} bytes")
    print()
    
    # Step 1: Check if it's recognized as an archive
    print("Step 1: Checking if file is recognized as archive...")
    is_archive = ArchiveExtractor.is_archive(sz_file_path)
    if is_archive:
        print("✓ File is recognized as an archive")
    else:
        print("❌ File is NOT recognized as an archive")
        return False
    print()
    
    # Step 2: List files in the archive
    print("Step 2: Listing files in archive...")
    try:
        files_in_archive = ArchiveExtractor.list_files(sz_file_path)
        print(f"✓ Found {len(files_in_archive)} file(s) in archive:")
        for i, filename in enumerate(files_in_archive, 1):
            print(f"  {i}. {filename}")
    except Exception as e:
        print(f"❌ Failed to list files: {e}")
        logger.exception("List files failed")
        return False
    print()
    
    # Step 3: Find SCD/SCL files
    print("Step 3: Searching for SCD/SCL files...")
    scd_files = [f for f in files_in_archive 
                 if f.lower().endswith(('.scd', '.cid', '.icd', '.xml'))]
    
    if not scd_files:
        print("⚠ No files with SCD/SCL extensions found in archive")
        print("  Note: Some .sz files contain files without extensions")
        print("  Proceeding with first file in archive...")
        if files_in_archive:
            scd_files = [files_in_archive[0]]
        else:
            print("❌ No files found in archive at all")
            return False
    
    print(f"✓ Using {len(scd_files)} file(s) for extraction:")
    for i, filename in enumerate(scd_files, 1):
        print(f"  {i}. {filename}")
    print()
    
    # Step 4: Select file to extract (prefer .scd)
    print("Step 4: Selecting file to extract...")
    selected_file = None
    for ext in ['.scd', '.cid', '.icd', '.xml']:
        for f in scd_files:
            if f.lower().endswith(ext):
                selected_file = f
                break
        if selected_file:
            break
    
    if not selected_file:
        selected_file = scd_files[0]
    
    print(f"✓ Selected: {selected_file}")
    print()
    
    # Step 5: Extract the file
    print("Step 5: Extracting file to temporary directory...")
    temp_dir = tempfile.mkdtemp(prefix="test_scada_scout_")
    print(f"  Temp directory: {temp_dir}")
    
    try:
        extracted_path = ArchiveExtractor.extract_file(sz_file_path, selected_file, temp_dir)
        print(f"✓ Extracted to: {extracted_path}")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        logger.exception("Extraction failed")
        return False
    print()
    
    # Step 6: Verify extracted file exists
    print("Step 6: Verifying extracted file...")
    if not os.path.exists(extracted_path):
        print(f"❌ Extracted file does not exist at: {extracted_path}")
        return False
    
    file_size = os.path.getsize(extracted_path)
    print(f"✓ File exists and is {file_size} bytes")
    print()
    
    # Step 7: Try to read first few lines (basic validation)
    print("Step 7: Validating file content...")
    try:
        with open(extracted_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_lines = [f.readline() for _ in range(10)]
            
        # Check if it looks like XML
        content_preview = ''.join(first_lines)
        if '<?xml' in content_preview.lower() or '<scl' in content_preview.lower():
            print("✓ File appears to be valid XML/SCL content")
            print("\n  First few lines:")
            for i, line in enumerate(first_lines[:5], 1):
                preview = line.strip()[:80]
                if preview:
                    print(f"    {i}. {preview}...")
        else:
            print("⚠ Warning: File may not be valid XML/SCL")
            print(f"  Content starts with: {content_preview[:100]}")
            
    except Exception as e:
        print(f"⚠ Warning: Could not read file content: {e}")
    print()
    
    # Step 8: Test with SCDParser (if available)
    print("Step 8: Testing with SCDParser...")
    try:
        from src.core.scd_parser import SCDParser
        
        parser = SCDParser(extracted_path)
        ieds = parser.extract_ieds_info()
        
        print(f"✓ SCDParser successfully parsed the file")
        print(f"  Found {len(ieds)} IED(s)")
        
        if ieds:
            print("\n  IED Details:")
            for i, ied in enumerate(ieds[:5], 1):  # Show first 5
                print(f"    {i}. Name: {ied.get('name', 'N/A')}")
                print(f"       IP: {ied.get('ip', 'N/A')}")
                print(f"       Access Point: {ied.get('access_point', 'N/A')}")
                if i < len(ieds):
                    print()
            
            if len(ieds) > 5:
                print(f"    ... and {len(ieds) - 5} more IED(s)")
    except ImportError:
        print("⚠ SCDParser not available - skipping parser test")
    except Exception as e:
        print(f"❌ SCDParser failed: {e}")
        logger.exception("Parser failed")
        return False
    print()
    
    # Cleanup
    print("Step 9: Cleaning up...")
    try:
        import shutil
        shutil.rmtree(temp_dir)
        print(f"✓ Cleaned up temporary directory")
    except Exception as e:
        print(f"⚠ Warning: Failed to cleanup temp dir: {e}")
    print()
    
    print("="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    return True


def test_archive_extractor_basic():
    """Test basic ArchiveExtractor functionality"""
    
    print("\n")
    print("="*70)
    print("Testing ArchiveExtractor Basic Functionality")
    print("="*70)
    print()
    
    # Test supported extensions
    print("Supported file extensions:")
    for ext in ArchiveExtractor.SUPPORTED_EXTENSIONS:
        print(f"  - {ext}")
    print()
    
    print("Recognized archive extensions:")
    for ext in ArchiveExtractor.ARCHIVE_EXTENSIONS:
        print(f"  - {ext}")
    print()
    
    # Test is_archive method
    print("Testing is_archive() method:")
    test_cases = [
        ("test.sz", True),
        ("test.zip", True),
        ("test.rar", True),
        ("test.7z", True),
        ("test.scd", False),
        ("test.xml", False),
        ("test.txt", False),
    ]
    
    all_passed = True
    for filename, expected in test_cases:
        result = ArchiveExtractor.is_archive(filename)
        status = "✓" if result == expected else "❌"
        print(f"  {status} {filename}: {result} (expected {expected})")
        if result != expected:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ Basic functionality tests passed!")
    else:
        print("❌ Some basic tests failed!")
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "="*70)
    print(" SCADA Scout - Compressed SCD File Import Test")
    print("="*70 + "\n")
    
    # Run basic tests first
    basic_passed = test_archive_extractor_basic()
    
    # Run dubgg.sz specific test
    dubgg_passed = test_dubgg_sz_extraction()
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    print(f"  Basic Tests: {'✅ PASSED' if basic_passed else '❌ FAILED'}")
    print(f"  dubgg.sz Test: {'✅ PASSED' if dubgg_passed else '❌ FAILED'}")
    print("="*70 + "\n")
    
    # Exit with appropriate code
    sys.exit(0 if (basic_passed and dubgg_passed) else 1)
