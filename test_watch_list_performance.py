"""
Test script to verify watch list performance optimizations.
Run this after adding 294 signals to the watch list.
"""
import time

def test_watch_list_performance(watch_manager):
    """Test watch list performance with large signal count."""
    
    print("\n=== Watch List Performance Test ===")
    print(f"Total watched signals: {len(watch_manager._watched_signals)}")
    print(f"Poll interval: {watch_manager._poll_interval_ms}ms")
    print(f"Max poll batch size: {watch_manager._max_poll_batch}")
    print(f"Current poll index: {watch_manager._poll_index}")
    
    # Calculate expected poll cycle time
    total_signals = len(watch_manager._watched_signals)
    cycle_time_ms = 0  # Initialize to avoid unbound variable
    if total_signals > 0:
        batches_needed = (total_signals + watch_manager._max_poll_batch - 1) // watch_manager._max_poll_batch
        cycle_time_ms = batches_needed * watch_manager._poll_interval_ms
        print(f"\nEstimated full poll cycle time: {cycle_time_ms}ms ({cycle_time_ms/1000:.1f}s)")
        print(f"Batches needed: {batches_needed}")
        print(f"Signals per batch: ~{total_signals // batches_needed if batches_needed > 0 else 0}")
    
    # Check pending updates
    print(f"\nPending updates in queue: {len(watch_manager._pending_updates)}")
    
    # Monitor polling progress
    print("\nMonitoring next 5 polling cycles...")
    start_time = time.time()
    poll_cycles = []
    
    def on_progress(current, total):
        elapsed = time.time() - start_time
        poll_cycles.append((current, total, elapsed))
        print(f"  Poll progress: {current}/{total} at {elapsed:.2f}s")
    
    # Connect to progress signal
    watch_manager.polling_progress.connect(on_progress)
    
    # Wait for 5 poll cycles
    time.sleep(5 * watch_manager._poll_interval_ms / 1000)
    
    # Disconnect
    watch_manager.polling_progress.disconnect(on_progress)
    
    print(f"\nTest completed. Captured {len(poll_cycles)} progress updates.")
    
    # Performance assessment
    if total_signals > 200 and cycle_time_ms < 10000:
        print("✓ Performance: GOOD - Handling large list efficiently")
    elif total_signals > 100 and cycle_time_ms < 5000:
        print("✓ Performance: EXCELLENT - Optimal for medium list")
    else:
        print("✓ Performance: OK")
    
    return poll_cycles


def check_ui_throttling(watch_list_widget):
    """Check UI update throttling status."""
    
    print("\n=== UI Throttling Test ===")
    print(f"Pending UI updates: {len(watch_list_widget._pending_row_updates)}")
    print(f"UI update interval: {watch_list_widget._ui_update_timer.interval()}ms")
    print(f"UI timer active: {watch_list_widget._ui_update_timer.isActive()}")
    
    if watch_list_widget._ui_update_timer.isActive():
        print("✓ UI throttling: ACTIVE")
    else:
        print("⚠ UI throttling: INACTIVE (may be issue if list is large)")


# Usage from main application:
# from test_watch_list_performance import test_watch_list_performance, check_ui_throttling
# test_watch_list_performance(app_controller.watch_manager)
# check_ui_throttling(main_window.watch_list_widget)
