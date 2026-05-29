#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import html
import ipaddress
import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Any

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

        # --------------------------------------------------------------
        # Central choice lists
        # Edit these to add/remove choices later
        # --------------------------------------------------------------
        self.target_choices: List[Tuple[str, str]] = [
            ("Gateway", "gateway"),
            ("192.168.178.1", "192.168.178.1"),
            ("172.16.0.1", "172.16.0.1"),
            ("192.168.0.1", "192.168.0.1"),
            ("192.168.2.1", "192.168.2.1"),
            ("192.168.99.99", "192.168.99.99"),
            ("10.10.1.1", "10.10.1.1"),
            ("10.0.0.1", "10.0.0.1"),
            ("1.1.1.1", "1.1.1.1"),
            ("8.8.8.8", "8.8.8.8"),
        ]

        self.nmap_profile_choices: List[Tuple[str, str]] = [
            ("Ping Sweep", "ping"),
            ("Basic Service", "basic"),
            ("Vuln Scripts", "vuln"),
        ]

        self.netcat_port_choices: List[int] = [22, 53, 80, 443]

        self.speedtest_secure_choices: List[Tuple[str, bool]] = [
            ("On", True),
            ("Off", False),
        ]

        self.ping_count_choices: List[int] = [4, 10]
        self.traceroute_hop_choices: List[int] = [10, 20, 30]
        self.duration_choices: List[int] = [5, 10, 30]

        self.iperf_port_choices: List[int] = [5001, 5201]
        self.iperf3_port_choices: List[int] = [5201, 5202]

        self.iperf_direction_choices: List[Tuple[str, bool]] = [
            ("Normal", False),
            ("Tradeoff", True),
        ]

        self.iperf3_direction_choices: List[Tuple[str, bool]] = [
            ("Normal", False),
            ("Reverse", True),
        ]

        # --------------------------------------------------------------
        # Current tool settings
        # --------------------------------------------------------------
        self.nmap_profile = "ping"
        self.netcat_port = 80
        self.speedtest_secure = True

        self.ping_target = "gateway"
        self.ping_count = 4

        self.traceroute_target = "gateway"
        self.traceroute_max_hops = 20

        self.iperf_server = "gateway"
        self.iperf_port = 5001
        self.iperf_tradeoff = False
        self.iperf_duration = 10

        self.iperf3_server = "gateway"
        self.iperf3_port = 5201
        self.iperf3_reverse = False
        self.iperf3_duration = 10

        # --------------------------------------------------------------
        # Output files
        # --------------------------------------------------------------
        self.nmap_text_output_file = os.path.expanduser("~/nmap_last.txt")
        self.nmap_xml_output_file = os.path.expanduser("~/nmap_last.xml")
        self.nmap_html_output_file = os.path.expanduser("~/nmap_last.html")

        self.netcat_output_file = os.path.expanduser("~/netcat_last.txt")
        self.speedtest_output_file = os.path.expanduser("~/speedtest_last.txt")
        self.ping_output_file = os.path.expanduser("~/ping_last.txt")
        self.traceroute_output_file = os.path.expanduser("~/traceroute_last.txt")
        self.iperf_output_file = os.path.expanduser("~/iperf_last.txt")
        self.iperf3_output_file = os.path.expanduser("~/iperf3_last.txt")

        self.root_menu = self.build_menu()

        # (menu_list, selected_index, top_index, title)
        self.menu_stack: List[Tuple[List[MenuItem], int, int, str]] = []
        self.current_menu = self.root_menu
        self.current_index = 0
        self.current_top = 0
        self.current_title = "Main Menu"

    # ------------------------------------------------------------------
    # Generic menu builders / label helpers
    # ------------------------------------------------------------------
    def build_choice_menu(self, choices: List[Tuple[str, Any]], setter: Callable[[Any], None]) -> List[MenuItem]:
        return [
            MenuItem(label, action=lambda value=value: setter(value))
            for label, value in choices
        ]

    def build_value_menu(self, values: List[Any], setter: Callable[[Any], None]) -> List[MenuItem]:
        return [
            MenuItem(str(value), action=lambda value=value: setter(value))
            for value in values
        ]

    def get_choice_label(self, choices: List[Tuple[str, Any]], value: Any) -> str:
        for label, stored in choices:
            if stored == value:
                return label
        return str(value)

    def get_choice_labels(self, choices: List[Tuple[str, Any]]) -> Tuple[str, ...]:
        return tuple(label for label, _ in choices)

    def get_menu_path_titles(self) -> List[str]:
        return [title for _, _, _, title in self.menu_stack] + [self.current_title]

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

        tools_netcat_menu = [
            MenuItem("Run Check", action=self.run_netcat_check),
            MenuItem("Last Result", action=self.show_last_netcat_result),
        ]

        tools_speedtest_menu = [
            MenuItem("Run Test", action=self.run_speedtest),
            MenuItem("Last Result", action=self.show_last_speedtest_result),
        ]

        tools_ping_menu = [
            MenuItem("Run", action=self.run_ping),
            MenuItem("Last Result", action=self.show_last_ping_result),
        ]

        tools_traceroute_menu = [
            MenuItem("Run", action=self.run_traceroute),
            MenuItem("Last Result", action=self.show_last_traceroute_result),
        ]

        tools_iperf_menu = [
            MenuItem("Run", action=self.run_iperf),
            MenuItem("Last Result", action=self.show_last_iperf_result),
        ]

        tools_iperf3_menu = [
            MenuItem("Run", action=self.run_iperf3),
            MenuItem("Last Result", action=self.show_last_iperf3_result),
        ]

        tools_menu = [
            MenuItem("Nmap", submenu=tools_nmap_menu),
            MenuItem("Netcat", submenu=tools_netcat_menu),
            MenuItem("Speedtest", submenu=tools_speedtest_menu),
            MenuItem("Ping", submenu=tools_ping_menu),
            MenuItem("Traceroute", submenu=tools_traceroute_menu),
            MenuItem("Iperf", submenu=tools_iperf_menu),
            MenuItem("Iperf3", submenu=tools_iperf3_menu),
        ]

        nmap_settings_menu = [
            MenuItem("Scan Type", submenu=self.build_choice_menu(self.nmap_profile_choices, self.set_nmap_profile)),
        ]

        netcat_settings_menu = [
            MenuItem("Port", submenu=self.build_value_menu(self.netcat_port_choices, self.set_netcat_port)),
        ]

        speedtest_settings_menu = [
            MenuItem("Secure", submenu=self.build_choice_menu(self.speedtest_secure_choices, self.set_speedtest_secure)),
        ]

        ping_settings_menu = [
            MenuItem("Ping Target", submenu=self.build_choice_menu(self.target_choices, self.set_ping_target)),
            MenuItem("Ping Count", submenu=self.build_value_menu(self.ping_count_choices, self.set_ping_count)),
        ]

        traceroute_settings_menu = [
            MenuItem("Trace Target", submenu=self.build_choice_menu(self.target_choices, self.set_traceroute_target)),
            MenuItem("Max Hops", submenu=self.build_value_menu(self.traceroute_hop_choices, self.set_traceroute_max_hops)),
        ]

        iperf_settings_menu = [
            MenuItem("Server", submenu=self.build_choice_menu(self.target_choices, self.set_iperf_server)),
            MenuItem("Port", submenu=self.build_value_menu(self.iperf_port_choices, self.set_iperf_port)),
            MenuItem("Direction", submenu=self.build_choice_menu(self.iperf_direction_choices, self.set_iperf_tradeoff)),
            MenuItem("Duration", submenu=self.build_value_menu(self.duration_choices, self.set_iperf_duration)),
        ]

        iperf3_settings_menu = [
            MenuItem("Server", submenu=self.build_choice_menu(self.target_choices, self.set_iperf3_server)),
            MenuItem("Port", submenu=self.build_value_menu(self.iperf3_port_choices, self.set_iperf3_port)),
            MenuItem("Direction", submenu=self.build_choice_menu(self.iperf3_direction_choices, self.set_iperf3_reverse)),
            MenuItem("Duration", submenu=self.build_value_menu(self.duration_choices, self.set_iperf3_duration)),
        ]

        power_menu = [
            MenuItem("Reboot", action=self.reboot_system),
            MenuItem("Shutdown", action=self.shutdown_system),
        ]

        settings_menu = [
            MenuItem("Nmap", submenu=nmap_settings_menu),
            MenuItem("Netcat", submenu=netcat_settings_menu),
            MenuItem("Speedtest", submenu=speedtest_settings_menu),
            MenuItem("Ping", submenu=ping_settings_menu),
            MenuItem("Traceroute", submenu=traceroute_settings_menu),
            MenuItem("Iperf", submenu=iperf_settings_menu),
            MenuItem("Iperf3", submenu=iperf3_settings_menu),
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
        draw.rectangle((0, self.lcd.height - 16, self.lcd.width, self.lcd.height), fill=(16, 16, 16))

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
    def ensure_selection_visible(self):
        visible_lines = 8
        if self.current_index < self.current_top:
            self.current_top = self.current_index
        elif self.current_index >= self.current_top + visible_lines:
            self.current_top = self.current_index - visible_lines + 1

    def move_selection(self, delta: int):
        if self.current_menu:
            self.current_index = (self.current_index + delta) % len(self.current_menu)
            self.ensure_selection_visible()

    def enter_item(self):
        if not self.current_menu:
            return

        item = self.current_menu[self.current_index]

        if item.submenu:
            self.menu_stack.append(
                (self.current_menu, self.current_index, self.current_top, self.current_title)
            )
            self.current_menu = item.submenu
            self.current_index = 0
            self.current_top = 0
            self.current_title = item.title
            return

        if item.action is not None:
            item.action()

    def go_back(self):
        if not self.menu_stack:
            return
        self.current_menu, self.current_index, self.current_top, self.current_title = self.menu_stack.pop()

    def go_home(self):
        self.menu_stack.clear()
        self.current_menu = self.root_menu
        self.current_index = 0
        self.current_top = 0
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

    def wrap_lines_for_display(self, lines: List[str], width: int = 20) -> List[str]:
        wrapped = []
        for line in lines:
            line = str(line).rstrip()
            if not line:
                wrapped.append("")
                continue

            chunks = textwrap.wrap(
                line,
                width=width,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
            if chunks:
                wrapped.extend(chunks)
            else:
                wrapped.append("")
        return wrapped

    def show_scrollable_lines(self, title: str, lines: List[str], width: int = 20):
        wrapped = self.wrap_lines_for_display(lines, width=width)
        if not wrapped:
            wrapped = ["No output"]

        top_index = 0
        line_h = 11
        visible_lines = 8

        while True:
            img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
            draw = ImageDraw.Draw(img)

            draw.rectangle((0, 0, self.lcd.width, 14), fill=(0, 0, 64))
            draw.text((2, 2), self.fit_text(title, 20), font=self.font, fill=self.text_color)

            y = 16
            end_index = min(top_index + visible_lines, len(wrapped))
            for line in wrapped[top_index:end_index]:
                draw.text((2, y), self.fit_text(line, 20), font=self.font, fill=self.text_color)
                y += line_h

            footer = f"{top_index + 1}-{end_index}/{len(wrapped)}"
            draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
            draw.text((2, self.lcd.height - 12), self.fit_text(footer, 20), font=self.font, fill=(128, 128, 128))

            self.lcd.LCD_ShowImage(img)

            if self.check_home_button():
                return

            if self.lcd.get_key_state("left") or self.lcd.get_key_state("key1"):
                time.sleep(0.08)
                return

            if self.lcd.get_key_state("up"):
                if top_index > 0:
                    top_index -= 1
                self.wait_for_key_release("up")
                continue

            if self.lcd.get_key_state("down"):
                if top_index < max(0, len(wrapped) - visible_lines):
                    top_index += 1
                self.wait_for_key_release("down")
                continue

            time.sleep(0.05)

    def draw_menu(self):
        path = self.get_menu_path_titles()

        img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle((0, 0, self.lcd.width, 14), fill=(0, 0, 64))
        draw.text((2, 2), self.fit_text(self.current_title, 20), font=self.font, fill=self.text_color)

        y = 18
        line_h = 12
        visible_lines = 8

        start = self.current_top
        end = min(start + visible_lines, len(self.current_menu))

        nmap_labels = self.get_choice_labels(self.nmap_profile_choices)
        target_labels = self.get_choice_labels(self.target_choices)
        speedtest_labels = self.get_choice_labels(self.speedtest_secure_choices)
        iperf_dir_labels = self.get_choice_labels(self.iperf_direction_choices)
        iperf3_dir_labels = self.get_choice_labels(self.iperf3_direction_choices)

        for idx in range(start, end):
            item = self.current_menu[idx]

            selected = idx == self.current_index
            if selected:
                draw.rectangle((0, y - 1, self.lcd.width, y + line_h - 1), fill=(32, 32, 32))
                color = self.highlight_color
                prefix = ">"
            else:
                color = self.text_color
                prefix = " "

            title = item.title

            if self.current_title == "Scan Type" and title in nmap_labels:
                if self.get_nmap_profile_label() == title:
                    title = "* " + title

            if self.current_title == "Secure" and title in speedtest_labels:
                if self.get_speedtest_secure_label() == title:
                    title = "* " + title

            if self.current_title == "Ping Target" and title in target_labels:
                if self.get_ping_target_label() == title:
                    title = "* " + title

            if self.current_title == "Ping Count" and title in tuple(str(v) for v in self.ping_count_choices):
                if int(title) == self.ping_count:
                    title = "* " + title

            if self.current_title == "Trace Target" and title in target_labels:
                if self.get_traceroute_target_label() == title:
                    title = "* " + title

            if self.current_title == "Max Hops" and title in tuple(str(v) for v in self.traceroute_hop_choices):
                if int(title) == self.traceroute_max_hops:
                    title = "* " + title

            if self.current_title == "Server" and title in target_labels:
                if "Iperf3" in path and self.get_iperf3_server_label() == title:
                    title = "* " + title
                elif "Iperf" in path and self.get_iperf_server_label() == title:
                    title = "* " + title

            if self.current_title == "Port":
                if "Netcat" in path and title in tuple(str(v) for v in self.netcat_port_choices):
                    if int(title) == self.netcat_port:
                        title = "* " + title
                elif "Iperf3" in path and title in tuple(str(v) for v in self.iperf3_port_choices):
                    if int(title) == self.iperf3_port:
                        title = "* " + title
                elif "Iperf" in path and title in tuple(str(v) for v in self.iperf_port_choices):
                    if int(title) == self.iperf_port:
                        title = "* " + title

            if self.current_title == "Direction":
                if "Iperf3" in path and title in iperf3_dir_labels:
                    if self.get_iperf3_direction_label() == title:
                        title = "* " + title
                elif "Iperf" in path and title in iperf_dir_labels:
                    if self.get_iperf_direction_label() == title:
                        title = "* " + title

            if self.current_title == "Duration" and title in tuple(str(v) for v in self.duration_choices):
                if "Iperf3" in path and int(title) == self.iperf3_duration:
                    title = "* " + title
                elif "Iperf" in path and int(title) == self.iperf_duration:
                    title = "* " + title

            draw.text((2, y), self.fit_text(prefix + " " + title, 20), font=self.font, fill=color)
            y += line_h

        footer = ""
        if self.current_title == "Main Menu":
            footer = "K2 OK  K3 Home"
        elif self.current_title == "Tools":
            footer = "Choose tool"
        elif self.current_title == "Nmap":
            footer = self.get_nmap_profile_label()
        elif self.current_title == "Netcat":
            footer = "Port: " + self.get_netcat_port_label()
        elif self.current_title == "Speedtest":
            footer = "Secure: " + self.get_speedtest_secure_label()
        elif self.current_title == "Ping":
            footer = self.fit_text(f"{self.get_ping_target_label()} x{self.ping_count}", 20)
        elif self.current_title == "Traceroute":
            footer = self.fit_text(f"{self.get_traceroute_target_label()} h{self.traceroute_max_hops}", 20)
        elif self.current_title == "Iperf":
            footer = self.fit_text(f"{self.get_iperf_server_label()} {self.get_iperf_direction_label()}", 20)
        elif self.current_title == "Iperf3":
            footer = self.fit_text(f"{self.get_iperf3_server_label()} {self.get_iperf3_direction_label()}", 20)
        elif self.current_title == "Scan Type":
            footer = "Now: " + self.get_nmap_profile_label()
        elif self.current_title == "Secure":
            footer = "Now: " + self.get_speedtest_secure_label()
        elif self.current_title == "Ping Target":
            footer = "Now: " + self.get_ping_target_label()
        elif self.current_title == "Ping Count":
            footer = "Now: " + str(self.ping_count)
        elif self.current_title == "Trace Target":
            footer = "Now: " + self.get_traceroute_target_label()
        elif self.current_title == "Max Hops":
            footer = "Now: " + str(self.traceroute_max_hops)
        elif self.current_title == "Server":
            if "Iperf3" in path:
                footer = "Now: " + self.get_iperf3_server_label()
            elif "Iperf" in path:
                footer = "Now: " + self.get_iperf_server_label()
        elif self.current_title == "Port":
            if "Netcat" in path:
                footer = "Now: " + self.get_netcat_port_label()
            elif "Iperf3" in path:
                footer = "Now: " + str(self.iperf3_port)
            elif "Iperf" in path:
                footer = "Now: " + str(self.iperf_port)
        elif self.current_title == "Direction":
            if "Iperf3" in path:
                footer = "Now: " + self.get_iperf3_direction_label()
            elif "Iperf" in path:
                footer = "Now: " + self.get_iperf_direction_label()
        elif self.current_title == "Duration":
            if "Iperf3" in path:
                footer = "Now: " + str(self.iperf3_duration)
            elif "Iperf" in path:
                footer = "Now: " + str(self.iperf_duration)
        elif self.current_title == "Settings":
            footer = f"{self.current_index + 1}/{len(self.current_menu)}"
        elif self.current_title == "Power":
            footer = "Reboot/Shutdown"

        if footer:
            draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
            draw.text((2, self.lcd.height - 12), self.fit_text(footer, 20), font=self.font, fill=(180, 180, 180))

        self.lcd.LCD_ShowImage(img)

    def show_message(self, title: str, lines: List[str], wait_for_back: bool = True, delay: float = 0.0):
        img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle((0, 0, self.lcd.width, 14), fill=(0, 0, 64))
        draw.text((2, 2), self.fit_text(title, 20), font=self.font, fill=self.text_color)

        y = 18
        for line in lines[:9]:
            draw.text((2, y), self.fit_text(line, 20), font=self.font, fill=self.text_color)
            y += 11

        if wait_for_back:
            draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
            draw.text((2, self.lcd.height - 12), "K1=Back K3=Home", font=self.font, fill=(128, 128, 128))

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
            draw.text((2, 2), self.fit_text(title, 20), font=self.font, fill=(255, 255, 255))

            y = 20
            for line in lines[:7]:
                draw.text((2, y), self.fit_text(line, 20), font=self.font, fill=(255, 255, 0))
                y += 12

            draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
            draw.text((2, self.lcd.height - 12), "K2=Yes K1=No K3=Home", font=self.font, fill=(160, 160, 160))

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

            draw.text((2, y), self.fit_text(f"CPU : {cpu_percent:4.1f}%", 20), font=self.font, fill=(255, 255, 255))
            y += line_h

            if temp_c is not None:
                draw.text((2, y), self.fit_text(f"Temp: {temp_c:4.1f}C", 20), font=self.font, fill=(255, 255, 255))
            else:
                draw.text((2, y), "Temp: N/A", font=self.font, fill=(255, 255, 255))
            y += line_h

            draw.text((2, y), self.fit_text(f"Disk: {used_gb:.1f}/{total_gb:.1f}G", 20), font=self.font, fill=(255, 255, 255))
            y += line_h

            draw.text((2, y), self.fit_text(f"eth0: {eth0_ip}", 20), font=self.font, fill=(255, 255, 0))
            y += line_h

            draw.text((2, y), self.fit_text(f"WAN : {wan_ip}", 20), font=self.font, fill=(0, 255, 0))

            draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
            draw.text((2, self.lcd.height - 12), "K1=Back K3=Home", font=self.font, fill=(128, 128, 128))

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
    # Common network helpers
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

    def get_default_gateway(self, interface: str = "eth0") -> Optional[str]:
        try:
            proc = subprocess.run(
                ["ip", "route", "show", "default", "dev", interface],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            for line in proc.stdout.splitlines():
                parts = line.split()
                if "via" in parts:
                    idx = parts.index("via")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
        except Exception:
            pass
        return None

    def resolve_target(self, target_name: str) -> Tuple[Optional[str], str]:
        if target_name == "gateway":
            gw = self.get_default_gateway("eth0")
            return gw, "Gateway"
        return target_name, target_name

    # ------------------------------------------------------------------
    # Nmap settings / labels
    # ------------------------------------------------------------------
    def set_nmap_profile(self, profile: str):
        self.nmap_profile = profile
        self.show_message("Nmap Type", ["Set to:", self.get_nmap_profile_label()], wait_for_back=False, delay=1.0)

    def get_nmap_profile_label(self) -> str:
        return self.get_choice_label(self.nmap_profile_choices, self.nmap_profile)

    # ------------------------------------------------------------------
    # Netcat settings / labels
    # ------------------------------------------------------------------
    def set_netcat_port(self, port: int):
        self.netcat_port = port
        self.show_message("Netcat Port", ["Set to:", str(port)], wait_for_back=False, delay=1.0)

    def get_netcat_port_label(self) -> str:
        return str(self.netcat_port)

    # ------------------------------------------------------------------
    # Speedtest settings / labels
    # ------------------------------------------------------------------
    def set_speedtest_secure(self, enabled: bool):
        self.speedtest_secure = enabled
        self.show_message("Speedtest", ["Secure:", self.get_speedtest_secure_label()], wait_for_back=False, delay=1.0)

    def get_speedtest_secure_label(self) -> str:
        return self.get_choice_label(self.speedtest_secure_choices, self.speedtest_secure)

    # ------------------------------------------------------------------
    # Ping settings / labels
    # ------------------------------------------------------------------
    def set_ping_target(self, target: str):
        self.ping_target = target
        self.show_message("Ping Target", ["Set to:", self.get_ping_target_label()], wait_for_back=False, delay=1.0)

    def get_ping_target_label(self) -> str:
        return self.get_choice_label(self.target_choices, self.ping_target)

    def set_ping_count(self, count: int):
        self.ping_count = count
        self.show_message("Ping Count", ["Set to:", str(count)], wait_for_back=False, delay=1.0)

    # ------------------------------------------------------------------
    # Traceroute settings / labels
    # ------------------------------------------------------------------
    def set_traceroute_target(self, target: str):
        self.traceroute_target = target
        self.show_message("Trace Target", ["Set to:", self.get_traceroute_target_label()], wait_for_back=False, delay=1.0)

    def get_traceroute_target_label(self) -> str:
        return self.get_choice_label(self.target_choices, self.traceroute_target)

    def set_traceroute_max_hops(self, hops: int):
        self.traceroute_max_hops = hops
        self.show_message("Max Hops", ["Set to:", str(hops)], wait_for_back=False, delay=1.0)

    # ------------------------------------------------------------------
    # Iperf settings / labels
    # ------------------------------------------------------------------
    def set_iperf_server(self, server: str):
        self.iperf_server = server
        self.show_message("Iperf Server", ["Set to:", self.get_iperf_server_label()], wait_for_back=False, delay=1.0)

    def get_iperf_server_label(self) -> str:
        return self.get_choice_label(self.target_choices, self.iperf_server)

    def set_iperf_port(self, port: int):
        self.iperf_port = port
        self.show_message("Iperf Port", ["Set to:", str(port)], wait_for_back=False, delay=1.0)

    def set_iperf_tradeoff(self, tradeoff: bool):
        self.iperf_tradeoff = tradeoff
        self.show_message("Iperf Dir", ["Set to:", self.get_iperf_direction_label()], wait_for_back=False, delay=1.0)

    def get_iperf_direction_label(self) -> str:
        return self.get_choice_label(self.iperf_direction_choices, self.iperf_tradeoff)

    def set_iperf_duration(self, duration: int):
        self.iperf_duration = duration
        self.show_message("Iperf Time", ["Set to:", str(duration)], wait_for_back=False, delay=1.0)

    # ------------------------------------------------------------------
    # Iperf3 settings / labels
    # ------------------------------------------------------------------
    def set_iperf3_server(self, server: str):
        self.iperf3_server = server
        self.show_message("Iperf3 Server", ["Set to:", self.get_iperf3_server_label()], wait_for_back=False, delay=1.0)

    def get_iperf3_server_label(self) -> str:
        return self.get_choice_label(self.target_choices, self.iperf3_server)

    def set_iperf3_port(self, port: int):
        self.iperf3_port = port
        self.show_message("Iperf3 Port", ["Set to:", str(port)], wait_for_back=False, delay=1.0)

    def set_iperf3_reverse(self, reverse: bool):
        self.iperf3_reverse = reverse
        self.show_message("Iperf3 Dir", ["Set to:", self.get_iperf3_direction_label()], wait_for_back=False, delay=1.0)

    def get_iperf3_direction_label(self) -> str:
        return self.get_choice_label(self.iperf3_direction_choices, self.iperf3_reverse)

    def set_iperf3_duration(self, duration: int):
        self.iperf3_duration = duration
        self.show_message("Iperf3 Time", ["Set to:", str(duration)], wait_for_back=False, delay=1.0)

    # ------------------------------------------------------------------
    # Nmap actions
    # ------------------------------------------------------------------
    def build_nmap_command(self, subnet: str, own_ip: str) -> List[str]:
        base = ["nmap", "-n", "--exclude", own_ip, "-oX", self.nmap_xml_output_file]
        if self.nmap_profile == "ping":
            return base + ["-sn", subnet]
        if self.nmap_profile == "basic":
            return base + ["-sV", "--top-ports", "100", "-T4", subnet]
        if self.nmap_profile == "vuln":
            return base + ["-sV", "--script", "vuln", "-T4", subnet]
        return base + ["-sn", subnet]

    def summarize_nmap_output(self, text: str) -> List[str]:
        hosts = []
        for line in text.splitlines():
            if line.startswith("Nmap scan report for "):
                host = line.replace("Nmap scan report for ", "").strip()
                if host not in hosts:
                    hosts.append(host)

        lines = ["Type: " + self.get_nmap_profile_label(), f"Hosts: {len(hosts)}"]
        for host in hosts[:6]:
            lines.append(host)
        if len(hosts) > 6:
            lines.append("...")
        return lines

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
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Nmap Running", font=self.font, fill=(0, 255, 255))
                    draw.text((2, 20), self.fit_text(self.get_nmap_profile_label(), 20), font=self.font, fill=(255, 255, 255))
                    draw.text((2, 32), self.fit_text(f"Net: {subnet}", 20), font=self.font, fill=(255, 255, 0))
                    draw.text((2, 44), self.fit_text(f"Excl:{own_ip}", 20), font=self.font, fill=(255, 255, 0))
                    draw.text((2, 60), f"Scan {spinner[i % len(spinner)]}", font=self.font, fill=(0, 255, 0))
                    draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
                    draw.text((2, self.lcd.height - 12), "K1=Cancel K3=Home", font=self.font, fill=(128, 128, 128))
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

            self.show_message("Nmap Done", self.summarize_nmap_output(result_text))

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
                    ["xsltproc", "-o", self.nmap_html_output_file, self.nmap_xml_output_file],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.show_message("HTML Saved", ["Created:", os.path.basename(self.nmap_html_output_file), "Method: xsltproc"])
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

                self.show_message("HTML Saved", ["Created:", os.path.basename(self.nmap_html_output_file), "Method: simple"])
                return

            self.show_message("Convert HTML", ["Nothing to convert"])

        except Exception as e:
            self.show_message("HTML Error", [str(e)])

    # ------------------------------------------------------------------
    # Netcat actions
    # ------------------------------------------------------------------
    def tcp_connect_check(self, host: str, port: int, timeout: float = 2.0) -> Tuple[bool, str]:
        nc_path = shutil.which("nc")

        if nc_path:
            try:
                proc = subprocess.run(
                    [nc_path, "-vz", "-w", str(int(timeout)), host, str(port)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                output = (proc.stdout + "\n" + proc.stderr).strip()
                return proc.returncode == 0, output or ("Connected" if proc.returncode == 0 else "Connection failed")
            except Exception as e:
                return False, str(e)

        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, f"Connected to {host}:{port}"
        except Exception as e:
            return False, str(e)

    def run_netcat_check(self):
        gateway = self.get_default_gateway("eth0")
        if not gateway:
            self.show_message("Netcat", ["No eth0 gateway", "found"])
            return

        port = self.netcat_port

        img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        draw.text((2, 2), "Netcat Check", font=self.font, fill=(0, 255, 255))
        draw.text((2, 22), self.fit_text(f"Host: {gateway}", 20), font=self.font, fill=(255, 255, 255))
        draw.text((2, 34), f"Port: {port}", font=self.font, fill=(255, 255, 0))
        draw.text((2, 50), "Checking...", font=self.font, fill=(0, 255, 0))
        self.lcd.LCD_ShowImage(img)

        ok, output = self.tcp_connect_check(gateway, port)

        lines = [f"Host: {gateway}", f"Port: {port}", "OPEN" if ok else "CLOSED"]
        extra = [line.strip() for line in output.splitlines() if line.strip()]
        lines.extend(extra[:4])

        try:
            with open(self.netcat_output_file, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
        except Exception:
            pass

        self.show_message("Netcat", lines)

    def show_last_netcat_result(self):
        if not os.path.exists(self.netcat_output_file):
            self.show_message("Netcat", ["No saved result"])
            return

        try:
            with open(self.netcat_output_file, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            if not lines:
                lines = ["No output"]
            self.show_message("Netcat Last", lines[:8])
        except Exception as e:
            self.show_message("Read Error", [str(e)])

    # ------------------------------------------------------------------
    # Speedtest actions
    # ------------------------------------------------------------------
    def run_speedtest(self):
        try:
            import speedtest  # noqa: F401
        except Exception:
            self.show_message("Speedtest", ["Install first:", "pip install", "speedtest-cli"])
            return

        cmd = [sys.executable, "-m", "speedtest", "--simple"]
        if self.speedtest_secure:
            cmd.append("--secure")

        try:
            with open(self.speedtest_output_file, "w") as out:
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Speedtest", font=self.font, fill=(0, 255, 255))
                    draw.text((2, 24), "Running...", font=self.font, fill=(255, 255, 255))
                    draw.text((2, 40), f"Secure: {self.get_speedtest_secure_label()}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 56), f"Test {spinner[i % len(spinner)]}", font=self.font, fill=(0, 255, 0))
                    draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
                    draw.text((2, self.lcd.height - 12), "K1=Cancel K3=Home", font=self.font, fill=(128, 128, 128))
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
                        self.show_message("Speedtest", ["Test cancelled"])
                        return

                    time.sleep(0.2)

            self.show_last_speedtest_result(title="Speedtest Done")

        except Exception as e:
            self.show_message("Speedtest Err", [str(e)])

    def show_last_speedtest_result(self, title: str = "Last Result"):
        if not os.path.exists(self.speedtest_output_file):
            self.show_message("Speedtest", ["No saved result"])
            return

        try:
            with open(self.speedtest_output_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                lines = ["No output"]
            self.show_message(title, lines[:8])
        except Exception as e:
            self.show_message("Read Error", [str(e)])

    # ------------------------------------------------------------------
    # Ping actions
    # ------------------------------------------------------------------
    def run_ping(self):
        target, label = self.resolve_target(self.ping_target)
        if not target:
            self.show_message("Ping", ["Target not ready"])
            return

        ping_path = shutil.which("ping")
        if ping_path is None:
            self.show_message("Ping", ["ping not found"])
            return

        cmd = [ping_path, "-c", str(self.ping_count), target]

        try:
            with open(self.ping_output_file, "w") as out:
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Ping", font=self.font, fill=(0, 255, 255))
                    draw.text((2, 22), self.fit_text(f"Tgt: {label}", 20), font=self.font, fill=(255, 255, 255))
                    draw.text((2, 34), self.fit_text(f"IP : {target}", 20), font=self.font, fill=(255, 255, 0))
                    draw.text((2, 46), f"Cnt: {self.ping_count}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 62), f"Run {spinner[i % len(spinner)]}", font=self.font, fill=(0, 255, 0))
                    draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
                    draw.text((2, self.lcd.height - 12), "K1=Cancel K3=Home", font=self.font, fill=(128, 128, 128))
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
                        self.show_message("Ping", ["Run cancelled"])
                        return

                    time.sleep(0.2)

            self.show_last_ping_result(title="Ping Done")

        except Exception as e:
            self.show_message("Ping Error", [str(e)])

    def show_last_ping_result(self, title: str = "Ping Result"):
        if not os.path.exists(self.ping_output_file):
            self.show_message("Ping", ["No saved result"])
            return

        try:
            with open(self.ping_output_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            raw_lines = [line.rstrip() for line in text.splitlines()]
            if not raw_lines:
                raw_lines = ["No output"]
            self.show_scrollable_lines(title, raw_lines)
        except Exception as e:
            self.show_message("Read Error", [str(e)])

    # ------------------------------------------------------------------
    # Traceroute actions
    # ------------------------------------------------------------------
    def run_traceroute(self):
        traceroute_path = shutil.which("traceroute")
        if traceroute_path is None:
            self.show_message("Traceroute", ["Install:", "sudo apt install", "traceroute"])
            return

        target, label = self.resolve_target(self.traceroute_target)
        if not target:
            self.show_message("Traceroute", ["Target not ready"])
            return

        cmd = [traceroute_path, "-n", "-m", str(self.traceroute_max_hops), target]

        try:
            with open(self.traceroute_output_file, "w") as out:
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Traceroute", font=self.font, fill=(0, 255, 255))
                    draw.text((2, 22), self.fit_text(f"Tgt: {label}", 20), font=self.font, fill=(255, 255, 255))
                    draw.text((2, 34), self.fit_text(f"IP : {target}", 20), font=self.font, fill=(255, 255, 0))
                    draw.text((2, 46), f"Hop: {self.traceroute_max_hops}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 62), f"Run {spinner[i % len(spinner)]}", font=self.font, fill=(0, 255, 0))
                    draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
                    draw.text((2, self.lcd.height - 12), "K1=Cancel K3=Home", font=self.font, fill=(128, 128, 128))
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
                        self.show_message("Traceroute", ["Run cancelled"])
                        return

                    time.sleep(0.2)

            self.show_last_traceroute_result(title="Trace Done")

        except Exception as e:
            self.show_message("Trace Error", [str(e)])

    def show_last_traceroute_result(self, title: str = "Trace Result"):
        if not os.path.exists(self.traceroute_output_file):
            self.show_message("Traceroute", ["No saved result"])
            return

        try:
            with open(self.traceroute_output_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            raw_lines = [line.rstrip() for line in text.splitlines()]
            if not raw_lines:
                raw_lines = ["No output"]
            self.show_scrollable_lines(title, raw_lines)
        except Exception as e:
            self.show_message("Read Error", [str(e)])

    # ------------------------------------------------------------------
    # Iperf actions
    # ------------------------------------------------------------------
    def run_iperf(self):
        iperf_path = shutil.which("iperf")
        if iperf_path is None:
            self.show_message("Iperf", ["Install:", "sudo apt install", "iperf"])
            return

        server, label = self.resolve_target(self.iperf_server)
        if not server:
            self.show_message("Iperf", ["Server not ready"])
            return

        cmd = [
            iperf_path,
            "-c", server,
            "-p", str(self.iperf_port),
            "-t", str(self.iperf_duration),
        ]
        if self.iperf_tradeoff:
            cmd.append("-r")

        try:
            with open(self.iperf_output_file, "w") as out:
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Iperf", font=self.font, fill=(0, 255, 255))
                    draw.text((2, 20), self.fit_text(f"Srv: {label}", 20), font=self.font, fill=(255, 255, 255))
                    draw.text((2, 32), f"Prt: {self.iperf_port}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 44), self.fit_text(f"Dir: {self.get_iperf_direction_label()}", 20), font=self.font, fill=(255, 255, 0))
                    draw.text((2, 56), f"Sec: {self.iperf_duration}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 70), f"Run {spinner[i % len(spinner)]}", font=self.font, fill=(0, 255, 0))
                    draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
                    draw.text((2, self.lcd.height - 12), "K1=Cancel K3=Home", font=self.font, fill=(128, 128, 128))
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
                        self.show_message("Iperf", ["Run cancelled"])
                        return

                    time.sleep(0.2)

            self.show_last_iperf_result(title="Iperf Done")

        except Exception as e:
            self.show_message("Iperf Err", [str(e)])

    def show_last_iperf_result(self, title: str = "Iperf Result"):
        if not os.path.exists(self.iperf_output_file):
            self.show_message("Iperf", ["No saved result"])
            return

        try:
            with open(self.iperf_output_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            raw_lines = [line.rstrip() for line in text.splitlines()]
            if not raw_lines:
                raw_lines = ["No output"]
            self.show_scrollable_lines(title, raw_lines)
        except Exception as e:
            self.show_message("Read Error", [str(e)])

    # ------------------------------------------------------------------
    # Iperf3 actions
    # ------------------------------------------------------------------
    def run_iperf3(self):
        iperf_path = shutil.which("iperf3")
        if iperf_path is None:
            self.show_message("Iperf3", ["Install:", "sudo apt install", "iperf3"])
            return

        server, label = self.resolve_target(self.iperf3_server)
        if not server:
            self.show_message("Iperf3", ["Server not ready"])
            return

        cmd = [
            iperf_path,
            "-c", server,
            "-p", str(self.iperf3_port),
            "-t", str(self.iperf3_duration),
        ]
        if self.iperf3_reverse:
            cmd.append("-R")

        try:
            with open(self.iperf3_output_file, "w") as out:
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                spinner = ["|", "/", "-", "\\"]
                i = 0

                while proc.poll() is None:
                    img = Image.new("RGB", (self.lcd.width, self.lcd.height), self.bg_color)
                    draw = ImageDraw.Draw(img)

                    draw.text((2, 2), "Iperf3", font=self.font, fill=(0, 255, 255))
                    draw.text((2, 20), self.fit_text(f"Srv: {label}", 20), font=self.font, fill=(255, 255, 255))
                    draw.text((2, 32), f"Prt: {self.iperf3_port}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 44), self.fit_text(f"Dir: {self.get_iperf3_direction_label()}", 20), font=self.font, fill=(255, 255, 0))
                    draw.text((2, 56), f"Sec: {self.iperf3_duration}", font=self.font, fill=(255, 255, 0))
                    draw.text((2, 70), f"Run {spinner[i % len(spinner)]}", font=self.font, fill=(0, 255, 0))
                    draw.rectangle((0, self.lcd.height - 14, self.lcd.width, self.lcd.height), fill=(16, 16, 16))
                    draw.text((2, self.lcd.height - 12), "K1=Cancel K3=Home", font=self.font, fill=(128, 128, 128))
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
                        self.show_message("Iperf3", ["Run cancelled"])
                        return

                    time.sleep(0.2)

            self.show_last_iperf3_result(title="Iperf3 Done")

        except Exception as e:
            self.show_message("Iperf3 Err", [str(e)])

    def show_last_iperf3_result(self, title: str = "Iperf3 Result"):
        if not os.path.exists(self.iperf3_output_file):
            self.show_message("Iperf3", ["No saved result"])
            return

        try:
            with open(self.iperf3_output_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            raw_lines = [line.rstrip() for line in text.splitlines()]
            if not raw_lines:
                raw_lines = ["No output"]
            self.show_scrollable_lines(title, raw_lines)
        except Exception as e:
            self.show_message("Read Error", [str(e)])


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