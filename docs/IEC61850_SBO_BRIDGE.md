# IEC 61850 C SBO Bridge

This project can use a small C bridge to keep SBO timing and validation in C while Python only reacts to callbacks.

## What it does
- Wraps `IedServer_create` and `IedServer_start` in C.
- Registers SBO control points in C via `IedServer_setControlHandler`.
- Calls back into Python on OPERATE so Python can update `stVal`, `opOk`, and `t`.

## Build (Windows, MSVC)

1) Ensure libiec61850 headers and libraries are available.

2) Compile the bridge from this repo:

- Source file: src/protocols/iec61850/native_sbo_bridge.c
- Output: src/protocols/iec61850/sbo_bridge.dll

Example MSVC command (adjust include/lib paths to your libiec61850 build):

```
cl /LD /O2 /I "<path-to-libiec61850-include>" \
   src\protocols\iec61850\native_sbo_bridge.c \
   /link /DLL /OUT:src\protocols\iec61850\sbo_bridge.dll \
   /LIBPATH:"<path-to-libiec61850-lib>" iec61850.lib
```

If you are using the Triangle MicroWorks SDK, point `<path-to-libiec61850-include>` and `<path-to-libiec61850-lib>` to the SDK include/lib folders.

## Enable/Disable

- Enabled by default when the DLL is found.
- Disable with:
  - `IEC61850_USE_C_SBO=false`

## Runtime behavior
- If the DLL loads, the server is created/started via the C bridge.
- SBO handler registration happens in C.
- Python updates values only when the C callback fires.
