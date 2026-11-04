/**
 * Icons the Maker offers to open: the saved device icons in defaultIcons.js
 * (generated from Stations/IconDisplay/icons/ by tools/sync_icons.py).
 *
 * This used to list the source photos in assets/, reconverted on open. Those
 * conversions predate the current designs and the measured white, so they are
 * no longer offered; assets/ and maps/ stay on disk for reference only.
 *
 * One list, three readers: main.js's loadFixture(), the top bar's picker and
 * the ChatBroadcast sample library.
 */
import { DEFAULT_ICONS } from "../../js/ledicons/defaultIcons.js";

export const FIXTURES = Object.keys(DEFAULT_ICONS).sort();
