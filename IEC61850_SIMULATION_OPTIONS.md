# IEC 61850 Simulation Options

## Current Status

We are using **libiec61850** - which remains the **best open-source option** for IEC 61850 simulation.

## Why libiec61850 is Still the Best Choice

### Comparison with Alternatives:

| Library | MMS | GOOSE | SV | License | Language | Maturity | Notes |
|---------|-----|-------|----|---------| ---------|----------|-------|
| **libiec61850** | ✅ | ✅ | ✅ | Apache 2.0 | C | ⭐⭐⭐⭐⭐ | Most mature open-source option |
| IEC61850bean | ✅ | ✅ | ✅ | LGPL | Java | ⭐⭐⭐⭐ | Good but Java-based |
| OpenIEC61850 | ⚠️ | ⚠️ | ❌ | GPL | C++ | ⭐⭐ | Less maintained |
| Rapid61850 | ✅ | ✅ | ✅ | Commercial | C | ⭐⭐⭐⭐⭐ | Excellent but $$$$ |
| IEC61850-Toolkit | ✅ | ✅ | ✅ | Commercial | Various | ⭐⭐⭐⭐⭐ | Professional but $$$$ |

**Verdict**: libiec61850 is the best free/open-source option.

## The Real Problem

The issue is **NOT** with libiec61850 itself, but with how we're trying to use it:

### What Works Well:
- ✅ IEC 61850 **client** functionality (connecting to IEDs, reading data)
- ✅ Loading **ICD files** (single IED descriptions)
- ✅ Loading **simple SCD files**
- ✅ Programmatically created models

### What's Challenging:
- ❌ Loading **complex SCD files** with multiple IEDs and communication sections
- ❌ Dynamic model creation from arbitrary SCD structures
- ❌ The `ConfigFileParser_createModelFromConfigFileEx` function has limitations

## Solutions (In Order of Recommendation)

### Option 1: Use ICD Files (BEST for Production) ⭐⭐⭐⭐⭐

**What**: Export individual IED configurations as ICD files from your engineering tool.

**How**:
1. In your IEC 61850 engineering tool (e.g., Siemens DIGSI, ABB PCM600):
   - Select one IED
   - Export as ICD (IED Capability Description)
2. Use the ICD file with SCADA Scout simulator

**Pros**:
- ✅ Works perfectly with libiec61850
- ✅ Smaller file sizes
- ✅ Cleaner configuration
- ✅ Exactly what libiec61850 server was designed for

**Cons**:
- ❌ Requires exporting each IED separately
- ❌ Extra step in workflow

### Option 2: Automatic ICD Extraction (CURRENT) ⭐⭐⭐⭐

**What**: We automatically extract ICD data from SCD files.

**Status**: ✅ Already implemented in `server_adapter.py`

**How it works**:
1. Try to load SCD directly
2. If that fails, extract the IED section + DataTypeTemplates
3. Create temporary ICD file
4. Load from extracted ICD

**Pros**:
- ✅ Automatic - no user intervention
- ✅ Works with SCD files
- ✅ Uses proven libiec61850 functionality

**Cons**:
- ⚠️ May still fail with very complex SCDs
- ⚠️ Doesn't include communication mappings

### Option 3: Simplified SCD Files ⭐⭐⭐

**What**: Pre-process SCD files to remove unnecessary sections.

**How**:
1. Remove all IEDs except the target
2. Simplify communication section
3. Keep only essential DataTypeTemplates

**Status**: Partially implemented but can be improved

### Option 4: Programmatic Model Creation ⭐⭐

**What**: Build the IED model in code using libiec61850 API.

**Why NOT recommended**:
- Extremely complex - requires recreating entire IED structure
- libiec61850's model API is low-level (designed for C developers)
- Would need to create: LogicalDevices, LogicalNodes, DataObjects, DataAttributes, etc.
- Each element needs proper type information, functional constraints, etc.

**Example complexity**:
```c
// This is what it looks like in C - imagine doing this for 100s of data points!
IedModel* model = IedModel_create("IED1");
LogicalDevice* ld = LogicalDevice_create("LD0", model);
LogicalNode* ln = LogicalNode_create("LLN0", ld);
DataObject* mod = DataObject_create("Mod", ln, 0);
DataAttribute* modStVal = DataAttribute_create("stVal", mod, IEC61850_INT32, IEC61850_FC_ST, 0, 0, 0);
// ... repeat for every single data point
```

### Option 5: Commercial Simulators ⭐⭐⭐⭐⭐ (If Budget Allows)

**Options**:
- **Omicron CMC** with IEC 61850 module
- **Doble F6150** Test System
- **Reason RPV** Relay Test System
- **Rapid61850** Software simulator

**Pros**:
- ✅ Full SCD support
- ✅ Professional support
- ✅ Advanced features
- ✅ Proven in utilities

**Cons**:
- 💰 Very expensive ($10,000 - $100,000+)
- 🔒 Proprietary
- 📦 Often requires hardware

## Recommended Workflow for SCADA Scout

### For Testing/Development:
1. Use **Option 2** (automatic ICD extraction) - already implemented
2. If it fails, user should:
   - Export ICD from engineering tool
   - Or simplify the SCD file

### For Production Use:
1. **Export ICD files** from engineering tool (Option 1)
2. Configure simulator to use ICD files directly
3. Falls back to automatic extraction if needed

## Implementation Status

✅ **Implemented**:
- ICD extraction from SCD
- Fallback mechanism
- Clear error messages

🔄 **Could Improve**:
- Better SCD simplification
- Support for more SCD variants
- GUI option to select ICD vs SCD

❌ **Not Recommended**:
- Full programmatic model builder (too complex)
- Switching to different library (no better free option)

## Bottom Line

**libiec61850 is the right choice.** The solution is to work within its design:
1. Use ICD files when possible
2. Let automatic extraction handle SCD files
3. Provide clear guidance when it fails

This is the same approach used by professional IEC 61850 tools and simulators.
