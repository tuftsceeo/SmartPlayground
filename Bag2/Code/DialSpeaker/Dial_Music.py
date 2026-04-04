# SPDX-FileCopyrightText: 2026
# SPDX-License-Identifier: MIT
#
# Musical Chairs Controller
# M5Stack Dial + AudioPlayer Unit (LVGL / M5UI)
# With ESP-NOW remote control support
#
# Designed for kindergarten classroom use on a 240px round display.
#
# Two-screen flow:
#   SELECT screen -> Browse songs with dial, tap to select
#   PLAYER screen -> Play/Pause with big center button, Close to go back
#
# ESP-NOW commands:
#   "FD_GO"     -> Start or resume playing
#   "FD_FREEZE" -> Pause playback
#   "stop"      -> Close back to select screen
#
# Controls:
#   Dial   -> Browse songs (select screen) / adjust volume (player screen)
#   BtnA   -> Same as big center button
#
# Available LVGL fonts: montserrat_14, montserrat_16, montserrat_24
# Available LVGL symbols: PLAY, PAUSE, STOP, PREV, NEXT, CLOSE, etc.
#
# SD Card / Filename limitation:
#   The AudioPlayer Unit firmware does NOT support FAT32 Long File Names (LFN).
#   It returns only the 8.3 short name (e.g. "FETCH~24" instead of the full title).
#   All audio files on the SD card MUST be named with 8 characters or fewer,
#   no spaces, and no special characters (apostrophes, commas, exclamation marks, etc.)
#   to avoid the FAT32 ~N alias being shown on screen instead of the real name.
#   Example good names: DanTigr.wav, GoodFeel.wav, Sakura.mp3

import os
import sys
import io
import M5
from M5 import *
from hardware import *
from hardware import Rotary
from unit import AudioPlayerUnit
import m5ui
import lvgl as lv
import time
import network
import espnow


# ══════════════════════════════════════════════
# AudioController
# ══════════════════════════════════════════════
class AudioController:
    """Manages all UART communication with the AudioPlayer unit."""

    MODE_SINGLE_LOOP = 1
    DEBOUNCE_MS = 400

    def __init__(self, uart_id=1, port=(1, 2), init_delay_s=2):
        self._player = AudioPlayerUnit(uart_id, port=port)
        time.sleep(init_delay_s)
        self._last_cmd_time = 0

    def _debounce_ok(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_cmd_time) < self.DEBOUNCE_MS:
            return False
        self._last_cmd_time = now
        return True

    def set_volume(self, level):
        self._player.set_volume(level)

    def set_play_mode(self, mode):
        self._player.set_play_mode(mode)

    def play_by_index(self, index):
        if not self._debounce_ok():
            return False
        self._player.play_audio_by_index(index)
        return True

    def pause(self):
        if not self._debounce_ok():
            return False
        self._player.pause_audio()
        return True

    def resume(self):
        if not self._debounce_ok():
            return False
        self._player.play_audio()
        return True

    def stop(self):
        if not self._debounce_ok():
            return False
        self._player.stop_audio()
        return True

    def get_total_files(self):
        count = self._player.get_total_audio_number()
        return count if count and count >= 1 else 0

    def read_file_name(self, index):
        try:
            self._player.select_audio_num(index)
            time.sleep_ms(40)
            raw = self._player.get_file_name()
            # #region agent log
            print("[DBG-34562d][RAW] index=", index, "type=", type(raw).__name__,
                  "repr=", repr(raw))
            if isinstance(raw, (list, bytes, bytearray)):
                print("[DBG-34562d][RAW] hex=", [hex(b) for b in bytes(raw)])
            # #endregion
            if isinstance(raw, (list, bytes, bytearray)):
                return bytes(raw).decode("utf-8", "replace").rstrip("\x00")
            return str(raw)
        except Exception as e:
            # #region agent log
            print("[DBG-34562d][RAW] index=", index, "EXCEPTION:", type(e).__name__, e)
            # #endregion
            return "Track " + str(index)

    def reset_selection(self, index=1):
        self._player.select_audio_num(index)


# ══════════════════════════════════════════════
# RemoteControl
# ══════════════════════════════════════════════
class RemoteControl:
    """ESP-NOW receiver for remote commands.

    Listens for broadcast messages and translates them into
    game actions. Non-blocking: call poll() in the main loop.
    """

    def __init__(self):
        """Initialize ESP-NOW in station mode with broadcast peer."""
        try:
          wlan.disconnect()  # Disconnect from Access Point
          wlan.active(False)
        except:
          print("wifi disconnect")
        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)
        # #region agent log
        print("[DBG-34562d][H-F] BEFORE disconnect: ch=", self._wlan.config('channel'),
              "connected=", self._wlan.isconnected())
        # #endregion
        self._wlan.disconnect()
        # #region agent log
        print("[DBG-34562d][H-F] AFTER disconnect: ch=", self._wlan.config('channel'),
              "connected=", self._wlan.isconnected())
        # #endregion
        self._esp = espnow.ESPNow()
        self._esp.active(True)
        self._esp.add_peer(b'\xff\xff\xff\xff\xff\xff')
        # #region agent log
        print("[DBG-34562d][H-F] espnow active:", self._esp.active(),
              "final ch=", self._wlan.config('channel'))
        # #endregion

    def poll(self):
        """Drain all pending messages and return the last command string.

        Returns None if no messages were waiting. Only the most
        recent command matters (older ones are stale).
        """
        last_cmd = None
        try:
            while True:
                host, msg = self._esp.recv(0)
                
                if msg is None:
                    break
                # #region agent log
                print("[DBG-34562d][H-B] recv raw:", msg, "from:", host)
                # #endregion
                last_cmd = msg.decode().strip()
                # #region agent log
                print("[DBG-34562d][H-B] decoded cmd:", last_cmd)
                # #endregion
        except Exception as e:
            # #region agent log
            print("[DBG-34562d][H-B] poll() EXCEPTION:", type(e).__name__, e)
            # #endregion
        return last_cmd


# ══════════════════════════════════════════════
# GameState
# ══════════════════════════════════════════════
class GameState:
    """Tracks play state, song selection, volume, and file list.

    Two modes:
      BROWSING  - User is on the select screen choosing a song
      IN_PLAYER - User has selected a song and is on the player screen
                  (can be PLAYING or PAUSED within this mode)
    """

    # Player sub-states
    PLAYING = 1
    PAUSED = 2

    def __init__(self, audio):
        self.audio = audio
        self.in_player = False      # False = select screen, True = player screen
        self.is_playing = False     # True = audio actively playing
        self.current_index = 1
        self.volume = 15
        self.file_names = []
        self.total_files = 0
        self._on_change = None

    def set_change_callback(self, cb):
        self._on_change = cb

    def _notify(self):
        if self._on_change:
            self._on_change()

    # ── Initialization ──

    def load_files(self):
        self.total_files = self.audio.get_total_files()
        self.file_names = []
        for i in range(1, self.total_files + 1):
            self.file_names.append(self.audio.read_file_name(i))
        if self.total_files > 0:
            self.audio.reset_selection(1)
        self.current_index = 1

    def configure(self):
        self.audio.set_volume(self.volume)
        self.audio.set_play_mode(AudioController.MODE_SINGLE_LOOP)

    # ── Song info ──

    def get_display_name(self):
        if self.current_index < 1 or self.current_index > len(self.file_names):
            return "---"
        name = self.file_names[self.current_index - 1]
        dot = name.rfind(".")
        if dot > 0:
            name = name[:dot]
        if len(name) > 14:
            name = name[:11] + "..."
        return name

    def get_index_text(self):
        if self.total_files == 0:
            return ""
        return str(self.current_index) + " / " + str(self.total_files)

    # ── Navigation (select screen only) ──

    def select_next(self):
        if self.total_files == 0 or self.in_player:
            return
        self.current_index += 1
        if self.current_index > self.total_files:
            self.current_index = 1
        self._notify()

    def select_prev(self):
        if self.total_files == 0 or self.in_player:
            return
        self.current_index -= 1
        if self.current_index < 1:
            self.current_index = self.total_files
        self._notify()

    # ── Screen transitions ──

    def enter_player(self):
        """Transition from select screen to player screen and start playing."""
        if self.total_files == 0:
            return
        self.in_player = True
        self.audio.set_play_mode(AudioController.MODE_SINGLE_LOOP)
        if self.audio.play_by_index(self.current_index):
            self.is_playing = True
        self._notify()

    def close_player(self):
        """Stop playback and return to select screen."""
        self.audio.stop()
        self.is_playing = False
        self.in_player = False
        self._notify()

    # ── Playback actions (player screen only) ──

    def play(self):
        """Start or resume playback."""
        if not self.in_player:
            # If on select screen, enter player first
            self.enter_player()
            return
        if self.is_playing:
            return
        if self.audio.resume():
            self.is_playing = True
            self._notify()

    def pause(self):
        """Pause playback."""
        if not self.in_player or not self.is_playing:
            return
        if self.audio.pause():
            self.is_playing = False
            self._notify()

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if not self.in_player:
            self.enter_player()
        elif self.is_playing:
            self.pause()
        else:
            self.play()

    # ── Volume ──

    def adjust_volume(self, delta):
        self.volume = max(0, min(30, self.volume + delta))
        self.audio.set_volume(self.volume)
        self._notify()

    # ── ESP-NOW command handler ──

    def handle_remote_command(self, cmd):
        """Process a command string from the ESP-NOW remote."""
        if cmd == "FD_GO":
            self.play()
        elif cmd == "FD_FREEZE":
            self.pause()
        elif cmd == "stop":
            self.close_player()


# ══════════════════════════════════════════════
# PlayerUI  (round-screen, two-screen flow)
# ══════════════════════════════════════════════
class PlayerUI:
    """LVGL interface for a 240px circular display.

    Two screens:
      SELECT - Song name centered, prev/next arrows, SELECT button
      PLAYER - Big play/pause button, song name, close button

    Volume popup appears briefly when the dial is turned during playback.
    """

    CX = 120
    CY = 120
    VOL_POPUP_DURATION_MS = 1500

    def __init__(self, game):
        self.game = game
        self.game.set_change_callback(self.refresh)
        self._vol_popup_visible = False
        self._vol_popup_hide_time = 0
        self._build_select_screen()
        self._build_player_screen()
        self._show_select()

    # ════════════════════════════════════════
    # SELECT screen
    # ════════════════════════════════════════
    def _build_select_screen(self):
        """Song browser screen."""
        self.pg_select = m5ui.M5Page(bg_c=0xFFFFFF)

        # Song name (centered, upper area)
        self.sel_lbl_song = m5ui.M5Label(
            "Loading...",
            x=20, y=50,
            text_c=0x333333, bg_c=0xFFFFFF, bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.pg_select
        )
        self.sel_lbl_song.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.sel_lbl_song.set_width(200)
        self.sel_lbl_song.align(lv.ALIGN.TOP_MID, 0, 50)

        # Index counter
        self.sel_lbl_index = m5ui.M5Label(
            "",
            x=90, y=75,
            text_c=0xAAAAAA, bg_c=0xFFFFFF, bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.pg_select
        )
        self.sel_lbl_index.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.sel_lbl_index.set_width(60)
        self.sel_lbl_index.align(lv.ALIGN.TOP_MID, 0, 75)

        # Prev arrow (circular, left of center)
        self.sel_btn_prev = m5ui.M5Button(
            text=lv.SYMBOL.PREV,
            x=20, y=100, w=50, h=50,
            bg_c=0x90CAF9, text_c=0xFFFFFF,
            font=lv.font_montserrat_16,
            parent=self.pg_select
        )
        self.sel_btn_prev.set_style_radius(25, 0)
        self.sel_btn_prev.set_style_border_width(0, 0)
        self.sel_btn_prev.add_event_cb(
            self._on_sel_prev, lv.EVENT.CLICKED, None
        )

        # SELECT button (big, center)
        self.sel_btn_go = m5ui.M5Button(
            text="SELECT",
            x=78, y=95, w=84, h=60,
            bg_c=0x1976D2, text_c=0xFFFFFF,
            font=lv.font_montserrat_16,
            parent=self.pg_select
        )
        self.sel_btn_go.set_style_radius(30, 0)
        self.sel_btn_go.set_style_border_width(0, 0)
        self.sel_btn_go.set_style_shadow_width(10, 0)
        self.sel_btn_go.set_style_shadow_color(lv.color_hex(0x999999), 0)
        self.sel_btn_go.set_style_shadow_opa(60, 0)
        self.sel_btn_go.add_event_cb(
            self._on_sel_go, lv.EVENT.CLICKED, None
        )

        # Next arrow (circular, right of center)
        self.sel_btn_next = m5ui.M5Button(
            text=lv.SYMBOL.NEXT,
            x=170, y=100, w=50, h=50,
            bg_c=0x90CAF9, text_c=0xFFFFFF,
            font=lv.font_montserrat_16,
            parent=self.pg_select
        )
        self.sel_btn_next.set_style_radius(25, 0)
        self.sel_btn_next.set_style_border_width(0, 0)
        self.sel_btn_next.add_event_cb(
            self._on_sel_next, lv.EVENT.CLICKED, None
        )

        # Hint text at bottom
        self.sel_lbl_hint = m5ui.M5Label(
            "Turn dial to browse",
            x=40, y=175,
            text_c=0xBBBBBB, bg_c=0xFFFFFF, bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.pg_select
        )
        self.sel_lbl_hint.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.sel_lbl_hint.set_width(160)
        self.sel_lbl_hint.align(lv.ALIGN.TOP_MID, 0, 175)

    # ════════════════════════════════════════
    # PLAYER screen
    # ════════════════════════════════════════
    def _build_player_screen(self):
        """Now-playing screen with play/pause and close."""
        self.pg_player = m5ui.M5Page(bg_c=0xFFFFFF)

        # Song name (top)
        self.pl_lbl_song = m5ui.M5Label(
            "",
            x=20, y=28,
            text_c=0x333333, bg_c=0xFFFFFF, bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.pg_player
        )
        self.pl_lbl_song.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.pl_lbl_song.set_width(200)
        self.pl_lbl_song.align(lv.ALIGN.TOP_MID, 0, 28)

        # Big play/pause button (center, large circle)
        self.pl_btn_main = m5ui.M5Button(
            text=lv.SYMBOL.PAUSE,
            x=70, y=60, w=100, h=100,
            bg_c=0x43A047, text_c=0xFFFFFF,
            font=lv.font_montserrat_24,
            parent=self.pg_player
        )
        self.pl_btn_main.set_style_radius(50, 0)
        self.pl_btn_main.set_style_border_width(0, 0)
        self.pl_btn_main.set_style_shadow_width(14, 0)
        self.pl_btn_main.set_style_shadow_color(lv.color_hex(0x888888), 0)
        self.pl_btn_main.set_style_shadow_opa(90, 0)
        self.pl_btn_main.add_event_cb(
            self._on_pl_main, lv.EVENT.CLICKED, None
        )

        # Close button (below, wider, clearly separated)
        self.pl_btn_close = m5ui.M5Button(
            text=lv.SYMBOL.CLOSE + " CLOSE",
            x=55, y=175, w=130, h=40,
            bg_c=0x757575, text_c=0xFFFFFF,
            font=lv.font_montserrat_14,
            parent=self.pg_player
        )
        self.pl_btn_close.set_style_radius(20, 0)
        self.pl_btn_close.set_style_border_width(0, 0)
        self.pl_btn_close.add_event_cb(
            self._on_pl_close, lv.EVENT.CLICKED, None
        )

        # Volume popup (hidden by default, shows briefly on dial turn)
        self.pl_lbl_vol = m5ui.M5Label(
            "",
            x=70, y=30,
            text_c=0xFFFFFF, bg_c=0x333333, bg_opa=220,
            font=lv.font_montserrat_24,
            parent=self.pg_player
        )
        self.pl_lbl_vol.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.pl_lbl_vol.set_width(100)
        self.pl_lbl_vol.set_style_radius(12, 0)
        self.pl_lbl_vol.set_style_pad_top(6, 0)
        self.pl_lbl_vol.set_style_pad_bottom(6, 0)
        self.pl_lbl_vol.align(lv.ALIGN.TOP_MID, 0, 30)
        self.pl_lbl_vol.add_flag(lv.obj.FLAG.HIDDEN)

    # ── Screen switching ──

    def _show_select(self):
        self.pg_select.screen_load()

    def _show_player(self):
        self.pg_player.screen_load()

    # ── SELECT screen callbacks ──

    def _on_sel_prev(self, event_struct):
        if event_struct.code == lv.EVENT.CLICKED:
            self.game.select_prev()

    def _on_sel_next(self, event_struct):
        if event_struct.code == lv.EVENT.CLICKED:
            self.game.select_next()

    def _on_sel_go(self, event_struct):
        if event_struct.code == lv.EVENT.CLICKED:
            self.game.enter_player()

    # ── PLAYER screen callbacks ──

    def _on_pl_main(self, event_struct):
        if event_struct.code == lv.EVENT.CLICKED:
            self.game.toggle_play_pause()

    def _on_pl_close(self, event_struct):
        if event_struct.code == lv.EVENT.CLICKED:
            self.game.close_player()

    # ── Volume popup ──

    def show_volume_popup(self):
        """Show the volume overlay and schedule it to hide."""
        vol_icon = lv.SYMBOL.VOLUME_MID
        if self.game.volume == 0:
            vol_icon = lv.SYMBOL.MUTE
        elif self.game.volume > 20:
            vol_icon = lv.SYMBOL.VOLUME_MAX
        self.pl_lbl_vol.set_text(vol_icon + " " + str(self.game.volume))
        self.pl_lbl_vol.remove_flag(lv.obj.FLAG.HIDDEN)
        self._vol_popup_visible = True
        self._vol_popup_hide_time = time.ticks_add(
            time.ticks_ms(), self.VOL_POPUP_DURATION_MS
        )

    def tick_volume_popup(self):
        """Call each loop iteration to auto-hide the volume popup."""
        if self._vol_popup_visible:
            if time.ticks_diff(time.ticks_ms(), self._vol_popup_hide_time) > 0:
                self.pl_lbl_vol.add_flag(lv.obj.FLAG.HIDDEN)
                self._vol_popup_visible = False

    # ── Full UI refresh (called by GameState._notify) ──

    def refresh(self):
        if self.game.in_player:
            self._refresh_player()
            self._show_player()
        else:
            self._refresh_select()
            self._show_select()

    def _refresh_select(self):
        if self.game.total_files == 0:
            self.sel_lbl_song.set_text("No songs found")
            self.sel_lbl_index.set_text("")
            return
        self.sel_lbl_song.set_text(self.game.get_display_name())
        self.sel_lbl_index.set_text(self.game.get_index_text())

    def _refresh_player(self):
        # Song name
        self.pl_lbl_song.set_text(self.game.get_display_name())

        # Play/pause button: green with play icon, or red with pause icon
        if self.game.is_playing:
            self.pl_btn_main.set_btn_text(lv.SYMBOL.PAUSE)
            self.pl_btn_main.set_style_bg_color(lv.color_hex(0xE53935), 0)
        else:
            self.pl_btn_main.set_btn_text(lv.SYMBOL.PLAY)
            self.pl_btn_main.set_style_bg_color(lv.color_hex(0x43A047), 0)


# ══════════════════════════════════════════════
# Application entry point
# ══════════════════════════════════════════════
def setup():
    """Initialize hardware, build UI, return (game, ui, rotary, remote)."""
    M5.begin()
    m5ui.init()

    audio = AudioController(uart_id=1, port=(1, 2), init_delay_s=2)

    rotary = Rotary()
    rotary.reset_rotary_value()

    remote = RemoteControl()

    game = GameState(audio)
    game.configure()

    ui = PlayerUI(game)

    game.load_files()
    ui.refresh()

    def on_btn_a(state):
        if game.in_player:
            game.toggle_play_pause()
        else:
            game.enter_player()
    BtnA.setCallback(type=BtnA.CB_TYPE.WAS_CLICKED, cb=on_btn_a)

    return game, ui, rotary, remote


def main():
    """Main event loop."""
    game, ui, rotary, remote = setup()
    last_rotary = 0
    # #region agent log
    _dbg_loop_count = 0
    _dbg_last_report = time.ticks_ms()
    _dbg_recv_count = 0
    # #endregion

    while True:
        M5.update()

        # #region agent log
        _dbg_loop_count += 1
        _dbg_now = time.ticks_ms()
        if time.ticks_diff(_dbg_now, _dbg_last_report) > 5000:
            print("[DBG-34562d][H-A] 5s report: loops=", _dbg_loop_count,
                  "msgs_total=", _dbg_recv_count,
                  "espnow_active=", remote._esp.active(),
                  "wlan_active=", remote._wlan.active(),
                  "ch=", remote._wlan.config('channel'))
            _dbg_loop_count = 0
            _dbg_last_report = _dbg_now
        # #endregion

        # ── ESP-NOW remote commands ──
        
        cmd = remote.poll()
        if cmd:
            # #region agent log
            _dbg_recv_count += 1
            print("[DBG-34562d][H-ALL] main got cmd:", cmd,
                  "in_player=", game.in_player,
                  "is_playing=", game.is_playing,
                  "msg#=", _dbg_recv_count)
            # #endregion
            game.handle_remote_command(cmd)

        # ── Volume popup auto-hide ──
        ui.tick_volume_popup()

        # ── Rotary encoder ──
        if rotary.get_rotary_status():
            new_val = rotary.get_rotary_value()
            delta = new_val - last_rotary
            last_rotary = new_val

            if game.in_player:
                # Dial adjusts volume on the player screen
                if delta > 0:
                    game.adjust_volume(1)
                elif delta < 0:
                    game.adjust_volume(-1)
                ui.show_volume_popup()
            else:
                # Dial browses songs on the select screen
                if delta > 0:
                    game.select_next()
                elif delta < 0:
                    game.select_prev()


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except ImportError:
            print("please update to latest firmware")