p = r"D:\Users\Jennifer\Documents\GitHub\SmartPlayground\Bag3\Code\Wand Module\lib\lobby_game.py"
s = open(p, newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')


def rep(x, y):
    global s
    assert s.count(x) == 1, (s.count(x), x[:70])
    s = s.replace(x, y)


rep('''            d["p"] = self.lobby_players()
''', '''            d["p"] = self.lobby_players()
            d["c"] = self.ident          # the lobby color: the host's identity
''')
rep('''            elif t == "pw_joined":
                pass            # a repeated answer to a retried pw_join''', '''            elif t == "pw_joined":
                pass            # a repeated answer to a retried pw_join
            elif t == "pw_lobby" and d.get("c"):
                self.lobby_p = d.get("p") or 0      # a host lobby: players and color
                self.lobby_c = d.get("c")''')
# Net attributes: set in __init__ after ident
rep('''        self.ident = splatpair.identity_name(my_mac)
''', '''        self.ident = splatpair.identity_name(my_mac)
        self.lobby_p = 0                # follower in a host lobby: players (pw_lobby p)
        self.lobby_c = None             # and the lobby color name (pw_lobby c)
        self.screen = None              # host: splat_host.HostScreen (enter)
        self.button_down = None
        self.leds = None
''')
# Host game tick in poll
rep('''                self._check_lost(now)
        if self._events:''', '''                self._check_lost(now)
            if self.is_host and self.screen is not None and self.phase == "game":
                self._host_tick(now)
        if self._events:''')
rep('''    def _finish(self, reason):''', '''    def _host_tick(self, now):
        """Host, while playing: the cyan heartbeat screen; a long hold ends the game."""
        down = self.button_down() if self.button_down is not None else False
        act, hold, _ = self.screen.button(down, "playing", now)
        if act == "end":
            print("  Splat host: game ended by a hold")
            self._finish("ended")
            return
        self.screen.draw(self.leds, self.ctl, "playing", now, hold,
                         count=len(self.players()) if hasattr(self, "players") else 0,
                         lobby_rgb=splatpair.WAND_RGB[self.ident])

    def _finish(self, reason):''')
# _draw_lobby: host branch replaced; follower in a host lobby shows dots
a = s.index('    if net.is_host:\n        # The player count as a numeral')
b = s.index('    if net.is_leader:\n        joined, need')
s = s[:a] + s[b:]
rep('''    # A follower waits with a blue spinner: a still icon in a red identity read as an error.''', '''    if net.lobby_c is not None:
        # A player in a host lobby: one dot per joined player, and the lobby
        # color in the center pixel (the host's center pixel).
        view = ("dots", net.lobby_p, net.lobby_c)
        if view == last:
            return last
        for i in range(leds.num):
            leds.np[i] = OFF
        dots = [i for i in range(leds.num) if i != 12][:net.lobby_p]
        for i in dots:
            leds.np[i] = GREEN
        if leds.num > 12:
            leds.np[12] = splatpair.WAND_RGB.get(net.lobby_c, BLUE_DIM)
        leds.np.write()
        return view
    # A follower waits with a blue spinner: a still icon in a red identity read as an error.''')
rep('''        down = button_down()
        if down and not was_down and net.can_start():
            net.start()
            return "start"
        was_down = down
        shown = _draw_lobby(leds, net, shown)''', '''        down = button_down()
        if net.is_host:
            # Host: a short press peeks the player count; a hold starts.
            now = time.ticks_ms()
            act, hold, _ = net.screen.button(down, "lobby", now, net.can_start())
            if act == "start":
                net.start()
                return "start"
            if act == "refuse":
                print("  Splat host: no players yet; not starting")
                buz.reject()
            net.screen.draw(leds, net.ctl, "lobby", now, hold, count=net.lobby_players(),
                            lobby_rgb=splatpair.WAND_RGB[net.ident])
            time.sleep_ms(1)
            continue
        if down and not was_down and net.can_start():
            net.start()
            return "start"
        was_down = down
        shown = _draw_lobby(leds, net, shown)''')
rep('''    net = Net(enow, my_mac, ctl, slug, splats_min, splats_max, host_game, is_host, players_min)
''', '''    net = Net(enow, my_mac, ctl, slug, splats_min, splats_max, host_game, is_host, players_min)
    net.leds = leds
    net.button_down = button_down
    if is_host:
        import splat_host
        net.screen = splat_host.HostScreen(born=time.ticks_add(time.ticks_ms(), -60000))
''')
open(p, 'w', newline='').write(s.replace('\n', nl))
print("ok")
