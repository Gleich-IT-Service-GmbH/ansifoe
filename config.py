import logging
import time

import spidev
import RPi.GPIO as GPIO

# GPIO define
KEY_UP_PIN = 6
KEY_DOWN_PIN = 19
KEY_LEFT_PIN = 5
KEY_RIGHT_PIN = 26
KEY_PRESS_PIN = 13

KEY1_PIN = 21
KEY2_PIN = 20
KEY3_PIN = 16


class RaspberryPi:
    def __init__(
        self,
        spi=None,
        spi_bus=0,
        spi_device=0,
        spi_freq=40000000,
        rst=27,
        dc=25,
        bl=24,
        bl_freq=1000,
    ):
        self.SPEED = spi_freq
        self.BL_freq = bl_freq

        # ---------------- GPIO INIT ----------------
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # LCD control pins
        self.RST = rst
        self.DC = dc
        self.BL = bl

        GPIO.setup(self.RST, GPIO.OUT)
        GPIO.setup(self.DC, GPIO.OUT)
        GPIO.setup(self.BL, GPIO.OUT)

        GPIO.output(self.BL, 1)  # backlight ON

        # ---------------- INPUT PINS ----------------
        self.pins = [
            KEY_UP_PIN,
            KEY_DOWN_PIN,
            KEY_LEFT_PIN,
            KEY_RIGHT_PIN,
            KEY_PRESS_PIN,
            KEY1_PIN,
            KEY2_PIN,
            KEY3_PIN,
        ]

        for p in self.pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # ---------------- SPI ----------------
        if spi is None:
            self.SPI = spidev.SpiDev()
            self.SPI.open(spi_bus, spi_device)
        else:
            self.SPI = spi

        self.SPI.max_speed_hz = spi_freq
        self.SPI.mode = 0b00

    # ---------------- GPIO HELPERS ----------------

    def digital_write(self, pin, value):
        GPIO.output(pin, value)

    def digital_read(self, pin):
        return GPIO.input(pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    # ---------------- SPI ----------------

    def spi_writebyte(self, data):
        if self.SPI is not None:
            self.SPI.writebytes(data)

    # ---------------- BACKLIGHT ----------------

    def bl_on(self):
        GPIO.output(self.BL, 1)

    def bl_off(self):
        GPIO.output(self.BL, 0)

    # ---------------- INIT / EXIT ----------------

    def module_init(self):
        if self.SPI is not None:
            self.SPI.max_speed_hz = self.SPEED
            self.SPI.mode = 0b00
        return 0

    def module_exit(self):
        logging.debug("SPI end")

        if self.SPI is not None:
            try:
                self.SPI.close()
            except Exception:
                pass

        logging.debug("GPIO cleanup")
        try:
            GPIO.output(self.RST, 1)
            GPIO.output(self.DC, 0)
            GPIO.output(self.BL, 0)
        except Exception:
            pass

        GPIO.cleanup()
        time.sleep(0.01)
