// Curated, friendly versions. Edit when a new release branch/tag is cut.
export const VERSIONS = [
  { label: "Stable — May 2026", ref: "May_2026", recommended: true },
  { label: "Beta — June 2026", ref: "June_2026" },
  { label: "Jan 2026", ref: "beta_January_2026" },
];

export const REPO = { owner: "tuftsceeo", repo: "SmartPlayground" };

// Device runtime config. File lists live in manifests/*.yml — edit those to change what flashes.
export const DEVICES = [
  {
    id: "wand",
    label: "Wand",
    icon: "wand-sparkles",
    blurb: "XIAO ESP32-C6 game wand",
    manifest: "wand.yml",
    hubTypeValue: "wand",
    devicePathRoot: "/",
    baudRate: 115200,
    writeHubType: false, // hubtype.txt ships from repo via manifest
    preserveFiles: ["hubName.txt"],
    hubConfig: false,
  },
  {
    id: "hub",
    label: "Hub (USB bridge)",
    icon: "router",
    blurb: "ESP32 USB bridge for Live Page Wands",
    manifest: "hub.yml",
    hubTypeValue: null,
    devicePathRoot: "/",
    baudRate: 115200,
    writeHubType: false,
    preserveFiles: [],
    hubConfig: true,
  },
  {
    id: "m5paper",
    label: "M5Paper Remote",
    icon: "tablet",
    blurb: "M5Paper e-ink teacher remote",
    manifest: "m5paper.yml",
    hubTypeValue: null,
    devicePathRoot: "/flash/",
    baudRate: 115200,
    writeHubType: false,
    preserveFiles: ["settings.json"],
    hubConfig: false,
  },
];

export function getDeviceById(id) {
  return DEVICES.find((d) => d.id === id) ?? null;
}

export function getDeviceByHubType(hubType) {
  if (!hubType) return null;
  return DEVICES.find((d) => d.hubTypeValue === hubType) ?? null;
}
