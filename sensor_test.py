#!/usr/bin/env python3
"""Conversation-derived dual-BME280 terminal test.

Inside sensor:  0x77 (SDO high)
Outside sensor: 0x76 (SDO low)
"""

import time

import board
from adafruit_bme280 import basic as adafruit_bme280


# Raspberry Pi I2C connection:
# SDA = physical pin 3
# SCL = physical pin 5
i2c = board.I2C()

inside_sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
outside_sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)

print("Both BME280 sensors connected.")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        inside_temperature = inside_sensor.temperature
        outside_temperature = outside_sensor.temperature
        inside_humidity = inside_sensor.relative_humidity
        outside_humidity = outside_sensor.relative_humidity

        print(
            f"INSIDE  | {inside_temperature:5.1f} °C"
            f" | Humidity: {inside_humidity:5.1f} %"
        )
        print(
            f"OUTSIDE | {outside_temperature:5.1f} °C"
            f" | Humidity: {outside_humidity:5.1f} %"
        )
        print("-" * 46)
        time.sleep(2)

except KeyboardInterrupt:
    print("\nSensor test stopped.")

except Exception as error:
    print(f"\nSensor error: {error}")
    print("Check the wiring and confirm that i2cdetect shows 76 and 77.")
