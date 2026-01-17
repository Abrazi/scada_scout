# Memory Optimization Fix for Large Signal Counts

## Problem
When loading devices with large numbers of signals (e.g., 7898 signals), the application would crash with exit code 137 (SIGKILL - system killing process due to memory exhaustion). This occurred because:

1. The `add_node_to_live()` method collected ALL signals from a node
2. The `set_node_filter()` method loaded ALL signals into the table model
3. Qt created thousands of widgets (table rows/cells) simultaneously
4. System ran out of memory and killed the process

## Solution
Implemented **signal limiting with user choice dialogs** in `/home/majid/Documents/scada_scout/src/ui/widgets/signals_view.py`:

### 1. Signal Limit Threshold
- Set `MAX_SIGNALS = 2000` as safe threshold
- When signal count exceeds this, user is prompted with options

### 2. User Dialog Options
When >2000 signals detected, user sees dialog with:
- **Load First 2000**: Safely loads first 2000 signals only (recommended)
- **Load All (Risky)**: Attempts to load all signals (may crash, but user is warned)
- **Cancel**: Abort the operation

### 3. Modified Methods

#### `add_node_to_live(node, device_name=None)`
- Lines 317-400 modified
- Checks signal count before adding to table
- Shows dialog if count > MAX_SIGNALS
- Limits signals to first 2000 if user chooses safe option
- Logs warning if user chooses to load all
- Updates event log with "(limited)" suffix when applicable

#### `set_node_filter(node, device_name=None)`
- Lines 291-365 modified
- Pre-collects signals to check count
- Shows dialog if count > MAX_SIGNALS
- Uses `table_model.set_signals()` directly for limited set
- Falls through to normal `table_model.set_node_filter()` if count is safe or user chooses "Load All"

## Benefits
1. **Prevents Crashes**: System no longer kills app due to memory exhaustion
2. **User Control**: User decides whether to risk loading all signals
3. **Clear Communication**: User understands why signals are limited and how to view more
4. **Performance**: Loading 2000 signals is fast and responsive
5. **Filtering Guidance**: Dialog suggests using filters or sub-nodes for specific signals

## Usage Recommendations
- **For large devices**: Select specific sub-nodes (e.g., logical nodes, equipment) rather than root device
- **Use filters**: Type in the filter box to narrow down visible signals
- **Tree navigation**: Expand device tree and select smaller branches
- **Avoid root selection**: Don't select top-level device node if it contains >2000 signals

## Technical Details
- **Memory Impact**: Each Qt table cell creates multiple objects (delegates, items, models)
- **Safe Limit**: 2000 signals = ~6000-8000 Qt objects (manageable)
- **Dangerous Limit**: 7898 signals = ~23,000-31,000 Qt objects (likely crash)
- **Protection Points**: Both `add_node_to_live()` and `set_node_filter()` are protected

## Testing
1. Import large SCD file with devices containing >2000 signals
2. Click on device with 7898 signals in device tree
3. Verify dialog appears with options
4. Select "Load First 2000"
5. Verify first 2000 signals load successfully
6. Verify informational message appears
7. Use filter to search for specific signals

## Future Enhancements
Potential improvements for even better performance:
- **Pagination**: Add "Load Next 2000" button to view signals in batches
- **Virtual Scrolling**: Only create Qt widgets for visible rows (lazy loading)
- **Smart Caching**: Keep frequently accessed signals in memory, unload others
- **Background Loading**: Load signals in chunks over time
- **Database Backend**: Store signals in SQLite for large datasets

## Files Modified
- `/home/majid/Documents/scada_scout/src/ui/widgets/signals_view.py`
  - `add_node_to_live()`: Lines 317-400
  - `set_node_filter()`: Lines 291-365

## Related Files
- `/home/majid/Documents/scada_scout/src/ui/models/signal_table_model.py`: Table model that holds signals
- `/home/majid/Documents/scada_scout/src/models/device_models.py`: Signal data structures
- `/home/majid/Documents/scada_scout/src/core/scd_parser.py`: Already optimized with caching

## See Also
- `IEC61850_SETUP.md`: IEC 61850 library setup
- `SETTINGS_GUIDE.md`: Application settings
- `.github/copilot-instructions.md`: Development guidelines
