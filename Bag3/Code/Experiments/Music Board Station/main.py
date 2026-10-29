"""
Music Board Station: entry point.

The radio must claim its contiguous IDF DRAM before anything else
allocates (see AGENTS.md and docs_and_design/2026-09-23-ap-memory-order.md),
so ESP-NOW comes up first and every other module is imported after it.
"""

import sys
sys.path.append('/lib')

from espnow_manager import ESPNowManager

enow = ESPNowManager()
enow.init()

import music_board

music_board.MusicBoard(enow).run()
