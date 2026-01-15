from machine import ADC, Pin
import time

# Setup ADC on pin A0 (usually GPIO36 or GPIO0 depending on the board)
adc = ADC(Pin(0))  # Replace with actual pin if A0 is mapped differently

# Configure ADC attenuation if needed (11dB maps ~3.3V full scale)
adc.atten(ADC.ATTN_11DB)  # Allows up to ~3.6V input
adc.width(ADC.WIDTH_12BIT)  # 12-bit resolution (0–4095)

while True:
    vbatt = 0
    for _ in range(16):
        raw = adc.read()
        print(raw)
        # Returns a value between 0 and 4095
        # Convert to millivolts

#out of the box values - 1905 to 1940 ish
# fully charged - 2300+ or 2200+ 2270 to