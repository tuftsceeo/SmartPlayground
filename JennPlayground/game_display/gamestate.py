class GameState:
    def __init__(self, coder_mac=None, sequence=None):
        """
        Initialize the game state.
        
        :param coder_mac: MAC address of the coder (game master).
        :param sequence: Optional initial sequence (list of numbers).
        """
        self.coder_mac = coder_mac
        self.sequence = sequence if sequence else []
        self.players = {}  # Dictionary to store players and their progress

    def set_sequence(self, sequence):
        """Set the game sequence provided by the coder."""
        if len(sequence) == 8 and all(1 <= num <= 10 for num in sequence):
            self.sequence = sequence
            print(f"Game sequence set to: {self.sequence}")
        else:
            raise ValueError("Sequence must be a list of 8 numbers between 1 and 10.")

    def add_player(self, mac_address):
        """Add a player with the given MAC address."""
        if len(self.players) >= 4:
            print("Cannot add more than 4 players.")
            return
        if mac_address not in self.players:
            self.players[mac_address] = 0  # Initial progress is 0
            print(f"Player {mac_address} added.")
        else:
            print(f"Player {mac_address} is already in the game.")

    def remove_player(self, mac_address):
        """Remove a player by their MAC address."""
        if mac_address in self.players:
            del self.players[mac_address]
            print(f"Player {mac_address} removed.")
        else:
            print(f"Player {mac_address} not found.")

    def update_progress(self, mac_address, step):
        """Update the progress of a player."""
        if mac_address in self.players:
            self.players[mac_address] = min(step, 8)  # Cap progress at 8 steps
            print(f"Player {mac_address} progress updated to step {step}.")
        else:
            print(f"Player {mac_address} not found. Add the player first.")

    def get_player_progress(self, mac_address):
        """Get the progress of a specific player."""
        return self.players.get(mac_address, None)

    def get_all_progress(self):
        """Get progress for all players."""
        return self.players

    def reset_game(self):
        """Reset the game state."""
        self.players = {}
        self.sequence = []
        print("Game has been reset.")

    def to_dict(self):
        """Convert the game state to a dictionary for saving."""
        return {
            "coder_mac": self.coder_mac,
            "sequence": self.sequence,
            "players": self.players
        }

    def from_dict(self, data):
        """Restore the game state from a dictionary."""
        self.coder_mac = data.get("coder_mac")
        self.sequence = data.get("sequence", [])
        self.players = data.get("players", {})

    def reset_player_activity(self, mac_address):
        """Reset the activity timestamp for a player."""
        self.players[mac_address] = time.time()

    def remove_inactive_players(self, timeout):
        """Remove players who have been inactive for the specified timeout duration."""
        current_time = time.time()
        inactive_players = [mac for mac, last_active in self.players.items() if current_time - last_active > timeout]
        for mac in inactive_players:
            self.remove_player(mac)

# Example Usage
if __name__ == "__main__":
    # Initialize the game with a coder's MAC address
    coder_mac = b'\x24\x0A\xC4\xDE\xAD\xBE'
    game = GameState(coder_mac)

    # Set the game sequence
    game.set_sequence([1, 5, 7, 2, 9, 4, 3, 6])

    # Add players dynamically
    player1 = b'\x24\x0A\xC4\x12\x34\x56'
    player2 = b'\x24\x0A\xC4\x65\x43\x21'
    game.add_player(player1)
    game.add_player(player2)

    # Update player progress
    game.update_progress(player1, 3)
    game.update_progress(player2, 5)

    # Display progress
    print(game.get_all_progress())

    # Remove a player
    game.remove_player(player1)

    # Display progress after removal
    print(game.get_all_progress())

    # Reset the game
    game.reset_game()
