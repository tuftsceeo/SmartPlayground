"""
Non-Blocking Qwiic Twist IoT Utilities
======================================
State-based functions for async/interrupt systems
"""
import qwiic_twist
import time

class TwistIOT:
    def __init__(self, i2c_driver=None):
        self.twist = qwiic_twist.QwiicTwist(i2c_driver=i2c_driver)
        self.current_mode = 0
        self.modes = []
        self.last_count = 0
        
        # Animation states
        self.blink_state = {'active': False, 'count': 0, 'next_time': 0, 'color': (0,0,0), 'original': (0,0,0)}
        self.breathe_state = {'active': False, 'start_time': 0, 'color': (0,0,0)}
        
    # === MODE MANAGEMENT ===
    def setup_modes(self, mode_list):
        """Setup modes: [(name, r, g, b), ...]"""
        self.modes = mode_list
        self.twist.count = 0
        
    def cycle_mode_on_click(self):
        """Check for mode change (call in main loop)"""
        if self.twist.clicked:
            # Stop all animations when changing modes
            self.blink_state['active'] = False
            self.breathe_state['active'] = False
            
            self.current_mode = (self.current_mode + 1) % len(self.modes)
            self.show_mode()
            return True
        return False
        
    def get_mode_from_rotation(self):
        """Map rotation to mode index"""
        if not self.modes: return 0
        count = self.twist.count
        ticks_per_mode = max(1, 24 // len(self.modes))
        return (count // ticks_per_mode) % len(self.modes)
        
    # === NON-BLOCKING ANIMATIONS ===
    def start_blink(self, color, times=3, interval=200):
        """Start blinking animation"""
        self.blink_state = {
            'active': True,
            'count': times * 2,  # on/off cycles
            'next_time': time.ticks_ms() + interval,
            'color': color,
            'original': self.get_current_mode_color(),
            'interval': interval,
            'on': True
        }
        
    def update_blink(self):
        """Update blink animation (call in main loop)"""
        if not self.blink_state['active']:
            return
            
        if time.ticks_ms() >= self.blink_state['next_time']:
            if self.blink_state['count'] > 0:
                color = self.blink_state['color'] if self.blink_state['on'] else self.blink_state['original']
                self.twist.set_color(*color)
                
                self.blink_state['on'] = not self.blink_state['on']
                self.blink_state['count'] -= 1
                self.blink_state['next_time'] += self.blink_state['interval']
            else:
                # Animation complete
                self.twist.set_color(*self.blink_state['original'])
                self.blink_state['active'] = False
                
    def start_breathe(self, color, duration=2000):
        """Start breathing animation"""
        self.breathe_state = {
            'active': True,
            'start_time': time.ticks_ms(),
            'color': color,
            'duration': duration
        }
        
    def update_breathe(self):
        """Update breathing animation (call in main loop)"""
        if not self.breathe_state['active']:
            return
            
        elapsed = time.ticks_ms() - self.breathe_state['start_time']
        if elapsed >= self.breathe_state['duration']:
            self.breathe_state['active'] = False
            self.show_mode()
            return
            
        # Simple triangle wave breathing (0 -> 1 -> 0 over 2 seconds)
        cycle_time = 1000  # 2 seconds per cycle
        cycle_pos = (elapsed % cycle_time) / cycle_time
        
        if cycle_pos < 0.5:
            intensity = cycle_pos * 2  # 0 to 1
        else:
            intensity = 2 - (cycle_pos * 2)  # 1 to 0
        
        r, g, b = self.breathe_state['color']
        self.twist.set_color(int(r * intensity), int(g * intensity), int(b * intensity))
        
    # === IMMEDIATE FUNCTIONS ===
    def show_mode(self):
        """Display current mode color immediately"""
        if self.modes:
            _, r, g, b = self.modes[self.current_mode]
            self.twist.set_color(r, g, b)
            
    def get_rotation_delta(self):
        """Get rotation change since last check"""
        count = self.twist.count
        delta = count - self.last_count
        self.last_count = count
        return delta
        
    def show_progress(self, percent):
        """Show progress as color (0-100)"""
        intensity = int(percent * 2.55)
        self.twist.set_color(intensity, 255-intensity, 0)
        
    def show_connection_status(self, connected):
        """Immediate status: Green=connected, Red=disconnected"""
        self.twist.set_color(0, 255, 0) if connected else self.twist.set_color(255, 0, 0)
        
    def reset_position(self):
        """Reset encoder to zero"""
        self.twist.count = 0
        
    # === HELPERS ===
    def get_current_mode_color(self):
        """Get current mode RGB tuple"""
        if self.modes:
            _, r, g, b = self.modes[self.current_mode]
            return (r, g, b)
        return (0, 0, 0)
        
    def encode_state(self):
        """Export state for network transmission"""
        return {
            'mode': self.current_mode,
            'count': self.twist.count,
            'pressed': self.twist.pressed
        }
        
    def update_animations(self):
        """Update all active animations (call in main loop)"""
        self.update_blink()
        self.update_breathe()
        
    # === STATUS SHORTCUTS ===
    def error_flash(self):
        """Start red error flash"""
        self.start_blink((255, 0, 0), times=3, interval=100)
        
    def success_flash(self):
        """Start green success flash"""
        self.start_blink((0, 255, 0), times=2, interval=300)
        
    def warning_breathe(self):
        """Start yellow breathing warning"""
        self.start_breathe((255, 255, 0), duration=3000)

def sin(x):
    """Fast sine approximation"""
    x = x % 6.283
    return x - (x**3)/6 + (x**5)/120

# === USAGE EXAMPLE ===
def main_loop_example():
    """Example main loop structure"""
    iot = TwistIOT()
    iot.setup_modes([
        ("WiFi", 255, 0, 255),
        ("Sensor", 0, 255, 0),
        ("Config", 255, 255, 0)
    ])
    
    while True:
        # Handle inputs
        iot.cycle_mode_on_click()
        delta = iot.get_rotation_delta()
        
        # Update animations
        iot.update_animations()
        
        # Your other async code here...
        # await something()
        
        time.sleep_ms(10)  # Small delay for loop timing