# -*- coding: UTF-8 -*-

import time
from typing import Optional, List

import numpy as np
import config


LCD_1IN44 = 1
LCD_1IN8 = 0

if LCD_1IN44 == 1:
    LCD_WIDTH = 128
    LCD_HEIGHT = 128
    LCD_X = 2
    LCD_Y = 1

if LCD_1IN8 == 1:
    LCD_WIDTH = 160
    LCD_HEIGHT = 128
    LCD_X = 1
    LCD_Y = 2

LCD_X_MAXPIXEL = 132
LCD_Y_MAXPIXEL = 162

# Scan directions
L2R_U2D = 1
L2R_D2U = 2
R2L_U2D = 3
R2L_D2U = 4
U2D_L2R = 5
U2D_R2L = 6
D2U_L2R = 7
D2U_R2L = 8
SCAN_DIR_DFT = U2D_R2L


class LCD(config.RaspberryPi):
    KEYS = {
        "up": config.KEY_UP_PIN,
        "down": config.KEY_DOWN_PIN,
        "left": config.KEY_LEFT_PIN,
        "right": config.KEY_RIGHT_PIN,
        "press": config.KEY_PRESS_PIN,
        "key1": config.KEY1_PIN,
        "key2": config.KEY2_PIN,
        "key3": config.KEY3_PIN,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.width = LCD_WIDTH
        self.height = LCD_HEIGHT
        self.LCD_Scan_Dir = SCAN_DIR_DFT
        self.LCD_X_Adjust = LCD_X
        self.LCD_Y_Adjust = LCD_Y

    # -------------------------------------------------------------------------
    # Key handling
    # -------------------------------------------------------------------------

    def get_key_state(self, name: str) -> bool:
        pin = self.KEYS.get(name)
        if pin is None:
            raise ValueError(f"Unknown key name: {name}")
        return self.digital_read(pin) == 0  # active low

    def get_pressed_keys(self) -> List[str]:
        pressed = []
        for name, pin in self.KEYS.items():
            if self.digital_read(pin) == 0:
                pressed.append(name)
        return pressed

    def wait_for_key(self, timeout: Optional[float] = None, debounce_ms: int = 50) -> Optional[str]:
        start = time.time()
        while True:
            for name, pin in self.KEYS.items():
                if self.digital_read(pin) == 0:
                    time.sleep(debounce_ms / 1000.0)
                    if self.digital_read(pin) == 0:
                        return name

            if timeout is not None and (time.time() - start) > timeout:
                return None

            time.sleep(0.01)

    # -------------------------------------------------------------------------
    # LCD low-level
    # -------------------------------------------------------------------------

    def LCD_Reset(self):
        self.digital_write(self.RST, True)
        time.sleep(0.01)
        self.digital_write(self.RST, False)
        time.sleep(0.01)
        self.digital_write(self.RST, True)
        time.sleep(0.01)

    def LCD_WriteReg(self, reg):
        self.digital_write(self.DC, False)
        self.spi_writebyte([reg & 0xFF])

    def LCD_WriteData_8bit(self, data):
        self.digital_write(self.DC, True)
        self.spi_writebyte([data & 0xFF])

    def LCD_WriteData_NLen16Bit(self, data, data_len):
        self.digital_write(self.DC, True)
        hi = (data >> 8) & 0xFF
        lo = data & 0xFF
        buf = [hi, lo] * data_len
        for i in range(0, len(buf), 4096):
            self.spi_writebyte(buf[i:i + 4096])

    def LCD_InitReg(self):
        self.LCD_WriteReg(0xB1)
        self.LCD_WriteData_8bit(0x01)
        self.LCD_WriteData_8bit(0x2C)
        self.LCD_WriteData_8bit(0x2D)

        self.LCD_WriteReg(0xB2)
        self.LCD_WriteData_8bit(0x01)
        self.LCD_WriteData_8bit(0x2C)
        self.LCD_WriteData_8bit(0x2D)

        self.LCD_WriteReg(0xB3)
        self.LCD_WriteData_8bit(0x01)
        self.LCD_WriteData_8bit(0x2C)
        self.LCD_WriteData_8bit(0x2D)
        self.LCD_WriteData_8bit(0x01)
        self.LCD_WriteData_8bit(0x2C)
        self.LCD_WriteData_8bit(0x2D)

        self.LCD_WriteReg(0xB4)
        self.LCD_WriteData_8bit(0x07)

        self.LCD_WriteReg(0xC0)
        self.LCD_WriteData_8bit(0xA2)
        self.LCD_WriteData_8bit(0x02)
        self.LCD_WriteData_8bit(0x84)

        self.LCD_WriteReg(0xC1)
        self.LCD_WriteData_8bit(0xC5)

        self.LCD_WriteReg(0xC2)
        self.LCD_WriteData_8bit(0x0A)
        self.LCD_WriteData_8bit(0x00)

        self.LCD_WriteReg(0xC3)
        self.LCD_WriteData_8bit(0x8A)
        self.LCD_WriteData_8bit(0x2A)

        self.LCD_WriteReg(0xC4)
        self.LCD_WriteData_8bit(0x8A)
        self.LCD_WriteData_8bit(0xEE)

        self.LCD_WriteReg(0xC5)
        self.LCD_WriteData_8bit(0x0E)

        self.LCD_WriteReg(0xE0)
        for d in (
            0x0F, 0x1A, 0x0F, 0x18, 0x2F, 0x28, 0x20, 0x22,
            0x1F, 0x1B, 0x23, 0x37, 0x00, 0x07, 0x02, 0x10
        ):
            self.LCD_WriteData_8bit(d)

        self.LCD_WriteReg(0xE1)
        for d in (
            0x0F, 0x1B, 0x0F, 0x17, 0x33, 0x2C, 0x29, 0x2E,
            0x30, 0x30, 0x39, 0x3F, 0x00, 0x07, 0x03, 0x10
        ):
            self.LCD_WriteData_8bit(d)

        self.LCD_WriteReg(0xF0)
        self.LCD_WriteData_8bit(0x01)

        self.LCD_WriteReg(0xF6)
        self.LCD_WriteData_8bit(0x00)

        self.LCD_WriteReg(0x3A)
        self.LCD_WriteData_8bit(0x05)

    def LCD_SetGramScanWay(self, scan_dir):
        self.LCD_Scan_Dir = scan_dir

        if scan_dir in (L2R_U2D, L2R_D2U, R2L_U2D, R2L_D2U):
            self.width = LCD_HEIGHT
            self.height = LCD_WIDTH

            if scan_dir == L2R_U2D:
                memory_access_reg_data = 0x00
            elif scan_dir == L2R_D2U:
                memory_access_reg_data = 0x80
            elif scan_dir == R2L_U2D:
                memory_access_reg_data = 0x40
            else:
                memory_access_reg_data = 0xC0
        else:
            self.width = LCD_WIDTH
            self.height = LCD_HEIGHT

            if scan_dir == U2D_L2R:
                memory_access_reg_data = 0x20
            elif scan_dir == U2D_R2L:
                memory_access_reg_data = 0x60
            elif scan_dir == D2U_L2R:
                memory_access_reg_data = 0xA0
            else:
                memory_access_reg_data = 0xE0

        if (memory_access_reg_data & 0x10) != 1:
            self.LCD_X_Adjust = LCD_Y
            self.LCD_Y_Adjust = LCD_X
        else:
            self.LCD_X_Adjust = LCD_X
            self.LCD_Y_Adjust = LCD_Y

        self.LCD_WriteReg(0x36)
        if LCD_1IN44 == 1:
            self.LCD_WriteData_8bit(memory_access_reg_data | 0x08)
        else:
            self.LCD_WriteData_8bit(memory_access_reg_data & 0xF7)

    def LCD_Init(self, lcd_scan_dir=SCAN_DIR_DFT):
        if self.module_init() != 0:
            return -1

        self.bl_on()
        self.LCD_Reset()
        self.LCD_InitReg()
        self.LCD_SetGramScanWay(lcd_scan_dir)
        self.delay_ms(200)

        self.LCD_WriteReg(0x11)
        self.delay_ms(120)

        self.LCD_WriteReg(0x29)
        return 0

    def LCD_SetWindows(self, xstart, ystart, xend, yend):
        self.LCD_WriteReg(0x2A)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit((xstart & 0xFF) + self.LCD_X_Adjust)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit(((xend - 1) & 0xFF) + self.LCD_X_Adjust)

        self.LCD_WriteReg(0x2B)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit((ystart & 0xFF) + self.LCD_Y_Adjust)
        self.LCD_WriteData_8bit(0x00)
        self.LCD_WriteData_8bit(((yend - 1) & 0xFF) + self.LCD_Y_Adjust)

        self.LCD_WriteReg(0x2C)

    # -------------------------------------------------------------------------
    # Drawing
    # -------------------------------------------------------------------------

    def LCD_Clear(self, color=0xFFFF):
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        buffer = [hi, lo] * (self.width * self.height)

        self.LCD_SetWindows(0, 0, self.width, self.height)
        self.digital_write(self.DC, True)

        for i in range(0, len(buffer), 4096):
            self.spi_writebyte(buffer[i:i + 4096])

    def LCD_ShowImage(self, image, xstart=0, ystart=0):
        if image is None:
            return

        imwidth, imheight = image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError(
                f"Image must be same dimensions as display ({self.width}x{self.height})."
            )

        img = np.asarray(image.convert("RGB"))

        pix = np.zeros((self.height, self.width, 2), dtype=np.uint8)
        pix[..., 0] = (img[..., 0] & 0xF8) | (img[..., 1] >> 5)
        pix[..., 1] = ((img[..., 1] << 3) & 0xE0) | (img[..., 2] >> 3)

        pix = pix.flatten().tolist()

        self.LCD_SetWindows(xstart, ystart, xstart + self.width, ystart + self.height)
        self.digital_write(self.DC, True)

        for i in range(0, len(pix), 4096):
            self.spi_writebyte(pix[i:i + 4096])


if __name__ == "__main__":
    from PIL import Image, ImageDraw, ImageFont

    lcd = LCD()

    try:
        lcd.LCD_Init()
        lcd.LCD_Clear(0x0000)

        img = Image.new("RGB", (lcd.width, lcd.height), "black")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()

        draw.text((10, 10), "LCD OK", fill="white", font=font)
        draw.text((10, 25), "Press keys...", fill="green", font=font)
        lcd.LCD_ShowImage(img)

        while True:
            pressed = lcd.get_pressed_keys()
            if pressed:
                img = Image.new("RGB", (lcd.width, lcd.height), "black")
                draw = ImageDraw.Draw(img)
                draw.text((10, 10), "Pressed:", fill="white", font=font)
                y = 25
                for key in pressed:
                    draw.text((10, y), key, fill="yellow", font=font)
                    y += 12
                lcd.LCD_ShowImage(img)
            time.sleep(0.1)

    finally:
        lcd.module_exit()
