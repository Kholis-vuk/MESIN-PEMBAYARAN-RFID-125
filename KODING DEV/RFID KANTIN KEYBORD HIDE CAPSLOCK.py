#!/usr/bin/env python3
import sys
import time
import serial
import subprocess
import threading
import pyautogui
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QPushButton, QGridLayout, QHBoxLayout, QLabel,
    QMenu, QAction
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QPainter, QColor

PORT = "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_0C:4E:A0:60:02:D8-if00"
BAUD = 115200


# ===== WiFi Monitor =====
class WiFiMonitor(QThread):
    wifi_status_changed = pyqtSignal(str, bool)

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
        except Exception as e:
            print(f"Error getting WiFi info: {e}")
            return "Error", False

    def get_wifi_quality(self):
        try:
            result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SIGNAL', 'dev', 'wifi'],
                                    capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                if line.startswith('yes:'):
                    return int(line.split(':')[1])
            return 0
        except Exception:
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
            painter.drawRect(cx - 8, cy + 8, 4, 4)
            if self.quality > 25:
                painter.drawRect(cx - 12, cy + 4, 4, 8)
                painter.drawRect(cx + 8, cy + 4, 4, 8)
            if self.quality > 50:
                painter.drawRect(cx - 16, cy, 4, 12)
                painter.drawRect(cx + 12, cy, 4, 12)
            if self.quality > 75:
                painter.drawRect(cx - 20, cy - 4, 4, 16)
                painter.drawRect(cx + 16, cy - 4, 4, 16)
        else:
            painter.setPen(QColor(255, 0, 0))
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(10, 10, 30, 30)
            painter.drawLine(30, 10, 10, 30)


# ===== Serial Thread =====
class SerialThread(QThread):
    data_received = pyqtSignal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        self.ser = None
        self.running = True

    def connect_serial(self):
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
                try: self.ser.close()
                except: pass
                time.sleep(2)
                self.connect_serial()

    def stop(self):
        self.running = False
        if self.ser: self.ser.close()
        self.quit()
        self.wait()


# ===== Main WebApp =====
class WebApp(QMainWindow):
    def __init__(self):
        super().__init__()
        central = QWidget()
        self.setCentralWidget(central)

        self.caps_lock = False
        self.letter_buttons = []

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 5, 10, 5)
        title = QLabel("Pesat Kantin - Self Order")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        self.wifi_indicator = WiFiIndicator()
        self.wifi_indicator.setCursor(Qt.PointingHandCursor)
        self.wifi_indicator.mousePressEvent = self.show_wifi_menu
        h_layout.addWidget(self.wifi_indicator)
        layout.addWidget(header)

        # Browser
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://pesatkantin.com/order-self"))
        layout.addWidget(self.browser, stretch=7)

        # Keyboard
        self.keyboard_widget = QWidget()
        self.keyboard_widget.setVisible(False)
        grid = QGridLayout(self.keyboard_widget)
        rows = [list("QWERTYUIOP"), list("ASDFGHJKL"), list("ZXCVBNM"), list("1234567890")]
        row_idx = 0
        for row in rows:
            col_idx = 0
            for key in row:
                btn = self.make_button(key)
                grid.addWidget(btn, row_idx, col_idx)
                col_idx += 1
                if key.isalpha():
                    self.letter_buttons.append(btn)
            row_idx += 1

        # Baris fungsi
        grid.addWidget(self.make_button("CapsLock"), row_idx, 0, 1, 2)
        grid.addWidget(self.make_button("Space"), row_idx, 2, 1, 4)
        grid.addWidget(self.make_button("Backspace"), row_idx, 6, 1, 2)
        grid.addWidget(self.make_button("Enter"), row_idx, 8, 1, 2)
        grid.addWidget(self.make_button("Close"), row_idx, 10, 1, 2)

        layout.addWidget(self.keyboard_widget, stretch=3)
        self.showFullScreen()

        # Timer fokus
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.check_focused_element)
        self.focus_timer.start(500)

        # Serial thread
        self.serial_thread = SerialThread(PORT, BAUD)
        self.serial_thread.data_received.connect(self.handle_rfid)
        self.serial_thread.start()

        # WiFi monitor
        self.wifi_monitor = WiFiMonitor()
        self.wifi_monitor.wifi_status_changed.connect(self.update_wifi_status)
        self.wifi_monitor.start()

    # ===== WiFi =====
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
                        ssid, signal, security = parts[0], parts[1], ':'.join(parts[2:])
                        networks.append((ssid, int(signal), security))
            networks.sort(key=lambda x: x[1], reverse=True)
            for ssid, signal, security in networks:
                action = QAction(f"{ssid} ({signal}%) - {security}", self)
                action.triggered.connect(lambda checked, s=ssid: self.connect_to_wifi(s))
                menu.addAction(action)
        except Exception as e:
            a = QAction(f"Error: {e}", self)
            a.setEnabled(False)
            menu.addAction(a)
        menu.addSeparator()
        refresh_action = QAction("Refresh Networks", self)
        refresh_action.triggered.connect(self.refresh_wifi_networks)
        menu.addAction(refresh_action)
        menu.exec_(self.mapToGlobal(self.wifi_indicator.geometry().bottomRight()))

    def connect_to_wifi(self, ssid):
        def t():
            try:
                result = subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid],
                                        capture_output=True, text=True, timeout=30)
                print(f"✅ Terhubung ke {ssid}" if result.returncode==0 else f"❌ Gagal ke {ssid}")
            except Exception as e:
                print(f"❌ Error connecting to {ssid}: {e}")
        threading.Thread(target=t, daemon=True).start()

    def refresh_wifi_networks(self):
        try: subprocess.run(['nmcli', 'dev', 'wifi', 'rescan'], capture_output=True, timeout=10)
        except Exception as e: print(f"Error refreshing WiFi: {e}")

    def update_wifi_status(self, ssid, connected):
        quality = self.wifi_monitor.get_wifi_quality() if connected else 0
        self.wifi_indicator.update_status(ssid, connected, quality)

    # ===== Keyboard =====
    def make_button(self, text):
        btn = QPushButton(text)
        btn.setStyleSheet("font-size: 18px; padding: 12px;")
        btn.clicked.connect(lambda _, t=text: self.send_key(t))
        return btn

    def check_focused_element(self):
        js = """
        var f = document.activeElement;
        if(f && (f.tagName==='INPUT' || f.tagName==='TEXTAREA')) 'input';
        else 'none';
        """
        self.browser.page().runJavaScript(js, self.handle_focus_check)

    def handle_focus_check(self, result):
        self.keyboard_widget.setVisible(result=='input')

    def send_key(self, key):
        if key=="CapsLock":
            self.caps_lock = not self.caps_lock
            for btn in self.letter_buttons:
                btn.setText(btn.text().upper() if self.caps_lock else btn.text().lower())
            return
        if len(key)==1 and key.isalpha():
            key = key.upper() if self.caps_lock else key.lower()
        if key=="Close":
            self.keyboard_widget.setVisible(False)
            self.browser.page().runJavaScript("""
            var f=document.activeElement;
            if(f && (f.tagName==='INPUT'||f.tagName==='TEXTAREA')) f.blur();
            """)
            return
        if key=="Enter":
            js = """
            var i=document.activeElement;
            if(i&&(i.tagName==='INPUT'||i.tagName==='TEXTAREA')){
                var d=new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true});
                var u=new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true});
                i.dispatchEvent(d);i.dispatchEvent(u);
            }
            """
        elif key=="Backspace":
            js = """
            var i=document.activeElement;
            if(i&&(i.tagName==='INPUT'||i.tagName==='TEXTAREA')){
                i.value=i.value.slice(0,-1);
                var e=new Event('input',{bubbles:true});
                i.dispatchEvent(e);
                var u=new KeyboardEvent('keyup',{key:'Backspace',code:'Backspace',keyCode:8,which:8,bubbles:true});
                i.dispatchEvent(u);
            }
            """
        elif key=="Space":
            js = """
            var i=document.activeElement;
            if(i&&(i.tagName==='INPUT'||i.tagName==='TEXTAREA')){
                i.value+=' ';
                var d=new KeyboardEvent('keydown',{key:' ',code:'Space',keyCode:32,which:32,bubbles:true});
                var u=new KeyboardEvent('keyup',{key:' ',code:'Space',keyCode:32,which:32,bubbles:true});
                i.dispatchEvent(d);i.dispatchEvent(u);
            }
            """
        else:
            js = f"""
            var i=document.activeElement;
            if(i&&(i.tagName==='INPUT'||i.tagName==='TEXTAREA')){{
                i.value+='{key}';
                var e=new Event('input',{{bubbles:true}});
                i.dispatchEvent(e);
                var d=new KeyboardEvent('keydown',{{key:'{key}',code:'Key{key.upper()}',keyCode:{ord(key)},which:{ord(key)},bubbles:true}});
                var u=new KeyboardEvent('keyup',{{key:'{key}',code:'Key{key.upper()}',keyCode:{ord(key)},which:{ord(key)},bubbles:true}});
                i.dispatchEvent(d);i.dispatchEvent(u);
            }}
            """
        self.browser.page().runJavaScript(js)

    # ===== RFID =====
    def handle_rfid(self, rfid_data):
        print("📡 Dari ESP32:", rfid_data)
        try: self.browser.setFocus(); time.sleep(0.06)
        except: pass
        try:
            pyautogui.typewrite(rfid_data)
            pyautogui.press("enter")
        except Exception as e:
            print("⚠️ pyautogui error:", e)

    def closeEvent(self, event):
        self.serial_thread.stop()
        self.focus_timer.stop()
        self.wifi_monitor.stop()
        event.accept()


if __name__=="__main__":
    app = QApplication(sys.argv)
    window = WebApp()
    sys.exit(app.exec_())
