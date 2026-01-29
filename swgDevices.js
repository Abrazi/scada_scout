// Host and workspace setup
var host = "DTHost";
var ws = FindNode("/");

// Create folders

var swgFolder = AddFolder(ws, "SWG");

// IP mapping from Excel
var ipMap = {
  "GPS1": "172.16.31.63", "GPS2": "172.16.32.63", "GPS3": "172.16.33.63", "GPS4": "172.16.34.63"
};

// Path to the register CSV file
var csvFileName = "Gen_Registers.csv";
var csvFilePath = scriptPath + "\\" + csvFileName;
var registerCsvPath = csvFilePath ; // <-- Update this path as needed


// Function to create a basic switchgear slave (no CSV needed)
function createSwgSlave(folder, swgId, ip) {
  //var deviceName = "sMB_" + swgId;
  var deviceName = swgId;
    print("Creating Modbus Slave for Switchgear: " + swgId + " @ " + ip);

    var dCfg = CreateDeviceConfig();
    dCfg.DeviceName = deviceName;
    dCfg.HostName = host;
    var device = AddDevice(folder, dCfg);

    var cCfg = MBCreateOutstationChannelConfig();
    cCfg.ChannelName = "sMB";
    cCfg.TCP.LocalIP = ip;
    cCfg.TCP.RemoteIPsAsArray = ["*.*.*.*"];
    cCfg.TCP.Port = 502;
    var channel = MBAddChannel(device, cCfg);

    var sCfg = SMBCreateSessionConfig();
    sCfg.SessionName = "sMB";
    var session = SMBAddSession(channel, sCfg);

    return device;
}


// Create switchgear slaves (GPS1–GPS4)
for (var j = 1; j <= 4; j++) {
    var swgId = "GPS" + j;
    createSwgSlave(swgFolder, swgId, ipMap[swgId]);
}

print("All Modbus Slaves created with registers and IP addresses.");
