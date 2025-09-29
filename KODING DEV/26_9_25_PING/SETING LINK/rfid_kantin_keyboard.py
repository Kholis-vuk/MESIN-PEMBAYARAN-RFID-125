#!/usr/bin/env python3
import sys, time, threading, subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGridLayout, QMenu
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QObject, Slot, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QPainter, QColor, QAction
import serial, pyautogui

PORT = "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_94:A9:90:98:0B:78-if00"
BAUD = 115200

import socket

class DataSender(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ip = "103.108.131.236"
        self.port = 26692

        # buat timer 10 menit (600000 ms)
        self.timer = QTimer()
        self.timer.timeout.connect(self.send_data)
        self.timer.start(60000)  # 10 menit

    def get_cpu_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read().strip()) // 1000  # hasil integer
            return str(temp)
        except:
            return "0"

    def send_data(self):
        try:
            # Data dasar
            SCR = "QW30"
            CPNY = "4000100"
            SN = "000001"

            # Tambah suhu CPU (integer)
            cpu_temp = self.get_cpu_temp()

            # Gabungkan semua data
            data = SCR + CPNY + SN  + cpu_temp  # contoh: QW304000100000001|42

            # Kirim ke server pakai TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.ip, self.port))
                s.sendall(data.encode())
                # Tunggu respon dari server
                try:
                    response = s.recv(1024).decode().strip()
                except socket.timeout:
                    response = "⚠️ Tidak ada respon dari server"

            print(f"✅ Data terkirim: {data}")
            print(f"📩 Respon server: {response}")

        except Exception as e:
            print("❌ Gagal kirim data:", e)


# ===== WiFi Monitor =====
class WiFiMonitor(QThread):
    wifi_status_changed = Signal(str, bool)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.current_ssid = ""
        self.current_quality = 0

    def get_wifi_info(self):
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'], 
                                  capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                if line.startswith('yes:'): 
                    return line.split(':')[1], True
            return "Not Connected", False
        except:
            return "Error", False

    def get_wifi_quality(self):
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SIGNAL', 'dev', 'wifi'], 
                                  capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                if line.startswith('yes:'): 
                    return int(line.split(':')[1])
            return 0
        except:
            return 0

    def run(self):
        while self.running:
            ssid, connected = self.get_wifi_info()
            quality = self.get_wifi_quality() if connected else 0
            if ssid != self.current_ssid or connected != (self.current_quality > 0):
                self.wifi_status_changed.emit(ssid, connected)
                self.current_ssid = ssid
                self.current_quality = quality if connected else 0
            time.sleep(5)

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

# ===== WiFi Indicator =====
class WiFiIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.connected = False
        self.quality = 0
        self.ssid = "Not Connected"
        self.setToolTip("Not Connected")

    def update_status(self, ssid, connected, quality=0):
        self.connected = connected
        self.quality = quality
        self.ssid = ssid
        self.setToolTip(f"{ssid}\nQuality: {quality}%" if connected else "Not Connected")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(240, 240, 240, 200))
        
        if self.connected:
            if self.quality > 75: 
                color = QColor(0, 200, 0)
            elif self.quality > 50: 
                color = QColor(255, 165, 0)
            elif self.quality > 25: 
                color = QColor(255, 69, 0)
            else: 
                color = QColor(255, 0, 0)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            cx = self.width() // 2
            cy = self.height() // 2
            
            painter.drawRect(cx-8, cy+8, 4, 4)
            if self.quality > 25: 
                painter.drawRect(cx-12, cy+4, 4, 8)
                painter.drawRect(cx+8, cy+4, 4, 8)
            if self.quality > 50: 
                painter.drawRect(cx-16, cy, 4, 12)
                painter.drawRect(cx+12, cy, 4, 12)
            if self.quality > 75: 
                painter.drawRect(cx-20, cy-4, 4, 16)
                painter.drawRect(cx+16, cy-4, 4, 16)
        else:
            painter.setPen(QColor(255, 0, 0))
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(10, 10, 30, 30)
            painter.drawLine(30, 10, 10, 30)

# ===== Serial Thread =====
class SerialThread(QThread):
    data_received = Signal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        self.ser = None
        self.running = True

    def connect_serial(self):
        """Coba konek ke port serial sampai berhasil."""
        while self.running:
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=1)
                print("✅ Terkoneksi ke", self.port)
                return
            except Exception as e:
                print("⚠️ Gagal buka port, retry 2 detik...", e)
                time.sleep(2)

    def run(self):
        self.connect_serial()
        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    rfid_data = self.ser.readline().decode(errors="ignore").strip()
                    if rfid_data:
                        self.data_received.emit(rfid_data)
            except Exception as e:
                print("⚠️ Serial error, reconnect:", e)
                try:
                    self.ser.close()
                except:
                    pass
                time.sleep(2)
                self.connect_serial()

    def stop(self):
        self.running = False
        if self.ser:
            self.ser.close()
        self.quit()
        self.wait()

# ===== Bridge for WebChannel =====
class Bridge(QObject):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

    @Slot(str)
    def sendWifiPassword(self, pwd):
        print("Password diterima:", pwd)
        threading.Thread(target=self.parent.run_nmcli_connect,
                         args=(self.parent.current_ssid, pwd),
                         daemon=True).start()

  #  @Slot()
  #  def goHome(self):
  #     self.parent.keyboard_widget.setVisible(False)
  #     self.parent.browser.setUrl(QUrl("https://pesatkantin.com/order-self"))
        
    @Slot()
    def goHome(self):
        self.parent.keyboard_widget.setVisible(False)

        try:
            # baca URL dari file txt
            with open("urlx.txt", "r") as f:
                url = f.read().strip()   # hapus spasi/enter
        except Exception as e:
            print("❌ Gagal baca file URL:", e)
            # fallback ke default
            url = "https://pesatkantin.com/order-self"

        # set URL ke browser
        self.parent.browser.setUrl(QUrl(url))
        
    @Slot(str)
    def saveUrl(self, url):
        try:
            with open("urlx.txt", "w") as f:
                f.write(url.strip())
            print(f"✅ URL tersimpan: {url}")
            self.parent.browser.setUrl(QUrl(url.strip()))
        except Exception as e:
            print("❌ Gagal simpan URL:", e)


# ===== Main App =====
class WebApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_ssid = ""
        self.caps_lock = False
        
        self.data_sender = DataSender(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 5, 10, 5)

        title = QLabel("Kantin Pesat")
        title.setStyleSheet("font-size:16px;font-weight:bold;")
        hl.addWidget(title)
        hl.addStretch()

        # 📶 WiFi Indicator
        self.wifi_indicator = WiFiIndicator()
        self.wifi_indicator.setCursor(Qt.PointingHandCursor)
        self.wifi_indicator.mousePressEvent = self.show_wifi_menu
        hl.addWidget(self.wifi_indicator)

        # 🔄 Tombol Refresh Halaman
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedSize(35, 35)
        self.refresh_btn.setToolTip("Refresh halaman")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_page)
        hl.addWidget(self.refresh_btn)

        layout.addWidget(header)

        # Browser
   #     self.browser = QWebEngineView()
    #    layout.addWidget(self.browser, stretch=7)
    #    self.browser.setUrl(QUrl("https://pesatkantin.com/order-self"))
        
        self.browser = QWebEngineView()
        layout.addWidget(self.browser, stretch=7)

        try:
            with open("urlx.txt", "r") as f:
                start_url = f.read().strip()
        except:
            start_url = "https://pesatkantin.com/order-self"

        self.browser.setUrl(QUrl(start_url))


        # Keyboard
        self.keyboard_widget = QWidget()
        self.keyboard_widget.setVisible(False)
        layout.addWidget(self.keyboard_widget)
        
        # Buat layout untuk keyboard dengan styling
        keyboard_layout = QVBoxLayout(self.keyboard_widget)
        keyboard_layout.setContentsMargins(10, 10, 10, 10)
        keyboard_layout.setSpacing(5)
        
        # Container untuk keyboard
        keyboard_container = QWidget()
        keyboard_container.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-radius: 10px;
                padding: 5px;
            }
        """)
        keyboard_layout.addWidget(keyboard_container)
        
        grid = QGridLayout(keyboard_container)
        grid.setSpacing(5)
        
        # Baris keyboard - huruf kecil sebagai default
        rows = [
            list("qwertyuio"),
            list("asdfghjkl"),
            list("zxcvbnmp0"),
            list("123456789"),
            ["@", "#", "%", "&", "*", "(", ")", "-", "_"],
            ["=", ".", ",", "?", "/", "+", ":"]
        ]
        
        # Buat tombol keyboard
        r = 0
        for row in rows:
            c = 0
            for k in row:
                btn = self.make_button(k)
                if r == 4:  # Baris karakter khusus
                    grid.addWidget(btn, r, c, 1, 1)
                else:
                    grid.addWidget(btn, r, c)
                c += 1
            r += 1
        
        # Baris tombol fungsional
        caps_btn = self.make_button("Caps")
        space_btn = self.make_button("Space")
        backspace_btn = self.make_button("⌫")
        enter_btn = self.make_button("Enter")
        close_btn = self.make_button("Close")
        
        # Mengatur tata letak tombol fungsional
        grid.addWidget(caps_btn, r, 0, 1, 2)
        grid.addWidget(space_btn, r, 2, 1, 3)
        grid.addWidget(backspace_btn, r, 5, 1, 2)
        grid.addWidget(close_btn, r, 7, 1, 2)
        grid.addWidget(enter_btn, r-1, 7, 1, 2)

        self.showFullScreen()

        # Focus timer
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.check_focused_element)
        self.focus_timer.start(500)

        # Serial + WiFi Monitor
        self.serial_thread = SerialThread(PORT, BAUD)
        self.serial_thread.data_received.connect(self.handle_rfid)
        self.serial_thread.start()
        
        self.wifi_monitor = WiFiMonitor()
        self.wifi_monitor.wifi_status_changed.connect(self.update_wifi_status)
        self.wifi_monitor.start()

        # WebChannel
        self.channel = QWebChannel()
        self.bridge = Bridge(self)
        self.channel.registerObject("pywebchannel", self.bridge)
        self.browser.page().setWebChannel(self.channel)
        
        # === Footer dengan tombol Setting & Shutdown ===
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(10, 5, 10, 5)
        fl.addStretch()

        # 🔧 Tombol Setting
        setting_btn = QPushButton("⚙️")
        setting_btn.setFixedSize(60, 50)
        setting_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #5bc0de;
                color: white;
                border: 2px solid #46b8da;
                border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #31b0d5;
            }
        """)
        setting_btn.clicked.connect(self.open_setting_html)
        fl.addWidget(setting_btn)

        # ⏻ Tombol Shutdown
        shutdown_btn = QPushButton("⏻")
        shutdown_btn.setFixedSize(60, 50)
        shutdown_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #d9534f;
                color: white;
                border: 2px solid #c9302c;
                border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #c9302c;
            }
        """)
        shutdown_btn.clicked.connect(self.shutdown_system)
        fl.addWidget(shutdown_btn)

        layout.addWidget(footer)

        self.showFullScreen()
     
    
    def shutdown_system(self):
        """Matikan sistem dengan aman."""
        try:
            subprocess.run(["systemctl", "poweroff"], check=False)
        except Exception as e:
            print("❌ Gagal shutdown:", e)
            
    def refresh_page(self):
        self.browser.reload()
    
    # ===== Keyboard =====
    def make_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(50)
        
        # Styling tombol berdasarkan jenisnya
        if text == "Caps":
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    font-weight: bold;
                    background-color: #d0d0d0;
                    border: 2px solid #b0b0b0;
                    border-radius: 5px;
                }
                QPushButton:pressed {
                    background-color: #a0a0a0;
                }
            """)
        elif text in ["Space", "Enter", "Close"]:
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    font-weight: bold;
                    background-color: #4a86e8;
                    color: white;
                    border: 2px solid #3a76d8;
                    border-radius: 5px;
                }
                QPushButton:pressed {
                    background-color: #3a76d8;
                }
            """)
        elif text == "⌫":
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 20px;
                    font-weight: bold;
                    background-color: #ff6b6b;
                    color: white;
                    border: 2px solid #e55b5b;
                    border-radius: 5px;
                }
                QPushButton:pressed {
                    background-color: #e55b5b;
                }
            """)
        else:
            if text in ["@", "#", "%", "&", "*", "(", ")", "-", "_", "+", "=", "<", ">", "?", "/"]:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 14px;
                        background-color: white;
                        border: 2px solid #d0d0d0;
                        border-radius: 5px;
                    }
                    QPushButton:pressed {
                        background-color: #e0e0e0;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        background-color: white;
                        border: 2px solid #d0d0d0;
                        border-radius: 5px;
                    }
                    QPushButton:pressed {
                        background-color: #e0e0e0;
                    }
                """)
        
        def on_click():
            if text == "Caps":
                self.caps_lock = not self.caps_lock
                # Update tampilan tombol Caps Lock
                btn.setStyleSheet(f"""
                    QPushButton {{
                        font-size: 16px;
                        font-weight: bold;
                        background-color: {'#ADD8E6' if self.caps_lock else '#d0d0d0'};
                        border: 2px solid #b0b0b0;
                        border-radius: 5px;
                    }}
                    QPushButton:pressed {{
                        background-color: #a0a0a0;
                    }}
                """)
                self.update_keyboard_keys()
            else:
                self.send_key(text)
        
        btn.clicked.connect(on_click)
        return btn

    def update_keyboard_keys(self):
        for btn in self.keyboard_widget.findChildren(QPushButton):
            text = btn.text()
            if len(text) == 1 and text.isalpha():
                btn.setText(text.upper() if self.caps_lock else text.lower())

    def check_focused_element(self):
        js = "var f=document.activeElement;if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){'input';}else{'none';}"
        self.browser.page().runJavaScript(js, self.handle_focus_check)

    def handle_focus_check(self, res): 
        self.keyboard_widget.setVisible(res == 'input')

    def send_key(self, key):
        if key == "Close":
            self.keyboard_widget.setVisible(False)
            self.browser.page().runJavaScript(
                "var f=document.activeElement;if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){f.blur();}"
            )
            return
        
        # Mapping untuk tombol khusus
        key_mapping = {
            "⌫": "Backspace",
            "Caps": "CapsLock",
            "Space": " ",
            "Enter": "Enter"
        }
        
        # Gunakan mapping jika ada, else gunakan key asli
        actual_key = key_mapping.get(key, key)
        
        if actual_key == "Enter":
            js = "var f=document.activeElement;if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){var d=new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true});var u=new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true});f.dispatchEvent(d);f.dispatchEvent(u);}"
        elif actual_key == "Backspace":
            js = "var f=document.activeElement;if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){f.value=f.value.slice(0,-1);f.dispatchEvent(new Event('input',{bubbles:true}));var u=new KeyboardEvent('keyup',{key:'Backspace',code:'Backspace',keyCode:8,which:8,bubbles:true});f.dispatchEvent(u);}"
        elif actual_key == " ":
            js = "var f=document.activeElement;if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){f.value+=' ';f.dispatchEvent(new Event('input',{bubbles:true}));}"
        else:
            if actual_key.isalpha():
                char = actual_key.upper() if self.caps_lock else actual_key.lower()
            else:
                char = actual_key

            js = f"""
            var f=document.activeElement;
            if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){{
                f.value+='{char}';
                f.dispatchEvent(new Event('input',{{bubbles:true}}));
                var d = new KeyboardEvent('keydown',{{key:'{char}',code:'{char}',keyCode:{ord(char)},which:{ord(char)},bubbles:true}});
                var u = new KeyboardEvent('keyup',{{key:'{char}',code:'{char}',keyCode:{ord(char)},which:{ord(char)},bubbles:true}});
                f.dispatchEvent(d); f.dispatchEvent(u);
            }}
            """
        self.browser.page().runJavaScript(js)
        
    def open_setting_html(self):
        self.keyboard_widget.setVisible(True)

        # Baca URL lama jika ada
        try:
            with open("urlx.txt", "r") as f:
                current_url = f.read().strip()
        except:
            current_url = "https://pesatkantin.com/order-self"

        html = f"""
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Setting URL</title>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                body {{
                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    padding: 40px 20px;
                    font-family: Arial, sans-serif;
                }}
                .container {{
                    background-color: rgba(255, 255, 255, 0.95);
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                    width: 100%;
                    max-width: 450px;
                    padding: 30px;
                    text-align: center;
                    margin-top: 30px;
                }}
                h1 {{
                    margin-bottom: 20px;
                    color: #333;
                }}
                input[type="text"] {{
                    width: 90%;
                    padding: 15px;
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    font-size: 16px;
                }}
                .button-group {{
                    margin-top: 20px;
                    display: flex;
                    gap: 15px;
                }}
                button {{
                    flex: 1;
                    padding: 15px;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                }}
                .save-btn {{
                    background: #38ef7d;
                    color: white;
                }}
                .home-btn {{
                    background: #eee;
                }}
            </style>
        </head>
        <body onload="setupChannel()">
            <div class="container">
                <h1>Setting URL</h1>
                <input type="text" id="urlInput" value="{current_url}">
                <div class="button-group">
                    <button class="save-btn" onclick="saveUrl()">Simpan</button>
                    <button class="home-btn" onclick="goHome()">Batal</button>
                </div>
            </div>
            <script>
                function setupChannel() {{
                    new QWebChannel(qt.webChannelTransport, function(channel) {{
                        window.pywebchannel = channel.objects.pywebchannel;
                    }});
                }}
                function saveUrl() {{
                    var url = document.getElementById('urlInput').value;
                    if(window.pywebchannel) {{
                        window.pywebchannel.saveUrl(url);
                    }}
                }}
                function goHome() {{
                    if(window.pywebchannel) {{
                        window.pywebchannel.goHome();
                    }}
                }}
            </script>
        </body>
        </html>
        """
        self.browser.setHtml(html)
        self.browser.page().runJavaScript("""
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pywebchannel = channel.objects.pywebchannel;
            });
        """)


    # ===== WiFi Menu =====
    def show_wifi_menu(self, event):
        menu = QMenu(self)
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi'], 
                                  capture_output=True, text=True)
            networks = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3: 
                        ssid, signal, sec = parts[0], int(parts[1]), ':'.join(parts[2:])
                        networks.append((ssid, signal, sec))
            networks.sort(key=lambda x: x[1], reverse=True)
            
            for ssid, signal, sec in networks:
                act = QAction(f"{ssid} ({signal}%) - {sec}", self)
                act.triggered.connect(lambda checked, s=ssid: self.open_wifi_html(s))
                menu.addAction(act)
        except Exception as e:
            act = QAction(f"Error: {e}", self)
            act.setEnabled(False)
            menu.addAction(act)
        
        menu.addSeparator()
        refresh = QAction("Refresh Networks", self)
        refresh.triggered.connect(self.refresh_wifi_networks)
        menu.addAction(refresh)
        
        menu.exec(self.mapToGlobal(self.wifi_indicator.geometry().bottomRight()))

    def open_wifi_html(self, ssid):
        self.current_ssid = ssid
        self.keyboard_widget.setVisible(True)
        html = f"""
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>WiFi Password</title>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                }}
                
                body {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    padding: 40px 20px;
                }}
                
                .container {{
                    background-color: rgba(255, 255, 255, 0.9);
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                    width: 100%;
                    max-width: 450px;
                    padding: 30px;
                    text-align: center;
                    margin-top: 30px;
                }}
                
                h1 {{
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 24px;
                }}
                
                .ssid {{
                    color: #667eea;
                    font-weight: bold;
                    font-size: 18px;
                    margin-bottom: 25px;
                    word-break: break-word;
                }}
                
                .input-group {{
                    margin-bottom: 25px;
                    text-align: left;
                }}
                
                label {{
                    display: block;
                    margin-bottom: 8px;
                    color: #555;
                    font-weight: 500;
                }}
                
                input[type="text"] {{
                    width: 100%;
                    padding: 15px;
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    font-size: 16px;
                    transition: border-color 0.3s;
                }}
                
                input[type="text"]:focus {{
                    border-color: #667eea;
                    outline: none;
                }}
                
                .button-group {{
                    display: flex;
                    gap: 15px;
                }}
                
                button {{
                    flex: 1;
                    padding: 15px;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                
                .connect-btn {{
                    background-color: #667eea;
                    color: white;
                }}
                
                .connect-btn:hover {{
                    background-color: #5a6fd5;
                    transform: translateY(-2px);
                }}
                
                .home-btn {{
                    background-color: #f8f9fa;
                    color: #333;
                    border: 1px solid #ddd;
                }}
                
                .home-btn:hover {{
                    background-color: #e9ecef;
                    transform: translateY(-2px);
                }}
                
                .status-message {{
                    margin-top: 20px;
                    padding: 12px;
                    border-radius: 8px;
                    display: none;
                    font-weight: 500;
                }}
                
                .error {{
                    background-color: #ffebee;
                    color: #d32f2f;
                }}
                
                .success {{
                    background-color: #e8f5e9;
                    color: #388e3c;
                }}
                
                @media (max-width: 480px) {{
                    .container {{
                        padding: 20px;
                    }}
                    
                    .button-group {{
                        flex-direction: column;
                    }}
                }}
            </style>
        </head>
        <body onload="setupChannel()">
            <div class="container">
                <h1>Masukkan Password WiFi</h1>
                <div class="ssid" id="ssid-display">{ssid}</div>
                
                <div class="input-group">
                    <label for="wifiPwd">Password</label>
                    <input type="text" id="wifiPwd" placeholder="Masukkan password WiFi">
                </div>
                
                <div class="button-group">
                    <button class="connect-btn" onclick="connectWifi()">Connect</button>
                    <button class="home-btn" onclick="goHome()">Home</button>
                </div>
                
                <div id="statusMessage" class="status-message"></div>
            </div>

            <script>
                function setupChannel() {{
                    new QWebChannel(qt.webChannelTransport, function(channel) {{
                        window.pywebchannel = channel.objects.pywebchannel;
                    }});
                }}
                
                function connectWifi() {{
                    var pwd = document.getElementById('wifiPwd').value;
                    var statusElement = document.getElementById('statusMessage');
                    
                    if (!pwd) {{
                        statusElement.textContent = "Password tidak boleh kosong!";
                        statusElement.className = "status-message error";
                        statusElement.style.display = "block";
                        return;
                    }}
                    
                    if (window.pywebchannel) {{ 
                        window.pywebchannel.sendWifiPassword(pwd); 
                        statusElement.textContent = "Menghubungkan...";
                        statusElement.className = "status-message success";
                        statusElement.style.display = "block";
                    }} else {{ 
                        statusElement.textContent = "WebChannel belum siap, coba lagi sebentar.";
                        statusElement.className = "status-message error";
                        statusElement.style.display = "block";
                    }}
                }}
                
                function goHome() {{
                    if (window.pywebchannel) {{ 
                        window.pywebchannel.goHome(); 
                    }} else {{
                        alert("WebChannel belum siap, coba lagi sebentar.");
                    }}
                }}
            </script>
        </body>
        </html>
        """
        self.browser.setHtml(html)
        self.browser.page().runJavaScript("""
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pywebchannel = channel.objects.pywebchannel;
            });
        """)

    def run_nmcli_connect(self, ssid, password):
        def worker():
            try:
                result = subprocess.run(
                    ['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"✅ Terhubung ke {ssid}")
                else:
                    print(f"❌ Gagal terhubung ke {ssid}: {result.stderr}")
            except Exception as e:
                print("❌ Error:", e)

        threading.Thread(target=worker, daemon=True).start()




    def refresh_wifi_networks(self):
        try: 
            subprocess.run(['nmcli', 'dev', 'wifi', 'rescan'], capture_output=True, timeout=10)
        except Exception as e: 
            print("Error refreshing WiFi:", e)

    def update_wifi_status(self, ssid, connected):
        quality = self.wifi_monitor.get_wifi_quality() if connected else 0
        self.wifi_indicator.update_status(ssid, connected, quality)

    # ===== RFID =====
    def handle_rfid(self, rfid_data):
        print("📡 Dari ESP32 (RFID):", rfid_data, flush=True)
        
        try:
            self.browser.activateWindow()
            self.browser.setFocus()
            time.sleep(0.1)
            
            pyautogui.typewrite(rfid_data)
            time.sleep(0.05)
            pyautogui.press("enter")
            print("✅ RFID berhasil diinput")
            
        except Exception as e:
            print("❌ Error:", e)
            # Fallback ke JavaScript
            js = f"""
            var f=document.activeElement;
            if(f&&(f.tagName==='INPUT'||f.tagName==='TEXTAREA')){{
                f.value='{rfid_data}';
                f.dispatchEvent(new Event('input',{{bubbles:true}}));
                f.dispatchEvent(new Event('change',{{bubbles:true}}));
                var form = f.closest('form');
                if(form) form.dispatchEvent(new Event('submit', {{bubbles: true}}));
            }}
            """
            self.browser.page().runJavaScript(js)


    def closeEvent(self, event):
        self.serial_thread.stop()
        self.focus_timer.stop()
        self.wifi_monitor.stop()
        event.accept()
        
    

# ===== Run =====
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebApp()
    sys.exit(app.exec())