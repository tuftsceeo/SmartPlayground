#battery in V
from machine import ADC, Pin
import time

# Set up ADC on GPIO0 (you can change this to the actual pin you're using)
adc = ADC(Pin(0))           # Replace 0 with the correct GPIO number connected to your voltage divider
adc.atten(ADC.ATTN_11DB)    # Configure attenuation for full-scale voltage (approx 3.6V)
adc.width(ADC.WIDTH_12BIT) # 12-bit resolution (0-4095)

while True:
    Vbatt = 0
    for _ in range(16):
        Vbatt += adc.read()  # Read raw ADC value
        time.sleep_ms(10)    # Small delay between readings
    
    avg_adc = Vbatt / 16
    voltage = (avg_adc / 4095.0) * 3.6 * 2  # Convert to volts and adjust for 1:2 voltage divider

    print("{:.3f} V".format(voltage))  # Print voltage with 3 decimal places
    time.sleep(1)


