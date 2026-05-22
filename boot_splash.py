#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from PIL import Image, ImageDraw, ImageFont

from LCD_1in44 import LCD


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SPLASH_PATH = os.path.join(PROJECT_DIR, "splash.png")


def main():
    lcd = LCD()
    try:
        lcd.LCD_Init()
        lcd.LCD_Clear(0x0000)

        if os.path.exists(SPLASH_PATH):
            img = Image.open(SPLASH_PATH).convert("RGB")
            img = img.resize((lcd.width, lcd.height))
            lcd.LCD_ShowImage(img)
        else:
            # fallback splash if image missing
            img = Image.new("RGB", (lcd.width, lcd.height), "black")
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()

            draw.rectangle((0, 0, lcd.width, 20), fill=(0, 0, 80))
            draw.text((18, 18), "Raspberry Pi", fill="white", font=font)
            draw.text((36, 36), "Booting...", fill="green", font=font)
            draw.text((20, 60), "LCD Splash", fill="cyan", font=font)

            lcd.LCD_ShowImage(img)

        # Keep splash visible for a moment before menu service starts
        time.sleep(3)

    finally:
        # Do NOT blank the display here.
        # module_exit() turns BL off, so skip it.
        pass


if __name__ == "__main__":
    main()
