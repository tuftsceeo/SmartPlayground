/**
 * Hub board detection and main.py patching — lifted from hubSetupModal.js.
 */

export function parseDeviceType(info) {
  if (!info) return null;
  const infoUpper = info.toUpperCase();
  if (infoUpper.includes("ESP32-C6") || infoUpper.includes("ESP32C6")) return "C6";
  if (infoUpper.includes("ESP32-C3") || infoUpper.includes("ESP32C3")) return "C3";
  if (infoUpper.includes("ESP32-S3") || infoUpper.includes("ESP32S3")) return "S3";
  if (infoUpper.includes("ESP32-S2") || infoUpper.includes("ESP32S2")) return "S2";
  if (infoUpper.includes("ESP32")) return "ESP32";
  return "Unknown";
}

export function applyHubMainPyPatches(content, deviceType, hasExternalAntenna) {
  let patched = content;

  if (!hasExternalAntenna) {
    patched = patched.replace(
      /(# __ANTENNA_CONFIG_START__\s*\n\s*antenna_enabled = )True(\s*# C6 external antenna \(set to False for internal\)\s*\n\s*# __ANTENNA_CONFIG_END__)/,
      "$1False$2"
    );
  }

  if (deviceType === "C3") {
    patched = patched.replace(
      /i2c = I2C\(scl=Pin\(23\), sda=Pin\(22\)\)  # __DISPLAY_CONFIG_C6__\s*\n\s*# i2c = SoftI2C\(scl=Pin\(7\), sda=Pin\(6\)\)  # __DISPLAY_CONFIG_C3__/,
      "# i2c = I2C(scl=Pin(23), sda=Pin(22))  # __DISPLAY_CONFIG_C6__\n            i2c = SoftI2C(scl=Pin(7), sda=Pin(6))  # __DISPLAY_CONFIG_C3__"
    );
  }

  return patched;
}

export function showAntennaOption(deviceType) {
  return deviceType === "C6";
}
