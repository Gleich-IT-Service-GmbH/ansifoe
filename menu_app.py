#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import html
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

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
        # Load choice lists from JSON
        # --------------------------------------------------------------
        self.load_choice_config()

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
    # Choice config / menu building helpers
    # ------------------------------------------------------------------
    def load_choice_config(self):
        defaults = {
            "target_choices": [
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
            ],
            "nmap_profile_choices": [
                ("Ping Sweep", "ping"),
                ("Basic Service", "basic"),
                ("Vuln Scripts", "vuln"),
            ],
            "netcat_port_choices": [22, 53, 80, 443],
            "speedtest_secure_choices": [
                ("On", True),
                ("Off", False),
            ],
            "ping_count_choices": [4, 10],
            "traceroute_hop_choices": [10, 20, 30],
            "duration_choices": [5, 10, 30],
            "iperf_port_choices": [5001, 5201],
            "iperf3_port_choices": [5201, 5202],
            "iperf_direction_choices": [
                ("Normal", False),
                ("Tradeoff", True),
            ],
            "iperf3_direction_choices": [
                ("Normal", False),
                ("Reverse", True),
            ],
        }

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu_choices.json")
        data = {}

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        self.target_choices = self.normalize_choice_pairs(
            data.get("target_choices", defaults["target_choices"]),
            defaults["target_choices"],
        )
        self.nmap_profile_choices = self.normalize_choice_pairs(
            data.get("nmap_profile_choices", defaults["nmap_profile_choices"]),
            defaults["nmap_profile_choices"],
        )
        self.netcat_port_choices = self.normalize_simple_list(
            data.get("netcat_port_choices", defaults["netcat_port_choices"]),
            defaults["netcat_port_choices"],
            int,
        )
        self.speedtest_secure_choices = self.normalize_choice_pairs(
            data.get("speedtest_secure_choices", defaults["speedtest_secure_choices"]),
            defaults["speedtest_secure_choices"],
        )
        self.ping_count_choices = self.normalize_simple_list(
            data.get("ping_count_choices", defaults["ping_count_choices"]),
            defaults["ping_count_choices"],
            int,
        )
        self.traceroute_hop_choices = self.normalize_simple_list(
            data.get("traceroute_hop_choices", defaults["traceroute_hop_choices"]),
            defaults["traceroute_hop_choices"],
            int,
        )
        self.duration_choices = self.normalize_simple_list(
            data.get("duration_choices", defaults["duration_choices"]),
            defaults["duration_choices"],
            int,
        )
        self.iperf_port_choices = self.normalize_simple_list(
            data.get("iperf_port_choices", defaults["iperf_port_choices"]),
            defaults["iperf_port_choices"],
            int,
        )
        self.iperf3_port_choices = self.normalize_simple_list(
            data.get("iperf3_port_choices", defaults["iperf3_port_choices"]),
            defaults["iperf3_port_choices"],
            int,
        )
        self.iperf_direction_choices = self.normalize_choice_pairs(
            data.get("iperf_direction_choices", defaults["iperf_direction_choices"]),
            defaults["iperf_direction_choices"],
        )
        self.iperf3_direction_choices = self.normalize_choice_pairs(
            data.get("iperf3_direction_choices", defaults["iperf3_direction_choices"]),
            defaults["iperf3_direction_choices"],
        )

    def normalize_choice_pairs(self, value, fallback):
        try:
            result = []
            for item in value:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    result.append((item[0], item[1]))
            if result:
                return result
        except Exception:
            pass
        return fallback

    def normalize_simple_list(self, value, fallback, cast_type=int):
        try:
            result = [cast_type(v) for v in value]
            if result:
                return result
        except Exception:
            pass
        return fallback

    def build_choice_menu(self, choices: List[Tuple[str, Any]], setter: Callable[[Any], None]) -> List[MenuItem]:
        return [MenuItem(label, action=lambda value=value: setter(value)) for label, value in choices]

    def build_value_menu(self, values: List[Any], setter: Callable[[Any], None]) -> List[MenuItem]:
        return [MenuItem(str(value), action=lambda value=value: setter(value)) for value in values]

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
    # Main loop / navigation
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
            self.menu_stack.append((self.current_menu, self.current_index, self.current_top, self.current_title))
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

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def check_home_button(self) -> bool:
        if self.lcd.get_key_state("key3"):
            time.sleep(0.08)
            if self.lcd.get_key_state("key3"):
                self.go_home()
                self.wait_for_key_release("key3")
                return True
        return False

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
            wrapped.extend(chunks if chunks else [""])
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

    # ------------------------------------------------------------------
    # Confirm / message dialogs
    # ------------------------------------------------------------------
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
            if self.lcd.get_key_state("right") or self.lcd.get_key_state("press") or self.lcd.get_key_state("key2"):
                time.sleep(0.08)
                return True
            if self.lcd.get_key_state("left") or self.lcd.get_key_state("key1"):
                time.sleep(0.08)
                return False
            time.sleep(0.05)


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