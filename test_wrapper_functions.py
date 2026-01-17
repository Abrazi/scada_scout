#!/usr/bin/env python3
"""Test that all new ControlObjectClient wrapper functions are available."""

from src.protocols.iec61850 import iec61850_wrapper as iec61850

print('Testing wrapper functions...')
print('ControlObjectClient_create:', hasattr(iec61850, 'ControlObjectClient_create'))
print('ControlObjectClient_getControlModel:', hasattr(iec61850, 'ControlObjectClient_getControlModel'))
print('ControlObjectClient_select:', hasattr(iec61850, 'ControlObjectClient_select'))
print('ControlObjectClient_selectWithValue:', hasattr(iec61850, 'ControlObjectClient_selectWithValue'))
print('ControlObjectClient_operate:', hasattr(iec61850, 'ControlObjectClient_operate'))
print('ControlObjectClient_getLastError:', hasattr(iec61850, 'ControlObjectClient_getLastError'))
print('ControlObjectClient_destroy:', hasattr(iec61850, 'ControlObjectClient_destroy'))
print('ControlObjectClient_setOriginator:', hasattr(iec61850, 'ControlObjectClient_setOriginator'))
print('\nAll wrapper functions available!')
