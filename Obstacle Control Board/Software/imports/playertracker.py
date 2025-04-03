from machine import Pin
import neopixel

class PlayerTracker:
    def __init__(self, pin, num_rows=5, row_length=8):
        """
        Initialize the NeoPixel player tracker.

        :param pin: GPIO pin connected to the NeoPixels.
        :param num_rows: Number of rows (default is 5: 1 for coder + 4 for players).
        :param row_length: Number of LEDs per row (default is 8).
        """
        self.num_rows = num_rows
        self.row_length = row_length
        self.total_leds = num_rows * row_length
        self.np = neopixel.NeoPixel(Pin(pin), self.total_leds)
        self.clear_all()
        self.COLOR_MAP = self.generate_color_map()

    def clear_all(self):
        """Clear all LEDs."""
        self.np.fill((0, 0, 0))
        self.np.write()

    def color_wheel(self, pos):
        """
        Generate rainbow colors across 0-255 positions for NeoPixel.
        
        :param pos: Position (0-255) for color generation.
        """
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)
    
    def generate_color_map(self):
        """
        Generate a color map for values 1 to 9 using the color wheel.
        """
        color_map = {i: self.color_wheel(int(i * 255 / 9)) for i in range(1, 10)}
        color_map[10] = (255, 255, 255)  # White for 10
        color_map[None] = (0, 0, 0)      # Black (off) for None
        return color_map

    def display_coder_sequence(self, sequence):
        """
        Display the coder's sequence in the first row of LEDs.

        :param sequence: List of 8 numbers representing the sequence.
        """
        for i, num in enumerate(sequence[:self.row_length]):
            color = self.COLOR_MAP.get(num, (0, 0, 0))
            self.np[i] = color
        self.np.write()
    
    def update_player_progress(self, player_index, progress, sequence):
        """
        Update the progress lights for a specific player.

        :param player_index: Index of the player (0 to 3).
        :param progress: Number of steps completed (0 to 8).
        :param sequence: The game sequence to determine the color for each step.
        """
        if player_index < 0 or player_index >= (self.num_rows - 1):
            print(f"Invalid player index: {player_index}. Must be between 0 and 3.")
            return

        row_start = (player_index + 1) * self.row_length
        for i in range(self.row_length):
            if i < progress:
                color = self.COLOR_MAP.get(sequence[i], (0, 0, 0))
                self.np[row_start + i] = color
            else:
                self.np[row_start + i] = (0, 0, 0)  # Black for incomplete steps

        self.np.write()

    def clear_player_progress(self, player_index):
        """
        Clear the progress lights for a specific player.

        :param player_index: Index of the player (0 to 3).
        """
        if player_index < 0 or player_index >= (self.num_rows - 1):
            print(f"Invalid player index: {player_index}. Must be between 0 and 3.")
            return

        row_start = (player_index + 1) * self.row_length
        for i in range(self.row_length):
            self.np[row_start + i] = (0, 0, 0)

        self.np.write()
    
    def reset_all_progress(self):
        """Clear the progress lights for all players."""
        self.clear_all()
        print("All player progress reset.")

    def indicate_request(self, row, color=(255, 255, 0)):
        """
        Light up a row of LEDs to indicate an active request.
        
        :param row: The row to light up (0 for coder, 1-4 for players).
        :param color: The color to display (default is yellow).
        """
        if row < 0 or row >= self.num_rows:
            print(f"Invalid row index: {row}. Must be between 0 and {self.num_rows - 1}.")
            return
        
        row_start = row * self.row_length
        for i in range(self.row_length):
            self.np[row_start + i] = color
        self.np.write()