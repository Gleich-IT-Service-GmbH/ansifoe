# ansifoe
a raspberry pi with a display to run basic scripts to scan a network

A small network toolkit for **Raspberry Pi 4** with a **1.44" ST7735 SPI LCD** and onboard **joystick + buttons**.

This project provides a menu-driven interface on the LCD for:

- system stats
- Nmap scans
- Netcat checks
- Speedtest
- Ping
- Traceroute
- reboot / shutdown actions

The interface is designed to be navigated entirely with the joystick and buttons on the LCD board.

---

## Features

- LCD menu interface on a **128x128 SPI display**
- Navigation with:
  - joystick up/down/left/right
  - joystick press
  - 3 hardware buttons
- Startup splash screen via `splash.png`
- System stats:
  - CPU usage
  - CPU temperature
  - disk usage
  - `eth0` IP
  - external IP
- Network tools:
  - **Nmap**
  - **Netcat**
  - **Speedtest**
  - **Ping**
  - **Traceroute**
- Persistent “last result” screens for tools
- Settings-driven configuration for each tool
- Optional systemd autostart on boot

---

## Hardware

This project was built and tested with the following hardware:

- **Raspberry Pi 4**
- **1.44" SPI LCD display module / HAT**
  - Resolution: **128 × 128**
  - Controller: **ST7735 / ST7735S**
  - Includes:
    - **5-way joystick**
      - Up
      - Down
      - Left
      - Right
      - Press
    - **3 additional push buttons**
- **microSD card** with Raspberry Pi OS
- **5V power supply** for the Raspberry Pi 4
- **Ethernet connection** on `eth0`

---

## Software Requirements

- **Raspberry Pi OS**
- **Python 3**
- **SPI enabled**
- Python packages:
  - `numpy`
  - `pillow`
  - `psutil`
  - `speedtest-cli`

System packages:

- `python3-rpi.gpio`
- `python3-spidev`
- `nmap`
- `netcat-openbsd`
- `traceroute`

Optional:

- `xsltproc` for better Nmap HTML export

---

## Project Structure

```text
.
├── config.py
├── LCD_1in44.py
├── menu_app.py
├── splash.png
├── requirements.txt
└── venv/
```

## Installation

---

### 1. Enable SPI

```bash
sudo raspi-config
```
Then go to:

Interface Options &rarr; SPI &rarr; Enable
Reboot if needed.

### 2. Install system packages

```bash
sudo apt update
sudo apt install python3-rpi.gpio python3-spidev nmap netcat-openbsd traceroute xsltproc
```
### 3. Clone this repository

```bash
git clone git@github.com:Gleich-IT-Service-GmbH/ansifoe.git
cd ansifoe
```

### 4. Create a Python virtual environment
```bash
python3 -m venv venv
```
```bash
source venv/bin/activate
```
### 5. Install Python dependencies
```bash
pip3 install -r requirements.txt
```

## 7. Run the application
```bash
source venv/bin/activate
python menu_app.py
```

## Optional: Autostart on boot with systemd

Create the service file:

```bash
sudo nano /etc/systemd/system/lcd-menu.service
```
Example content:

```ini
[Unit]
Description=ANSIFOE
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/your_project
ExecStart=/home/pi/your_project/venv/bin/python /home/pi/your_project/menu_app.py
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
Replace:

/home/pi/your_project with your actual project path
Then enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lcd-menu.service
sudo systemctl start lcd-menu.service
```
Check status:

```bash
sudo systemctl status lcd-menu.service
```
View logs:

```bash
journalctl -u lcd-menu.service -f
```

# Menu Structure

## Navigation Notes

- **Joystick Up / Down**: move selection
- **Joystick Right**: enter submenu / run action
- **Joystick Left**: go back one level
- **Joystick Press**: enter / confirm
- **Key1**: back
- **Key2**: OK / run / confirm
- **Key3**: jump directly to the **Main Menu**

## Scrolling

- Long menus automatically **scroll** when the selected item moves out of view
- Long tool outputs use a **scrollable text viewer**
  - **Up / Down**: scroll text
  - **Left / Key1**: back
  - **Key3**: home

---

# Main Menu

- System Stats
- Tools
- Settings

---

# System Stats

- Live Stats

---

# Tools

- Nmap
- Netcat
- Speedtest
- Ping
- Traceroute
- Iperf
- Iperf3

---

# Tools → Nmap

- Run Scan
- Last Result
- Convert to HTML

---

# Tools → Netcat

- Run Check
- Last Result

---

# Tools → Speedtest

- Run Test
- Last Result

---

# Tools → Ping

- Run
- Last Result

---

# Tools → Traceroute

- Run
- Last Result

---

# Tools → Iperf

- Run
- Last Result

---

# Tools → Iperf3

- Run
- Last Result

---

# Settings

- Nmap
- Netcat
- Speedtest
- Ping
- Traceroute
- Iperf
- Iperf3
- Power

---

# Settings → Nmap

- Scan Type

## Settings → Nmap → Scan Type

- Ping Sweep
- Basic Service
- Vuln Scripts

---

# Settings → Netcat

- Port

## Settings → Netcat → Port

- 22
- 53
- 80
- 443

---

# Settings → Speedtest

- Secure

## Settings → Speedtest → Secure

- On
- Off

---

# Settings → Ping

- Ping Target
- Ping Count

## Settings → Ping → Ping Target

- Gateway
- 1.1.1.1
- 8.8.8.8

## Settings → Ping → Ping Count

- 4
- 10

---

# Settings → Traceroute

- Trace Target
- Max Hops

## Settings → Traceroute → Trace Target

- Gateway
- 1.1.1.1
- 8.8.8.8

## Settings → Traceroute → Max Hops

- 10
- 20
- 30

---

# Settings → Iperf

- Server
- Port
- Direction
- Duration

## Settings → Iperf → Server

- Gateway
- 192.168.1.1
- 192.168.1.10

## Settings → Iperf → Port

- 5001
- 5201

## Settings → Iperf → Direction

- Normal
- Tradeoff

## Settings → Iperf → Duration

- 5
- 10
- 30

---

# Settings → Iperf3

- Server
- Port
- Direction
- Duration

## Settings → Iperf3 → Server

- Gateway
- 192.168.1.1
- 192.168.1.10

## Settings → Iperf3 → Port

- 5201
- 5202

## Settings → Iperf3 → Direction

- Normal
- Reverse

## Settings → Iperf3 → Duration

- 5
- 10
- 30

---

# Settings → Power

- Reboot
- Shutdown

## Disclaimer
Use the included network tools only on systems and networks you own or are authorized to test.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Third-Party Code

Parts of the LCD driver are based on vendor-provided ST7735 / Waveshare-style Python code.
Original copyright and permission notices are retained where applicable.



