@echo off
REM Batch file to add IP addresses to network adapter
REM Generated on: 05/02/2026 09:52:28
REM Run as Administrator

echo Adding IP addresses to adapter: Ethernet 5
echo.

echo Adding IP 1/302: 172.16.25.61/255.255.0.0 (SubNet: SCADA, IED: GBCUPM01, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.61 255.255.0.0

echo Adding IP 2/302: 10.16.11.18/255.255.0.0 (SubNet: Interlock, IED: GPS01ECB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.18 255.255.0.0

echo Adding IP 3/302: 172.16.11.18/255.255.0.0 (SubNet: SCADA, IED: GPS01ECB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.18 255.255.0.0

echo Adding IP 4/302: 10.16.11.15/255.255.0.0 (SubNet: Interlock, IED: GPS01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.15 255.255.0.0

echo Adding IP 5/302: 172.16.11.15/255.255.0.0 (SubNet: SCADA, IED: GPS01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.15 255.255.0.0

echo Adding IP 6/302: 10.16.11.16/255.255.0.0 (SubNet: Interlock, IED: GPS01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.16 255.255.0.0

echo Adding IP 7/302: 172.16.11.16/255.255.0.0 (SubNet: SCADA, IED: GPS01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.16 255.255.0.0

echo Adding IP 8/302: 10.16.11.21/255.255.0.0 (SubNet: Interlock, IED: GPS01FCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.21 255.255.0.0

echo Adding IP 9/302: 172.16.11.21/255.255.0.0 (SubNet: SCADA, IED: GPS01FCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.21 255.255.0.0

echo Adding IP 10/302: 10.16.11.19/255.255.0.0 (SubNet: Interlock, IED: GPS01FCB04, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.19 255.255.0.0

echo Adding IP 11/302: 172.16.11.19/255.255.0.0 (SubNet: SCADA, IED: GPS01FCB04, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.19 255.255.0.0

echo Adding IP 12/302: 10.16.11.20/255.255.0.0 (SubNet: Interlock, IED: GPS01FCB05, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.20 255.255.0.0

echo Adding IP 13/302: 172.16.11.20/255.255.0.0 (SubNet: SCADA, IED: GPS01FCB05, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.20 255.255.0.0

echo Adding IP 14/302: 10.16.11.2/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.2 255.255.0.0

echo Adding IP 15/302: 172.16.11.2/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.2 255.255.0.0

echo Adding IP 16/302: 10.16.11.4/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.4 255.255.0.0

echo Adding IP 17/302: 172.16.11.4/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.4 255.255.0.0

echo Adding IP 18/302: 10.16.11.6/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.6 255.255.0.0

echo Adding IP 19/302: 172.16.11.6/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.6 255.255.0.0

echo Adding IP 20/302: 10.16.11.9/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB04, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.9 255.255.0.0

echo Adding IP 21/302: 172.16.11.9/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB04, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.9 255.255.0.0

echo Adding IP 22/302: 10.16.11.11/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB05, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.11 255.255.0.0

echo Adding IP 23/302: 172.16.11.11/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB05, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.11 255.255.0.0

echo Adding IP 24/302: 10.16.11.13/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB06, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.13 255.255.0.0

echo Adding IP 25/302: 172.16.11.13/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB06, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.13 255.255.0.0

echo Adding IP 26/302: 10.16.11.14/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB07, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.14 255.255.0.0

echo Adding IP 27/302: 172.16.11.14/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB07, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.14 255.255.0.0

echo Adding IP 28/302: 10.16.11.3/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB08, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.3 255.255.0.0

echo Adding IP 29/302: 172.16.11.3/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB08, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.3 255.255.0.0

echo Adding IP 30/302: 10.16.11.5/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB09, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.5 255.255.0.0

echo Adding IP 31/302: 172.16.11.5/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB09, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.5 255.255.0.0

echo Adding IP 32/302: 10.16.11.8/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB10, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.8 255.255.0.0

echo Adding IP 33/302: 172.16.11.8/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB10, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.8 255.255.0.0

echo Adding IP 34/302: 10.16.11.10/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB11, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.10 255.255.0.0

echo Adding IP 35/302: 172.16.11.10/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB11, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.10 255.255.0.0

echo Adding IP 36/302: 10.16.11.12/255.255.0.0 (SubNet: Interlock, IED: GPS01GCB12, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.12 255.255.0.0

echo Adding IP 37/302: 172.16.11.12/255.255.0.0 (SubNet: SCADA, IED: GPS01GCB12, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.12 255.255.0.0

echo Adding IP 38/302: 10.16.21.12/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC01UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.12 255.255.0.0

echo Adding IP 39/302: 172.16.21.12/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC01UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.12 255.255.0.0

echo Adding IP 40/302: 10.16.21.13/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC01UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.13 255.255.0.0

echo Adding IP 41/302: 172.16.21.13/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC01UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.13 255.255.0.0

echo Adding IP 42/302: 10.16.21.11/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC01UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.11 255.255.0.0

echo Adding IP 43/302: 172.16.21.11/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC01UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.11 255.255.0.0

echo Adding IP 44/302: 10.16.21.22/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC02UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.22 255.255.0.0

echo Adding IP 45/302: 172.16.21.22/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC02UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.22 255.255.0.0

echo Adding IP 46/302: 10.16.21.23/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC02UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.23 255.255.0.0

echo Adding IP 47/302: 172.16.21.23/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC02UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.23 255.255.0.0

echo Adding IP 48/302: 10.16.21.21/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC02UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.21 255.255.0.0

echo Adding IP 49/302: 172.16.21.21/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC02UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.21 255.255.0.0

echo Adding IP 50/302: 10.16.21.32/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC03UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.32 255.255.0.0

echo Adding IP 51/302: 172.16.21.32/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC03UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.32 255.255.0.0

echo Adding IP 52/302: 10.16.21.33/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC03UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.33 255.255.0.0

echo Adding IP 53/302: 172.16.21.33/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC03UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.33 255.255.0.0

echo Adding IP 54/302: 10.16.21.31/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC03UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.31 255.255.0.0

echo Adding IP 55/302: 172.16.21.31/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC03UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.31 255.255.0.0

echo Adding IP 56/302: 10.16.21.42/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC04UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.42 255.255.0.0

echo Adding IP 57/302: 172.16.21.42/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC04UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.42 255.255.0.0

echo Adding IP 58/302: 10.16.21.43/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC04UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.43 255.255.0.0

echo Adding IP 59/302: 172.16.21.43/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC04UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.43 255.255.0.0

echo Adding IP 60/302: 10.16.21.41/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC04UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.41 255.255.0.0

echo Adding IP 61/302: 172.16.21.41/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC04UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.41 255.255.0.0

echo Adding IP 62/302: 10.16.21.52/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC05UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.52 255.255.0.0

echo Adding IP 63/302: 172.16.21.52/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC05UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.52 255.255.0.0

echo Adding IP 64/302: 10.16.21.53/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC05UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.53 255.255.0.0

echo Adding IP 65/302: 172.16.21.53/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC05UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.53 255.255.0.0

echo Adding IP 66/302: 10.16.21.51/255.255.0.0 (SubNet: Interlock, IED: GPS01GPC05UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.21.51 255.255.0.0

echo Adding IP 67/302: 172.16.21.51/255.255.0.0 (SubNet: SCADA, IED: GPS01GPC05UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.21.51 255.255.0.0

echo Adding IP 68/302: 10.16.11.17/255.255.0.0 (SubNet: Interlock, IED: GPS01LBB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.17 255.255.0.0

echo Adding IP 69/302: 172.16.11.17/255.255.0.0 (SubNet: SCADA, IED: GPS01LBB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.17 255.255.0.0

echo Adding IP 70/302: 10.16.11.1/255.255.0.0 (SubNet: Interlock, IED: GPS01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.11.1 255.255.0.0

echo Adding IP 71/302: 172.16.11.1/255.255.0.0 (SubNet: SCADA, IED: GPS01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.11.1 255.255.0.0

echo Adding IP 72/302: 10.16.12.18/255.255.0.0 (SubNet: Interlock, IED: GPS02ECB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.18 255.255.0.0

echo Adding IP 73/302: 172.16.12.18/255.255.0.0 (SubNet: SCADA, IED: GPS02ECB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.18 255.255.0.0

echo Adding IP 74/302: 10.16.12.15/255.255.0.0 (SubNet: Interlock, IED: GPS02FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.15 255.255.0.0

echo Adding IP 75/302: 172.16.12.15/255.255.0.0 (SubNet: SCADA, IED: GPS02FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.15 255.255.0.0

echo Adding IP 76/302: 10.16.12.16/255.255.0.0 (SubNet: Interlock, IED: GPS02FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.16 255.255.0.0

echo Adding IP 77/302: 172.16.12.16/255.255.0.0 (SubNet: SCADA, IED: GPS02FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.16 255.255.0.0

echo Adding IP 78/302: 10.16.12.21/255.255.0.0 (SubNet: Interlock, IED: GPS02FCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.21 255.255.0.0

echo Adding IP 79/302: 172.16.12.21/255.255.0.0 (SubNet: SCADA, IED: GPS02FCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.21 255.255.0.0

echo Adding IP 80/302: 10.16.12.19/255.255.0.0 (SubNet: Interlock, IED: GPS02FCB04, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.19 255.255.0.0

echo Adding IP 81/302: 172.16.12.19/255.255.0.0 (SubNet: SCADA, IED: GPS02FCB04, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.19 255.255.0.0

echo Adding IP 82/302: 10.16.12.20/255.255.0.0 (SubNet: Interlock, IED: GPS02FCB05, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.20 255.255.0.0

echo Adding IP 83/302: 172.16.12.20/255.255.0.0 (SubNet: SCADA, IED: GPS02FCB05, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.20 255.255.0.0

echo Adding IP 84/302: 10.16.12.2/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.2 255.255.0.0

echo Adding IP 85/302: 172.16.12.2/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.2 255.255.0.0

echo Adding IP 86/302: 10.16.12.4/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.4 255.255.0.0

echo Adding IP 87/302: 172.16.12.4/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.4 255.255.0.0

echo Adding IP 88/302: 10.16.12.6/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.6 255.255.0.0

echo Adding IP 89/302: 172.16.12.6/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.6 255.255.0.0

echo Adding IP 90/302: 10.16.12.9/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB04, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.9 255.255.0.0

echo Adding IP 91/302: 172.16.12.9/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB04, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.9 255.255.0.0

echo Adding IP 92/302: 10.16.12.11/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB05, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.11 255.255.0.0

echo Adding IP 93/302: 172.16.12.11/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB05, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.11 255.255.0.0

echo Adding IP 94/302: 10.16.12.13/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB06, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.13 255.255.0.0

echo Adding IP 95/302: 172.16.12.13/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB06, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.13 255.255.0.0

echo Adding IP 96/302: 10.16.12.14/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB07, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.14 255.255.0.0

echo Adding IP 97/302: 172.16.12.14/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB07, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.14 255.255.0.0

echo Adding IP 98/302: 10.16.12.3/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB08, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.3 255.255.0.0

echo Adding IP 99/302: 172.16.12.3/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB08, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.3 255.255.0.0

echo Adding IP 100/302: 10.16.12.5/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB09, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.5 255.255.0.0

echo Adding IP 101/302: 172.16.12.5/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB09, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.5 255.255.0.0

echo Adding IP 102/302: 10.16.12.8/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB10, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.8 255.255.0.0

echo Adding IP 103/302: 172.16.12.8/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB10, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.8 255.255.0.0

echo Adding IP 104/302: 10.16.12.10/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB11, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.10 255.255.0.0

echo Adding IP 105/302: 172.16.12.10/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB11, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.10 255.255.0.0

echo Adding IP 106/302: 10.16.12.12/255.255.0.0 (SubNet: Interlock, IED: GPS02GCB12, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.12 255.255.0.0

echo Adding IP 107/302: 172.16.12.12/255.255.0.0 (SubNet: SCADA, IED: GPS02GCB12, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.12 255.255.0.0

echo Adding IP 108/302: 10.16.22.12/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC01UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.12 255.255.0.0

echo Adding IP 109/302: 172.16.22.12/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC01UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.12 255.255.0.0

echo Adding IP 110/302: 10.16.22.13/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC01UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.13 255.255.0.0

echo Adding IP 111/302: 172.16.22.13/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC01UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.13 255.255.0.0

echo Adding IP 112/302: 10.16.22.11/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC01UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.11 255.255.0.0

echo Adding IP 113/302: 172.16.22.11/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC01UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.11 255.255.0.0

echo Adding IP 114/302: 10.16.22.22/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC02UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.22 255.255.0.0

echo Adding IP 115/302: 172.16.22.22/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC02UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.22 255.255.0.0

echo Adding IP 116/302: 10.16.22.23/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC02UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.23 255.255.0.0

echo Adding IP 117/302: 172.16.22.23/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC02UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.23 255.255.0.0

echo Adding IP 118/302: 10.16.22.21/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC02UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.21 255.255.0.0

echo Adding IP 119/302: 172.16.22.21/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC02UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.21 255.255.0.0

echo Adding IP 120/302: 10.16.22.32/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC03UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.32 255.255.0.0

echo Adding IP 121/302: 172.16.22.32/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC03UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.32 255.255.0.0

echo Adding IP 122/302: 10.16.22.33/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC03UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.33 255.255.0.0

echo Adding IP 123/302: 172.16.22.33/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC03UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.33 255.255.0.0

echo Adding IP 124/302: 10.16.22.31/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC03UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.31 255.255.0.0

echo Adding IP 125/302: 172.16.22.31/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC03UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.31 255.255.0.0

echo Adding IP 126/302: 10.16.22.42/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC04UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.42 255.255.0.0

echo Adding IP 127/302: 172.16.22.42/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC04UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.42 255.255.0.0

echo Adding IP 128/302: 10.16.22.43/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC04UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.43 255.255.0.0

echo Adding IP 129/302: 172.16.22.43/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC04UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.43 255.255.0.0

echo Adding IP 130/302: 10.16.22.41/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC04UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.41 255.255.0.0

echo Adding IP 131/302: 172.16.22.41/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC04UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.41 255.255.0.0

echo Adding IP 132/302: 10.16.22.52/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC05UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.52 255.255.0.0

echo Adding IP 133/302: 172.16.22.52/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC05UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.52 255.255.0.0

echo Adding IP 134/302: 10.16.22.53/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC05UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.53 255.255.0.0

echo Adding IP 135/302: 172.16.22.53/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC05UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.53 255.255.0.0

echo Adding IP 136/302: 10.16.22.51/255.255.0.0 (SubNet: Interlock, IED: GPS02GPC05UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.22.51 255.255.0.0

echo Adding IP 137/302: 172.16.22.51/255.255.0.0 (SubNet: SCADA, IED: GPS02GPC05UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.22.51 255.255.0.0

echo Adding IP 138/302: 10.16.12.17/255.255.0.0 (SubNet: Interlock, IED: GPS02LBB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.17 255.255.0.0

echo Adding IP 139/302: 172.16.12.17/255.255.0.0 (SubNet: SCADA, IED: GPS02LBB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.17 255.255.0.0

echo Adding IP 140/302: 10.16.12.1/255.255.0.0 (SubNet: Interlock, IED: GPS02MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.12.1 255.255.0.0

echo Adding IP 141/302: 172.16.12.1/255.255.0.0 (SubNet: SCADA, IED: GPS02MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.12.1 255.255.0.0

echo Adding IP 142/302: 10.16.13.18/255.255.0.0 (SubNet: Interlock, IED: GPS03ECB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.18 255.255.0.0

echo Adding IP 143/302: 172.16.13.18/255.255.0.0 (SubNet: SCADA, IED: GPS03ECB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.18 255.255.0.0

echo Adding IP 144/302: 10.16.13.15/255.255.0.0 (SubNet: Interlock, IED: GPS03FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.15 255.255.0.0

echo Adding IP 145/302: 172.16.13.15/255.255.0.0 (SubNet: SCADA, IED: GPS03FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.15 255.255.0.0

echo Adding IP 146/302: 10.16.13.16/255.255.0.0 (SubNet: Interlock, IED: GPS03FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.16 255.255.0.0

echo Adding IP 147/302: 172.16.13.16/255.255.0.0 (SubNet: SCADA, IED: GPS03FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.16 255.255.0.0

echo Adding IP 148/302: 10.16.13.1/255.255.0.0 (SubNet: Interlock, IED: GPS03FCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.1 255.255.0.0

echo Adding IP 149/302: 172.16.13.1/255.255.0.0 (SubNet: SCADA, IED: GPS03FCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.1 255.255.0.0

echo Adding IP 150/302: 10.16.13.2/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.2 255.255.0.0

echo Adding IP 151/302: 172.16.13.2/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.2 255.255.0.0

echo Adding IP 152/302: 10.16.13.4/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.4 255.255.0.0

echo Adding IP 153/302: 172.16.13.4/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.4 255.255.0.0

echo Adding IP 154/302: 10.16.13.6/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.6 255.255.0.0

echo Adding IP 155/302: 172.16.13.6/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.6 255.255.0.0

echo Adding IP 156/302: 10.16.13.9/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB04, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.9 255.255.0.0

echo Adding IP 157/302: 172.16.13.9/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB04, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.9 255.255.0.0

echo Adding IP 158/302: 10.16.13.11/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB05, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.11 255.255.0.0

echo Adding IP 159/302: 172.16.13.11/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB05, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.11 255.255.0.0

echo Adding IP 160/302: 10.16.13.13/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB06, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.13 255.255.0.0

echo Adding IP 161/302: 172.16.13.13/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB06, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.13 255.255.0.0

echo Adding IP 162/302: 10.16.13.14/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB07, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.14 255.255.0.0

echo Adding IP 163/302: 172.16.13.14/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB07, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.14 255.255.0.0

echo Adding IP 164/302: 10.16.13.3/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB08, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.3 255.255.0.0

echo Adding IP 165/302: 172.16.13.3/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB08, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.3 255.255.0.0

echo Adding IP 166/302: 10.16.13.5/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB09, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.5 255.255.0.0

echo Adding IP 167/302: 172.16.13.5/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB09, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.5 255.255.0.0

echo Adding IP 168/302: 10.16.13.8/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB10, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.8 255.255.0.0

echo Adding IP 169/302: 172.16.13.8/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB10, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.8 255.255.0.0

echo Adding IP 170/302: 10.16.13.10/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB11, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.10 255.255.0.0

echo Adding IP 171/302: 172.16.13.10/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB11, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.10 255.255.0.0

echo Adding IP 172/302: 10.16.13.12/255.255.0.0 (SubNet: Interlock, IED: GPS03GCB12, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.12 255.255.0.0

echo Adding IP 173/302: 172.16.13.12/255.255.0.0 (SubNet: SCADA, IED: GPS03GCB12, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.12 255.255.0.0

echo Adding IP 174/302: 10.16.23.12/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC01UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.12 255.255.0.0

echo Adding IP 175/302: 172.16.23.12/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC01UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.12 255.255.0.0

echo Adding IP 176/302: 10.16.23.13/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC01UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.13 255.255.0.0

echo Adding IP 177/302: 172.16.23.13/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC01UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.13 255.255.0.0

echo Adding IP 178/302: 10.16.23.11/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC01UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.11 255.255.0.0

echo Adding IP 179/302: 172.16.23.11/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC01UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.11 255.255.0.0

echo Adding IP 180/302: 10.16.23.22/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC02UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.22 255.255.0.0

echo Adding IP 181/302: 172.16.23.22/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC02UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.22 255.255.0.0

echo Adding IP 182/302: 10.16.23.23/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC02UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.23 255.255.0.0

echo Adding IP 183/302: 172.16.23.23/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC02UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.23 255.255.0.0

echo Adding IP 184/302: 10.16.23.21/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC02UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.21 255.255.0.0

echo Adding IP 185/302: 172.16.23.21/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC02UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.21 255.255.0.0

echo Adding IP 186/302: 10.16.23.32/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC03UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.32 255.255.0.0

echo Adding IP 187/302: 172.16.23.32/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC03UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.32 255.255.0.0

echo Adding IP 188/302: 10.16.23.33/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC03UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.33 255.255.0.0

echo Adding IP 189/302: 172.16.23.33/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC03UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.33 255.255.0.0

echo Adding IP 190/302: 10.16.23.31/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC03UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.31 255.255.0.0

echo Adding IP 191/302: 172.16.23.31/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC03UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.31 255.255.0.0

echo Adding IP 192/302: 10.16.23.42/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC04UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.42 255.255.0.0

echo Adding IP 193/302: 172.16.23.42/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC04UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.42 255.255.0.0

echo Adding IP 194/302: 10.16.23.43/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC04UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.43 255.255.0.0

echo Adding IP 195/302: 172.16.23.43/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC04UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.43 255.255.0.0

echo Adding IP 196/302: 10.16.23.41/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC04UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.41 255.255.0.0

echo Adding IP 197/302: 172.16.23.41/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC04UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.41 255.255.0.0

echo Adding IP 198/302: 10.16.23.52/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC05UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.52 255.255.0.0

echo Adding IP 199/302: 172.16.23.52/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC05UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.52 255.255.0.0

echo Adding IP 200/302: 10.16.23.53/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC05UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.53 255.255.0.0

echo Adding IP 201/302: 172.16.23.53/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC05UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.53 255.255.0.0

echo Adding IP 202/302: 10.16.23.51/255.255.0.0 (SubNet: Interlock, IED: GPS03GPC05UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.23.51 255.255.0.0

echo Adding IP 203/302: 172.16.23.51/255.255.0.0 (SubNet: SCADA, IED: GPS03GPC05UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.23.51 255.255.0.0

echo Adding IP 204/302: 10.16.13.17/255.255.0.0 (SubNet: Interlock, IED: GPS03LBB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.13.17 255.255.0.0

echo Adding IP 205/302: 172.16.13.17/255.255.0.0 (SubNet: SCADA, IED: GPS03LBB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.13.17 255.255.0.0

echo Adding IP 206/302: 10.16.14.18/255.255.0.0 (SubNet: Interlock, IED: GPS04ECB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.18 255.255.0.0

echo Adding IP 207/302: 172.16.14.18/255.255.0.0 (SubNet: SCADA, IED: GPS04ECB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.18 255.255.0.0

echo Adding IP 208/302: 10.16.14.15/255.255.0.0 (SubNet: Interlock, IED: GPS04FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.15 255.255.0.0

echo Adding IP 209/302: 172.16.14.15/255.255.0.0 (SubNet: SCADA, IED: GPS04FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.15 255.255.0.0

echo Adding IP 210/302: 10.16.14.16/255.255.0.0 (SubNet: Interlock, IED: GPS04FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.16 255.255.0.0

echo Adding IP 211/302: 172.16.14.16/255.255.0.0 (SubNet: SCADA, IED: GPS04FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.16 255.255.0.0

echo Adding IP 212/302: 10.16.14.1/255.255.0.0 (SubNet: Interlock, IED: GPS04FCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.1 255.255.0.0

echo Adding IP 213/302: 172.16.14.1/255.255.0.0 (SubNet: SCADA, IED: GPS04FCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.1 255.255.0.0

echo Adding IP 214/302: 10.16.14.2/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.2 255.255.0.0

echo Adding IP 215/302: 172.16.14.2/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.2 255.255.0.0

echo Adding IP 216/302: 10.16.14.4/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.4 255.255.0.0

echo Adding IP 217/302: 172.16.14.4/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.4 255.255.0.0

echo Adding IP 218/302: 10.16.14.6/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB03, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.6 255.255.0.0

echo Adding IP 219/302: 172.16.14.6/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB03, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.6 255.255.0.0

echo Adding IP 220/302: 10.16.14.9/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB04, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.9 255.255.0.0

echo Adding IP 221/302: 172.16.14.9/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB04, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.9 255.255.0.0

echo Adding IP 222/302: 10.16.14.11/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB05, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.11 255.255.0.0

echo Adding IP 223/302: 172.16.14.11/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB05, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.11 255.255.0.0

echo Adding IP 224/302: 10.16.14.13/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB06, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.13 255.255.0.0

echo Adding IP 225/302: 172.16.14.13/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB06, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.13 255.255.0.0

echo Adding IP 226/302: 10.16.14.14/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB07, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.14 255.255.0.0

echo Adding IP 227/302: 172.16.14.14/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB07, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.14 255.255.0.0

echo Adding IP 228/302: 10.16.14.3/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB08, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.3 255.255.0.0

echo Adding IP 229/302: 172.16.14.3/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB08, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.3 255.255.0.0

echo Adding IP 230/302: 10.16.14.5/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB09, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.5 255.255.0.0

echo Adding IP 231/302: 172.16.14.5/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB09, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.5 255.255.0.0

echo Adding IP 232/302: 10.16.14.8/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB10, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.8 255.255.0.0

echo Adding IP 233/302: 172.16.14.8/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB10, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.8 255.255.0.0

echo Adding IP 234/302: 10.16.14.10/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB11, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.10 255.255.0.0

echo Adding IP 235/302: 172.16.14.10/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB11, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.10 255.255.0.0

echo Adding IP 236/302: 10.16.14.12/255.255.0.0 (SubNet: Interlock, IED: GPS04GCB12, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.12 255.255.0.0

echo Adding IP 237/302: 172.16.14.12/255.255.0.0 (SubNet: SCADA, IED: GPS04GCB12, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.12 255.255.0.0

echo Adding IP 238/302: 10.16.24.12/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC01UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.12 255.255.0.0

echo Adding IP 239/302: 172.16.24.12/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC01UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.12 255.255.0.0

echo Adding IP 240/302: 10.16.24.13/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC01UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.13 255.255.0.0

echo Adding IP 241/302: 172.16.24.13/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC01UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.13 255.255.0.0

echo Adding IP 242/302: 10.16.24.11/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC01UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.11 255.255.0.0

echo Adding IP 243/302: 172.16.24.11/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC01UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.11 255.255.0.0

echo Adding IP 244/302: 10.16.24.22/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC02UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.22 255.255.0.0

echo Adding IP 245/302: 172.16.24.22/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC02UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.22 255.255.0.0

echo Adding IP 246/302: 10.16.24.23/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC02UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.23 255.255.0.0

echo Adding IP 247/302: 172.16.24.23/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC02UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.23 255.255.0.0

echo Adding IP 248/302: 10.16.24.21/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC02UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.21 255.255.0.0

echo Adding IP 249/302: 172.16.24.21/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC02UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.21 255.255.0.0

echo Adding IP 250/302: 10.16.24.32/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC03UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.32 255.255.0.0

echo Adding IP 251/302: 172.16.24.32/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC03UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.32 255.255.0.0

echo Adding IP 252/302: 10.16.24.33/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC03UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.33 255.255.0.0

echo Adding IP 253/302: 172.16.24.33/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC03UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.33 255.255.0.0

echo Adding IP 254/302: 10.16.24.31/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC03UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.31 255.255.0.0

echo Adding IP 255/302: 172.16.24.31/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC03UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.31 255.255.0.0

echo Adding IP 256/302: 10.16.24.42/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC04UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.42 255.255.0.0

echo Adding IP 257/302: 172.16.24.42/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC04UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.42 255.255.0.0

echo Adding IP 258/302: 10.16.24.43/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC04UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.43 255.255.0.0

echo Adding IP 259/302: 172.16.24.43/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC04UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.43 255.255.0.0

echo Adding IP 260/302: 10.16.24.41/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC04UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.41 255.255.0.0

echo Adding IP 261/302: 172.16.24.41/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC04UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.41 255.255.0.0

echo Adding IP 262/302: 10.16.24.52/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC05UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.52 255.255.0.0

echo Adding IP 263/302: 172.16.24.52/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC05UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.52 255.255.0.0

echo Adding IP 264/302: 10.16.24.53/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC05UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.53 255.255.0.0

echo Adding IP 265/302: 172.16.24.53/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC05UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.53 255.255.0.0

echo Adding IP 266/302: 10.16.24.51/255.255.0.0 (SubNet: Interlock, IED: GPS04GPC05UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.24.51 255.255.0.0

echo Adding IP 267/302: 172.16.24.51/255.255.0.0 (SubNet: SCADA, IED: GPS04GPC05UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.24.51 255.255.0.0

echo Adding IP 268/302: 10.16.14.17/255.255.0.0 (SubNet: Interlock, IED: GPS04LBB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.14.17 255.255.0.0

echo Adding IP 269/302: 172.16.14.17/255.255.0.0 (SubNet: SCADA, IED: GPS04LBB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.14.17 255.255.0.0

echo Adding IP 270/302: 10.16.25.12/255.255.0.0 (SubNet: Interlock, IED: GPSXXGPC01UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.25.12 255.255.0.0

echo Adding IP 271/302: 172.16.25.12/255.255.0.0 (SubNet: SCADA, IED: GPSXXGPC01UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.12 255.255.0.0

echo Adding IP 272/302: 10.16.25.13/255.255.0.0 (SubNet: Interlock, IED: GPSXXGPC01UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.25.13 255.255.0.0

echo Adding IP 273/302: 172.16.25.13/255.255.0.0 (SubNet: SCADA, IED: GPSXXGPC01UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.13 255.255.0.0

echo Adding IP 274/302: 10.16.25.11/255.255.0.0 (SubNet: Interlock, IED: GPSXXGPC01UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.25.11 255.255.0.0

echo Adding IP 275/302: 172.16.25.11/255.255.0.0 (SubNet: SCADA, IED: GPSXXGPC01UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.11 255.255.0.0

echo Adding IP 276/302: 10.16.25.22/255.255.0.0 (SubNet: Interlock, IED: GPSXXGPC02UPM01FCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.25.22 255.255.0.0

echo Adding IP 277/302: 172.16.25.22/255.255.0.0 (SubNet: SCADA, IED: GPSXXGPC02UPM01FCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.22 255.255.0.0

echo Adding IP 278/302: 10.16.25.23/255.255.0.0 (SubNet: Interlock, IED: GPSXXGPC02UPM01FCB02, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.25.23 255.255.0.0

echo Adding IP 279/302: 172.16.25.23/255.255.0.0 (SubNet: SCADA, IED: GPSXXGPC02UPM01FCB02, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.23 255.255.0.0

echo Adding IP 280/302: 10.16.25.21/255.255.0.0 (SubNet: Interlock, IED: GPSXXGPC02UPM01MCB01, AP: E, Protocol: GOOSE, RedProt: HSR)
netsh interface ip add address "Ethernet 5" 10.16.25.21 255.255.0.0

echo Adding IP 281/302: 172.16.25.21/255.255.0.0 (SubNet: SCADA, IED: GPSXXGPC02UPM01MCB01, AP: F, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.25.21 255.255.0.0

echo Adding IP 282/302: 172.16.67.1/255.255.0.0 (SubNet: SCADA, IED: UPM02ADMIN, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.1 255.255.0.0

echo Adding IP 283/302: 172.16.67.2/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO1C1, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.2 255.255.0.0

echo Adding IP 284/302: 172.16.67.3/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO1C2, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.3 255.255.0.0

echo Adding IP 285/302: 172.16.67.4/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO1C3, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.4 255.255.0.0

echo Adding IP 286/302: 172.16.67.5/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO1C4, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.5 255.255.0.0

echo Adding IP 287/302: 172.16.67.6/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO2C1, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.6 255.255.0.0

echo Adding IP 288/302: 172.16.67.7/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO2C2, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.7 255.255.0.0

echo Adding IP 289/302: 172.16.67.8/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO2C3, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.8 255.255.0.0

echo Adding IP 290/302: 172.16.67.9/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO2C4, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.9 255.255.0.0

echo Adding IP 291/302: 172.16.67.10/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO3C1, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.10 255.255.0.0

echo Adding IP 292/302: 172.16.67.11/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO3C2, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.11 255.255.0.0

echo Adding IP 293/302: 172.16.67.12/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO3C3, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.12 255.255.0.0

echo Adding IP 294/302: 172.16.67.13/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO3C4, AP: E, Protocol: MMS+GOOSE, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.13 255.255.0.0

echo Adding IP 295/302: 172.16.67.14/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO4C1, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.14 255.255.0.0

echo Adding IP 296/302: 172.16.67.15/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO4C2, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.15 255.255.0.0

echo Adding IP 297/302: 172.16.67.16/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO4C3, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.16 255.255.0.0

echo Adding IP 298/302: 172.16.67.17/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO4C4, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.17 255.255.0.0

echo Adding IP 299/302: 172.16.67.18/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO5C1, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.18 255.255.0.0

echo Adding IP 300/302: 172.16.67.19/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO5C2, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.19 255.255.0.0

echo Adding IP 301/302: 172.16.67.20/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO5C3, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.20 255.255.0.0

echo Adding IP 302/302: 172.16.67.21/255.255.0.0 (SubNet: SCADA, IED: UPM02COLO5C4, AP: E, Protocol: MMS, RedProt: PRP)
netsh interface ip add address "Ethernet 5" 172.16.67.21 255.255.0.0

echo.
echo All IP addresses have been added.
echo Press any key to view current IP configuration...
pause >nul
ipconfig | findstr /C:"Ethernet 5"
pause
