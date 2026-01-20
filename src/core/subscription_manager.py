import logging
from typing import Dict, Set, Optional, List
from PySide6.QtCore import QObject, Signal as QtSignal

from src.models.subscription_models import IECSubscription, SubscriptionMode

logger = logging.getLogger(__name__)

class IECSubscriptionManager(QObject):
    """
    Single Source of Truth for all active data subscriptions.
    Workers adhere strictly to this manager's state.
    """
    # Emitted when subscriptions for a device change, so workers can re-evaluate
    subscriptions_changed = QtSignal(str) # device_name

    def __init__(self):
        super().__init__()
        # Storage: device_name -> Set[IECSubscription]
        self._subs_by_device: Dict[str, Set[IECSubscription]] = {}

    def subscribe(self, sub: IECSubscription):
        """Add a subscription."""
        if sub.device not in self._subs_by_device:
            self._subs_by_device[sub.device] = set()
        
        if sub in self._subs_by_device[sub.device]:
            return # Idempotent
            
        self._subs_by_device[sub.device].add(sub)
        logger.info(f"Subscribed: {sub.device} {sub.mms_path} [{sub.mode.value}] via {sub.source}")
        self.subscriptions_changed.emit(sub.device)

    def unsubscribe(self, sub: IECSubscription):
        """Remove a specific subscription."""
        if sub.device in self._subs_by_device:
            if sub in self._subs_by_device[sub.device]:
                self._subs_by_device[sub.device].remove(sub)
                logger.debug(f"Unsubscribed: {sub.device} {sub.mms_path} via {sub.source}")
                self.subscriptions_changed.emit(sub.device)

    def unsubscribe_all(self, device: str, source: Optional[str] = None):
        """
        Remove all subscriptions for a device, optionally filtering by source.
        Critically used for 'Clear Live Data'.
        """
        if device not in self._subs_by_device:
            return

        if source is None:
            # Wipe all
            self._subs_by_device[device].clear()
            logger.info(f"Unsubscribed ALL for {device}")
        else:
            # Filter by source
            to_remove = {s for s in self._subs_by_device[device] if s.source == source}
            if not to_remove:
                return
            
            self._subs_by_device[device] -= to_remove
            logger.info(f"Unsubscribed {len(to_remove)} items for {device} (source={source})")

        self.subscriptions_changed.emit(device)

    def get_subscriptions(self, device: str, mode: Optional[SubscriptionMode] = None) -> List[IECSubscription]:
        """Get current subscriptions, optionally filtered by mode."""
        if device not in self._subs_by_device:
            return []
            
        subs = list(self._subs_by_device[device])
        
        if mode:
            subs = [s for s in subs if s.mode == mode]
            
        return subs

    def rename_device(self, old_name: str, new_name: str):
        """Rename subscriptions stored under `old_name` to `new_name`."""
        if not old_name or not new_name or old_name == new_name:
            return

        if old_name not in self._subs_by_device:
            return

        try:
            old_set = self._subs_by_device.pop(old_name)
            new_set = self._subs_by_device.get(new_name, set())
            for sub in old_set:
                # Recreate subscription with new device name
                new_sub = IECSubscription(device=new_name, mms_path=sub.mms_path, fc=sub.fc, mode=sub.mode, source=sub.source)
                new_set.add(new_sub)

            self._subs_by_device[new_name] = new_set
            # Notify listeners that subscriptions changed for both devices
            self.subscriptions_changed.emit(old_name)
            self.subscriptions_changed.emit(new_name)
            logger.info(f"Renamed subscriptions: {old_name} -> {new_name}")
        except Exception:
            logger.exception(f"Failed to rename subscriptions from {old_name} to {new_name}")
    
    def is_subscribed(self, device: str, mms_path: str) -> bool:
        """Check if an active subscription exists for this path."""
        if device not in self._subs_by_device:
            return False
            
        # Optimization: We could use a secondary index if this is slow,
        # but for <10k signals iteration is fine.
        for sub in self._subs_by_device[device]:
            if sub.mms_path == mms_path:
                return True
        return False
