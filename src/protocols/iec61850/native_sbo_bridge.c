#include "iec61850_server.h"
#include "hal_thread.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#define DLL_EXPORT __declspec(dllexport)
#else
#define DLL_EXPORT
#endif

#ifndef MAX_CONTROL_POINTS
#define MAX_CONTROL_POINTS 64
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*SboOperateCallback)(const char* objectRef, uint8_t commandValue, void* ctx);

typedef struct {
    DataObject* controlObject;
    char reference[256];
    uint32_t sboTimeoutMs;
    uint64_t lastSelectTimestamp;
    bool selected;
} SboControlPoint;

typedef struct {
    IedServer server;
    SboOperateCallback operateCallback;
    void* operateCtx;
    SboControlPoint controlPoints[MAX_CONTROL_POINTS];
    uint8_t controlPointCount;
} SboBridgeContext;

static SboBridgeContext g_ctx = {0};

static uint64_t
sboBridge_getTimeMs(void)
{
    return (uint64_t) Hal_getTimeInMs();
}

static void
sboBridge_reset(void)
{
    memset(&g_ctx, 0, sizeof(g_ctx));
}

static ControlHandlerResult
sboBridge_controlHandler(ControlAction action, void* parameter, MmsValue* value, bool test)
{
    SboControlPoint* controlPoint = (SboControlPoint*) parameter;
    if (controlPoint == NULL) {
        return CONTROL_RESULT_FAILED;
    }

    if (test) {
        printf("[SBO_BRIDGE] TEST command received for %s\n", controlPoint->reference);
        return CONTROL_RESULT_OK;
    }

    const uint64_t now = sboBridge_getTimeMs();

    switch (action) {
    case CONTROL_ACTION_SELECT:
        controlPoint->selected = true;
        controlPoint->lastSelectTimestamp = now;
        printf("[SBO_BRIDGE] SELECT accepted for %s\n", controlPoint->reference);
        return CONTROL_RESULT_OK;

    case CONTROL_ACTION_OPERATE: {
        if (!controlPoint->selected) {
            printf("[SBO_BRIDGE] OPERATE rejected (not selected) for %s\n", controlPoint->reference);
            return CONTROL_RESULT_FAILED;
        }

        if ((now - controlPoint->lastSelectTimestamp) > controlPoint->sboTimeoutMs) {
            controlPoint->selected = false;
            printf("[SBO_BRIDGE] OPERATE rejected (selection timeout) for %s\n", controlPoint->reference);
            return CONTROL_RESULT_FAILED;
        }

        uint8_t commandValue = 0;
        if (value != NULL && MmsValue_getType(value) == MMS_BOOLEAN) {
            commandValue = MmsValue_getBoolean(value) ? 1 : 0;
        }

        controlPoint->selected = false;
        controlPoint->lastSelectTimestamp = 0;

        printf("[SBO_BRIDGE] OPERATE accepted for %s (value=%u)\n", controlPoint->reference, commandValue);

        if (g_ctx.operateCallback != NULL) {
            g_ctx.operateCallback(controlPoint->reference, commandValue, g_ctx.operateCtx);
        }

        return CONTROL_RESULT_OK;
    }

    case CONTROL_ACTION_CANCEL:
        controlPoint->selected = false;
        controlPoint->lastSelectTimestamp = 0;
        printf("[SBO_BRIDGE] CANCEL received for %s\n", controlPoint->reference);
        return CONTROL_RESULT_OK;

    default:
        break;
    }

    return CONTROL_RESULT_FAILED;
}

DLL_EXPORT void
SboBridge_setOperateCallback(SboOperateCallback callback, void* ctx)
{
    g_ctx.operateCallback = callback;
    g_ctx.operateCtx = ctx;
}

DLL_EXPORT IedServer
SboBridge_create(IedModel* model)
{
    sboBridge_reset();

    if (model == NULL) {
        return NULL;
    }

    g_ctx.server = IedServer_create(model);
    return g_ctx.server;
}

DLL_EXPORT bool
SboBridge_start(IedServer server, int tcpPort)
{
    if (server == NULL) {
        return false;
    }

    IedServer_start(server, tcpPort);
    return IedServer_isRunning(server);
}

DLL_EXPORT void
SboBridge_stop(IedServer server)
{
    if (server != NULL) {
        IedServer_stop(server);
    }
}

DLL_EXPORT void
SboBridge_destroy(IedServer server)
{
    if (server != NULL) {
        IedServer_destroy(server);
    }

    if (g_ctx.server == server) {
        sboBridge_reset();
    }
}

DLL_EXPORT int
SboBridge_registerControlPoint(IedServer server,
                               DataObject* controlObject,
                               const char* objectReference,
                               uint32_t sboTimeoutMs)
{
    if (server == NULL || controlObject == NULL || objectReference == NULL) {
        return -1;
    }

    if (g_ctx.server != server) {
        return -2;
    }

    if (g_ctx.controlPointCount >= MAX_CONTROL_POINTS) {
        return -3;
    }

    SboControlPoint* slot = &g_ctx.controlPoints[g_ctx.controlPointCount++];
    memset(slot, 0, sizeof(*slot));

    slot->controlObject = controlObject;
    slot->sboTimeoutMs = (sboTimeoutMs > 0) ? sboTimeoutMs : 30000U;
    strncpy(slot->reference, objectReference, sizeof(slot->reference) - 1);
    slot->reference[sizeof(slot->reference) - 1] = '\0';

    IedServer_setControlHandler(server, controlObject, sboBridge_controlHandler, slot);

    printf("[SBO_BRIDGE] Registered control point %s (timeout=%u ms)\n",
           slot->reference,
           slot->sboTimeoutMs);

    return 0;
}

#ifdef __cplusplus
}
#endif
