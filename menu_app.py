#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import html
import ipaddress
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import psutil
from PIL import Image, ImageDraw, ImageFont

from LCD_1in44 import LCD


@dataclass
class MenuItem:
    title: str
    action: Optional[Callable[[], None]] = None
    submenu: List["MenuItem"] = field(default_factory=list)


class MenuApp:
    def __init__(self, lcd: LCD):
        self.lcd = lcd

        self.font = ImageFont.load_default()
        self.bg_color = (0, 0, 0)
        self.text_color = (255, 255, 255)
        self.highlight_color = (0, 255, 0)

        self._external_ip_cache = "N/A"
        self._external_ip_last_update = 0

        self.nmap_profile = "ping"

        self.nmap_text_output_file = os.path.expanduser("~/nmap_last.txt")
        self.nmap_xml_output_file = os.path.expanduser("~/nmap_last.xml")
        self.nmap_html_output_file = os.path.expanduser("~/nmap_last.html")

        self.root_menu = self.build_menu()

        self.menu_stack: List[Tuple[List[MenuItem], int, str]] = []
        self.current_menu = self.root_menu
        self.current_index = 0
        self.current_title = "Main Menu"

    # ------------------------------------------------------------------
    # Menu structure
    # ------------------------------------------------------------------
    def build_menu(self) -> List[MenuItem]:
        system_stats_menu = [
            MenuItem("Live Stats", action=self.show_system_stats),
        ]

        tools_nmap_menu = [
            MenuItem("Run Scan", action=self.run_nmap_scan),
            MenuItem("Last Result", action=self.show_last_nmap_result),
            MenuItem("Convert to HTML", action=self.convert_nmap_to_html),
        ]

        tools_menu = [
            MenuItem("Nmap", submenu=tools_nmap_menu),
        ]

        nmap_scan_type_menu = [
            MenuItem("Ping Sweep", action=lambda: self.set_nmap_profile("ping")),
            MenuItem("Basic Service", action=lambda: self.set_nmap_profile("basic")),
            MenuItem("Vuln Scripts", action=lambda: self.set_nmap_profile("vuln")),
        ]

        nmap_settings_menu = [
            MenuItem("Scan Type", submenu=nmap_scan_type_menu),
        ]

        power_menu = [
            MenuItem("Reboot", action=self.reboot_system),
            MenuItem("Shutdown", action=self.shutdown_system),
        ]

        settings_menu = [
            MenuItem("Nmap", submenu=nmap_settings_menu),
            MenuItem("Power", submenu=power_menu),
        ]

        return [
            MenuItem("System Stats", submenu=system_stats_menu),
            MenuItem("Tools", submenu=tools_menu),
            MenuItem("Settings", submenu=settings_menu),
        ]

    # ------------------------------------------------------------------
    # Splash screen
    # ------------------------------------------------------------------
    def show_splash(self, duration: float = 2.5, image_path: Optional[str] = None):
        try:
            if image_path and os.path.exists(image_path):
                img = Image.open(image_path).convert("RGB")
                img = img.resize((self.lcd.width, self.lcd.height))
                self.lcd.LCD_ShowImage(img)
                time.sleep(duration)
                return
        except Exception:
            pass

        img = Image.new("RGB", (self.lcd.width, self.lcd.height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.rectangle((0, 0, self.lcd.width, 20), fill=(0, 0, 80))
        draw.rectangle(
            (0, self.lcd.height - 16, self.lcd.width, self.lcd.height),
            fill=(16, 16, 16),
        )

        draw.text((18, 18), "Raspberry Pi", font=self.font, fill=(255, 255, 255))
        draw.text((34, 36), "Network", font=self.font, fill=(0, 255, 0))
        draw.text((42, 50), "Toolkit", font=self.font, fill=(0, 255, 255))
        draw.text((20, 80), "Starting...", font=self.font, fill=(255, 255, 0))
        draw.text((8, self.lcd.height - 12), "Please wait", font=self.font, fill=(128, 128, 128))

        self.lcd.LCD_ShowImage(img)
        time.sleep(duration)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        self.draw_menu()

        while True:
            key = self.read_key()
            if key is None:
                time.sleep(0.03)
                continue

            if key == "up":
                self.move_selection(-1)
            elif key == "down":
                self.move_selection(1)
            elif key in ("right", "press", "key2"):
                self.enter_item()
            elif key in ("left", "key1"):
                self.go_back()
            elif key == "key3":
                self.go_home()

            self.wait_for_key_release(key)
            self.draw_menu()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def move_selection(self, delta: int):
        if self.current_menu:
            self.current_index = (self.current_index + delta) % len(self.current_menu)

    def enter_item(self):
        if not self.current_menu:
            return

        item = self.current_menu[self.current_index]

        if item.submenu:
            self.menu_stack.append(
                (self.current_menu, self.current_index, self.current_title)
            )
            self.current_menu = item.submenu
            self.current_index = 0
            self.current_title = item.title
            return

        if item.action is not None:
            item.action()

    def go_back(self):
        if not self.menu_stack:
            return
        self.current_menu, self.current_index, self.current_title = self.menu_stack.pop()

    def go_home(self):
        self.menu_stack.clear()
        self.current_menu = self.root_menu
        self.current_index = 0
        self.current_title = "Main Menu"

    def check_home_button(self) -> bool:
        if self.lcd.get_key_state("key3"):
            time.sleep(0.08)
            if self.lcd.get_key_state("key3"):
                self.go_home()
                self.wait_for_key_release("key3")
                return True
        return False

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def read_key(self) -> Optional[str]:
        order = ["up", "down", "left", "right", "press", "key1", "key2", "key3"]
        for name in order:
            if self.lcd.get_key_state(name):
                time.sleep(0.04)
                if self.lcd.get_key_state(name):
                    return name
        return None

    def wait_for_key_release(self, key_name: str, timeout: float = 1.0):
        start = time.time()
        while self.lcd.get_key_state(key_name):
            if time.time() - start > timeout:
                break
            time.sleep(0.02)

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def fit_text(self, text: str, max_chars: int = 20) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    def draw_menu(self):
        img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle((0, 0, self.lcd.width, 14), fill=(0, 0, 64))
        draw.text(
            (2, 2),
            self.fit_text(self.current_title, 20),
            font=self.font,
            fill=self.text_color,
        )

        y = 18
        line_h = 12

        for idx, item in enumerate(self.current_menu):
            if y + line_h > self.lcd.height - 16:
                break

            selected = idx == self.current_index
            if selected:
                draw.rectangle(
                    (0, y - 1, self.lcd.width, y + line_h - 1),
                    fill=(32, 32, 32),
                )
                color = self.highlight_color
                prefix = ">"
            else:
                color = self.text_color
                prefix = " "

            title = item.title

            if title in ("Ping Sweep", "Basic Service", "Vuln Scripts"):
                if self.scan_profile_label_to_key(title) == self.nmap_profile:
                    title = "* " + title

            draw.text(
                (2, y),
                self.fit_text(prefix + " " + title, 20),
                font=self.font,
                fill=color,
            )
            y += line_h

        footer = ""
        if self.current_title == "Main Menu":
            footer = "K2 OK  K3 Home"
        elif self.current_title == "Tools":
            footer = "Choose tool"
        elif self.current_title == "Nmap":
            footer = self.get_nmap_profile_label()
        elif self.current_title == "Scan Type":
            footer = "Now: " + self.get_nmap_profile_label()
        elif self.current_title == "Settings":
            footer = "K1 Back K3 Home"
        elif self.current_title == "Power":
            footer = "Reboot/Shutdown"

        if footer:
            draw.rectangle(
                (0, self.lcd.height - 14, self.lcd.width, self.lcd.height),
                fill=(16, 16, 16),
            )
            draw.text(
                (2, self.lcd.height - 12),
                self.fit_text(footer, 20),
                font=self.font,
                fill=(180, 180, 180),
            )

        self.lcd.LCD_ShowImage(img)

    def show_message(
        self,
        title: str,
        lines: List[str],
        wait_for_back: bool = True,
        delay: float = 0.0,
    ):
        img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle((0, 0, self.lcd.width, 14), fill=(0, 0, 64))
        draw.text(
            (2, 2),
            self.fit_text(title, 20),
            font=self.font,
            fill=self.text_color,
        )

        y = 18
        for line in lines[:9]:
            draw.text(
                (2, y),
                self.fit_text(line, 20),
                font=self.font,
                fill=self.text_color,
            )
            y += 11

        if wait_for_back:
            draw.rectangle(
                (0, self.lcd.height - 14, self.lcd.width, self.lcd.height),
                fill=(16, 16, 16),
            )
            draw.text(
                (2, self.lcd.height - 12),
                "K1=Back K3=Home",
                font=self.font,
                fill=(128, 128, 128),
            )

        self.lcd.LCD_ShowImage(img)

        if delay > 0:
            time.sleep(delay)
            return

        if wait_for_back:
            while True:
                if self.check_home_button():
                    return

                if (
                    self.lcd.get_key_state("left")
                    or self.lcd.get_key_state("key1")
                    or self.lcd.get_key_state("press")
                    or self.lcd.get_key_state("key2")
                    or self.lcd.get_key_state("right")
                ):
                    time.sleep(0.08)
                    return
                time.sleep(0.05)

    def confirm_action(self, title: str, lines: List[str]) -> bool:
        while True:
            img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
            draw = ImageDraw.Draw(img)

            draw.rectangle((0, 0, self.lcd.width, 14), fill=(64, 0, 0))
            draw.text(
                (2, 2),
                self.fit_text(title, 20),
                font=self.font,
                fill=(255, 255, 255),
            )

            y = 20
            for line in lines[:7]:
                draw.text(
                    (2, y),
                    self.fit_text(line, 20),
                    font=self.font,
                    fill=(255, 255, 0),
                )
                y += 12

            draw.rectangle(
                (0, self.lcd.height - 14, self.lcd.width, self.lcd.height),
                fill=(16, 16, 16),
            )
            draw.text(
                (2, self.lcd.height - 12),
                "K2=Yes K1=No K3=Home",
                font=self.font,
                fill=(160, 160, 160),
            )

            self.lcd.LCD_ShowImage(img)

            if self.check_home_button():
                return False

            if (
                self.lcd.get_key_state("right")
                or self.lcd.get_key_state("press")
                or self.lcd.get_key_state("key2")
            ):
                time.sleep(0.08)
                return True

            if self.lcd.get_key_state("left") or self.lcd.get_key_state("key1"):
                time.sleep(0.08)
                return False

            time.sleep(0.05)

    # ------------------------------------------------------------------
    # Power actions
    # ------------------------------------------------------------------
    def run_power_command(self, action: str):
        systemctl_path = shutil.which("systemctl") or "/bin/systemctl"

        try:
            os.sync()
        except Exception:
            pass

        try:
            subprocess.run(
                [systemctl_path, action],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() if e.stderr else str(e)
            self.show_message("Power Error", [err or f"Failed: {action}"])
        except Exception as e:
            self.show_message("Power Error", [str(e)])

    def reboot_system(self):
        if not self.confirm_action("Confirm Reboot", ["Reboot system?"]):
            return

        self.show_message("Reboot", ["Rebooting..."], wait_for_back=False, delay=0.5)
        self.run_power_command("reboot")

    def shutdown_system(self):
        if not self.confirm_action("Confirm Shutdown", ["Shutdown system?"]):
            return

        self.show_message("Shutdown", ["Powering off..."], wait_for_back=False, delay=0.5)
        self.run_power_command("poweroff")

    # ------------------------------------------------------------------
    # System stats
    # ------------------------------------------------------------------
    def show_system_stats(self):
        while True:
            if self.check_home_button():
                return

            if self.lcd.get_key_state("left") or self.lcd.get_key_state("key1"):
                time.sleep(0.08)
                if self.lcd.get_key_state("left") or self.lcd.get_key_state("key1"):
                    return

            cpu_percent = psutil.cpu_percent(interval=0.2)
            temp_c = self.get_cpu_temp()

            disk = shutil.disk_usage("/")
            used_gb = disk.used / (1024 ** 3)
            total_gb = disk.total / (1024 ** 3)

            eth0_ip = self.get_interface_ipv4("eth0") or "N/A"
            wan_ip = self.get_external_ip()

            img = Image.new("RGB", (self.lcd.width, self.lcd.height), (0, 0, 0))
            draw = ImageDraw.Draw(img)

            draw.text((2, 2), "System Stats", font=self.font, fill=(0, 255, 255))

            y = 16
            line_h = 11

            draw.text(
                (2, y),
                self.fit_text(f"CPU : {cpu_percent:4.1f}%", 20),
                font=self.font,
                fill=(255, 255, 255),
            )
            y += line_h

            if temp_c is not None:
                draw.text(
                    (2, y),
                    self.fit_text(f"Temp: {temp_c:4.1f}C", 20),
                    font=self.font,
                    fill=(255, 255, 255),
                )
            else:
                draw.text((2, y), "Temp: N/A", font=self.font, fill=(255, 255, 255))
            y += line_h

            draw.text(
                (2, y),
                self.fit_text(f"Disk: {used_gb:.1f}/{total_gb:.1f}G", 20),
                font=self.font,
                fill=(255, 255, 255),
            )
            y += line_h

            draw.text(
                (2, y),
                self.fit_text(f"eth0: {eth0_ip}", 20),
                font=self.font,
                fill=(255, 255, 0),
            )
            y += line_h

            draw.text(
                (2, y),
                self.fit_text(f"WAN : {wan_ip}", 20),
                font=self.font,
                fill=(0, 255, 0),
            )

            draw.rectangle(
                (0, self.lcd.height - 14, self.lcd.width, self.lcd.height),
                fill=(16, 16, 16),
            )
            draw.text(
                (2, self.lcd.height - 12),
                "K1=Back K3=Home",
                font=self.font,
                fill=(128, 128, 128),
            )

            self.lcd.LCD_ShowImage(img)
            time.sleep(0.25)

    @staticmethod
    def get_cpu_temp() -> Optional[float]:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            return None

    @staticmethod
    def get_interface_ipv4(interface_name: str) -> Optional[str]:
        try:
            addrs = psutil.net_if_addrs()
            if interface_name not in addrs:
                return None
            for addr in addrs[interface_name]:
                if addr.family == socket.AF_INET:
                    return addr.address
        except Exception:
            pass
        return None

    def get_external_ip(self, max_age: int = 60) -> str:
        now = time.time()
        if now - self._external_ip_last_update < max_age:
            return self._external_ip_cache

        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=2) as response:
                self._external_ip_cache = response.read().decode("utf-8").strip()
        except Exception:
            pass

        self._external_ip_last_update = now
        return self._external_ip_cache

    # ------------------------------------------------------------------
    # Nmap settings
    # ------------------------------------------------------------------
    def set_nmap_profile(self, profile: str):
        self.nmap_profile = profile
        self.show_message(
            "Nmap Type",
            [
                "Set to:",
                self.get_nmap_profile_label(),
            ],
            wait_for_back=False,
            delay=1.0,
        )

    def get_nmap_profile_label(self) -> str:
        labels = {
            "ping": "Ping Sweep",
            "basic": "Basic Service",
            "vuln": "Vuln Scripts",
        }
        return labels.get(self.nmap_profile, self.nmap_profile)

    def scan_profile_label_to_key(self, label: str) -> str:
        mapping = {
            "Ping Sweep": "ping",
            "Basic Service": "basic",
            "Vuln Scripts": "vuln",
        }
        return mapping.get(label, "")

    # ------------------------------------------------------------------
    # Network / nmap helpers
    # ------------------------------------------------------------------
    def get_eth0_network(self) -> Tuple[Optional[str], Optional[str]]:
        try:
            addrs = psutil.net_if_addrs()
            if "eth0" not in addrs:
                return None, None

            for addr in addrs["eth0"]:
                if addr.family == socket.AF_INET and addr.address and addr.netmask:
                    iface = ipaddress.IPv4Interface(f"{addr.address}/{addr.netmask}")
                    return str(iface.ip), str(iface.network)
        except Exception:
            pass

        return None, None

    def build_nmap_command(self, subnet: str, own_ip: str) -> List[str]:
        base = [
            "nmap",
            "-n",
            "--exclude", own_ip,
            "-oX", self.nmap_xml_output_file,
        ]

        if self.nmap_profile == "ping":
            return base + [
                "-sn",
                subnet,
            ]

        if self.nmap_profile == "basic":
            return base + [
                "-sV",
                "--top-ports", "100",
                "-T4",
                subnet,
            ]

        if self.nmap_profile == "vuln":
            return base + [
                "-sV",
                "--script", "vuln",
                "-T4",
                subnet,
            ]

        return base + [
            "-sn",
            subnet,
        ]

    def summarize_nmap_output(self, text: str) -> List[str]:
        hosts = []
        for line in text.splitlines():
            if line.startswith("Nmap scan report for "):
                host = line.replace("Nmap scan report for ", "").strip()
                if host not in hosts:
                    hosts.append(host)

        lines = [
            "Type: " + self.get_nmap_profile_label(),
            f"Hosts: {len(hosts)}",
        ]

        for host in hosts[:6]:
            lines.append(host)

        if len(hosts) > 6:
            lines.append("...")

        return lines

    # ------------------------------------------------------------------
    # Nmap actions
    # ------------------------------------------------------------------
    def run_nmap_scan(self):
        if shutil.which("nmap") is None:
            self.show_message("Nmap", ["nmap not found", "sudo apt install", "nmap"])
            return

        own_ip, subnet = self.get_eth0_network()
        if not own_ip or not subnet:
            self.show_message("Nmap", ["eth0 not ready", "No IPv4/netmask"])
            return

        cmd = self.build_nmap_command(subnet, own_ip)

        try:
            with open(self.nmap_text_output_file, "w") as out:
                proc = subprocess.Popen(
                    cmd,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Nmap Running", font=self.font, fill=(0, 255, 255))
                    draw.text(
                        (2, 20),
                        self.fit_text(self.get_nmap_profile_label(), 20),
                        font=self.font,
                        fill=(255, 255, 255),
                    )
                    draw.text(
                        (2, 32),
                        self.fit_text(f"Net: {subnet}", 20),
                        font=self.font,
                        fill=(255, 255, 0),
                    )
                    draw.text(
                        (2, 44),
                        self.fit_text(f"Excl:{own_ip}", 20),
                        font=self.font,
                        fill=(255, 255, 0),
                    )
                    draw.text(
                        (2, 60),
                        f"Scan {spinner[i % len(spinner)]}",
                        font=self.font,
                        fill=(0, 255, 0),
                    )

                    draw.rectangle(
                        (0, self.lcd.height - 14, self.lcd.width, self.lcd.height),
                        fill=(16, 16, 16),
                    )
                    draw.text(
                        (2, self.lcd.height - 12),
                        "K1=Cancel K3=Home",
                        font=self.font,
                        fill=(128, 128, 128),
                    )

                    self.lcd.LCD_ShowImage(img)
                    i += 1

                    if self.check_home_button():
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except Exception:
                            proc.kill()
                        return

                    if self.lcd.get_key_state("left") or self.lcd.get_key_state("key1"):
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except Exception:
                            proc.kill()
                        self.show_message("Nmap", ["Scan cancelled"])
                        return

                    time.sleep(0.2)

            with open(self.nmap_text_output_file, "r") as f:
                result_text = f.read()

            lines = self.summarize_nmap_output(result_text)
            self.show_message("Nmap Done", lines)

        except Exception as e:
            self.show_message("Nmap Error", [str(e)])

    def show_last_nmap_result(self):
        if not os.path.exists(self.nmap_text_output_file):
            self.show_message("Nmap Result", ["No saved result"])
            return

        try:
            with open(self.nmap_text_output_file, "r") as f:
                text = f.read()

            lines = self.summarize_nmap_output(text)
            if len(lines) <= 2:
                lines.append("No hosts found")

            self.show_message("Last Result", lines)

        except Exception as e:
            self.show_message("Read Error", [str(e)])

    def convert_nmap_to_html(self):
        xml_exists = os.path.exists(self.nmap_xml_output_file)
        txt_exists = os.path.exists(self.nmap_text_output_file)

        if not xml_exists and not txt_exists:
            self.show_message("Convert HTML", ["No scan result", "Run scan first"])
            return

        try:
            if xml_exists and shutil.which("xsltproc") is not None:
                subprocess.run(
                    [
                        "xsltproc",
                        "-o", self.nmap_html_output_file,
                        self.nmap_xml_output_file,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                self.show_message(
                    "HTML Saved",
                    [
                        "Created:",
                        os.path.basename(self.nmap_html_output_file),
                        "Method: xsltproc",
                    ],
                )
                return

            if txt_exists:
                with open(self.nmap_text_output_file, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()

                html_doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Nmap Report</title>
<style>
body {{
  background: #111;
  color: #eee;
  font-family: monospace;
  padding: 1rem;
}}
pre {{
  white-space: pre-wrap;
  word-wrap: break-word;
}}
h1 {{
  color: #7CFC00;
}}
</style>
</head>
<body>
<h1>Nmap Report</h1>
<p>Profile: {html.escape(self.get_nmap_profile_label())}</p>
<pre>{html.escape(text)}</pre>
</body>
</html>
"""
                with open(self.nmap_html_output_file, "w", encoding="utf-8") as f:
                    f.write(html_doc)

                self.show_message(
                    "HTML Saved",
                    [
                        "Created:",
                        os.path.basename(self.nmap_html_output_file),
                        "Method: simple",
                    ],
                )
                return

            self.show_message("Convert HTML", ["Nothing to convert"])

        except Exception as e:
            self.show_message("HTML Error", [str(e)])


def main():
    lcd = LCD()
    try:
        lcd.LCD_Init()
        lcd.LCD_Clear(0x0000)

        app = MenuApp(lcd)
        app.show_splash(duration=2.5, image_path="splash.png")
        app.run()

    finally:
        lcd.module_exit()


if __name__ == "__main__":
    main()
