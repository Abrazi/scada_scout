@ECHO OFF
CLS

:: List adapters and number them
ECHO =============================================
ECHO Available Network Adapters:
ECHO =============================================
setlocal enabledelayedexpansion
set count=0
for /f "skip=3 tokens=1,2,3,*" %%A in ('netsh interface show interface') do (
    set /a count+=1
    set "adapter[!count!]=%%D"
    echo !count!. %%D
)
ECHO =============================================
SET /P adapterChoice=Enter the number of the adapter to configure: 
set "interface="
for /L %%i in (1,1,!count!) do (
    if "%%i"=="%adapterChoice%" set "interface=!adapter[%%i]!"
)

IF NOT DEFINED interface (
    ECHO Invalid selection. Exiting.
    pause
    exit /b
)

:: Ask for action
ECHO =============================================
ECHO Press 1 to Add Static IPs
ECHO Press 2 to Return to DHCP
ECHO =============================================
SET /P action=Your choice (1 or 2): 

IF "%action%"=="1" GOTO ADD_IPS
IF "%action%"=="2" GOTO DHCP
ECHO Invalid option. Exiting.
pause
exit /b

:ADD_IPS
SET mask=255.255.0.0

:: Add generator IPs
FOR %%A IN (
  172.16.31.13 172.16.31.23 172.16.31.33 172.16.31.43 172.16.31.53
  172.16.32.13 172.16.32.23 172.16.32.33 172.16.32.43 172.16.32.53
  172.16.33.13 172.16.33.23 172.16.33.33 172.16.33.43 172.16.33.53
  172.16.34.13 172.16.34.23 172.16.34.33 172.16.34.43 172.16.34.53
  172.16.35.13 172.16.35.23
) DO (
  netsh interface ipv4 add address name="%interface%" addr=%%A mask=%mask%
)

:: Add switchgear IPs
FOR %%B IN (
  172.16.31.63 172.16.32.63 172.16.33.63 172.16.34.63
) DO (
  netsh interface ipv4 add address name="%interface%" addr=%%B mask=%mask%
)

ECHO =============================================
ECHO IPs added to %interface%.
PAUSE
GOTO END

:DHCP
ECHO Setting %interface% to DHCP...
netsh interface ipv4 set address name="%interface%" source=dhcp
netsh interface ipv4 set dns name="%interface%" source=dhcp
ECHO Adapter %interface% reset to DHCP.
PAUSE
GOTO END

:END
ECHO =============================================
ECHO Script execution completed.
PAUSE
