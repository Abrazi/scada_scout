// Host and workspace setup
var host = "DTHost";
var ws = FindNode("/");

// Create folders
var genFolder = AddFolder(ws, "GEN");


// IP mapping from Excel
var ipMap = {
  "G1": "172.16.31.13", "G2": "172.16.31.23", "G3": "172.16.31.33", "G4": "172.16.31.43", "G5": "172.16.31.53",
  "G6": "172.16.32.13", "G7": "172.16.32.23", "G8": "172.16.32.33", "G9": "172.16.32.43", "G10": "172.16.32.53",
  "G11": "172.16.33.13", "G12": "172.16.33.23", "G13": "172.16.33.33", "G14": "172.16.33.43", "G15": "172.16.33.53",
  "G16": "172.16.34.13", "G17": "172.16.34.23", "G18": "172.16.34.33", "G19": "172.16.34.43", "G20": "172.16.34.53",
  "G21": "172.16.35.13", "G22": "172.16.35.23",

};

// Path to the register CSV file
var csvFileName = "Gen_Registers.csv";
var csvFilePath = scriptPath + "\\" + csvFileName;
var registerCsvPath = csvFilePath ; // <-- Update this path as needed

// Function to create a generator slave with CSV-based register import
function createGenSlave(folder, genId, ip) {
    var deviceName = genId;
    print("Creating Modbus Slave for Generator: " + genId + " @ " + ip);

    var dCfg = CreateDeviceConfig();
    dCfg.DeviceName = deviceName;
    dCfg.HostName = host;
    var device = AddDevice(folder, dCfg);

    var cCfg = MBCreateOutstationChannelConfig();
    cCfg.ChannelName = "sMB" ;
    cCfg.TCP.LocalIP = ip;
    cCfg.TCP.RemoteIPsAsArray = ["*.*.*.*"];
    cCfg.TCP.Port = 502;
    var channel = MBAddChannel(device, cCfg);

    var sCfg = SMBCreateSessionConfig();
    sCfg.SessionName = "sMB";

    // Use SMBAddSessionEx to load the register database
    var session = SMBAddSessionEx(channel, sCfg, registerCsvPath);

    return device;
}


// Create generator slaves (G1–G22)
for (var i = 1; i <= 22; i++) {
    var genId = "G" + i;
    createGenSlave(genFolder, genId, ipMap[genId]);
}


print("All Modbus Slaves created with registers and IP addresses.");
