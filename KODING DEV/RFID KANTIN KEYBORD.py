import sys
import time
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout,
    QWidget, QPushButton, QHBoxLayout, QGridLayout
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QThread, pyqtSignal


PORT = "/dev/ttyACM0"   # ganti sesuai port ESP32 kamu
BAUD = 115200


class SerialThread(QThread):
    data_received = pyqtSignal(str)

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
                print("? Terkoneksi ke", self.port)
                return
            except Exception as e:
                print("? Gagal buka port, retry 2 detik...", e)
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
                print("?? Serial error, reconnect:", e)
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
        
class WebApp(QMainWindow):
    def __init__(self):
        super().__init__()
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Browser di atas
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://pesatkantin.com/order-self"))
        layout.addWidget(self.browser, stretch=7)

        # Keyboard di bawah
        keyboard = QWidget()
        grid = QGridLayout(keyboard)

        # Baris huruf
        rows = [
            list("QWERTYUIOP"),
            list("ASDFGHJKL"),
            list("ZXCVBNM"),
            list("1234567890")
        ]

        row_idx = 0
        for row in rows:
            col_idx = 0
            for key in row:
                grid.addWidget(self.make_button(key), row_idx, col_idx)
                col_idx += 1
            row_idx += 1

        # Tambah tombol spasi, backspace, enter
        grid.addWidget(self.make_button("Space"), row_idx, 0, 1, 5)
        grid.addWidget(self.make_button("Backspace"), row_idx, 5, 1, 2)
        grid.addWidget(self.make_button("Enter"), row_idx, 7, 1, 3)

        layout.addWidget(keyboard, stretch=3)

        self.showFullScreen()

        # Jalankan thread serial
        self.serial_thread = SerialThread(PORT, BAUD)
        self.serial_thread.data_received.connect(self.handle_rfid)
        self.serial_thread.start()

    def make_button(self, text):
        btn = QPushButton(text)
        btn.setStyleSheet("font-size: 18px; padding: 12px;")
        btn.clicked.connect(lambda _, t=text: self.send_key(t))
        return btn

    def send_key(self, key):
        """Kirim input ke form web"""
        if key == "Enter":
            js = """
            var input = document.activeElement;
            if (input && input.tagName === "INPUT") {
                var evtDown = new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true});
                var evtUp = new KeyboardEvent('keyup', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true});
                input.dispatchEvent(evtDown);
                input.dispatchEvent(evtUp);
            }
            """
        elif key == "Backspace":
            js = """
            var input = document.activeElement;
            if (input && input.tagName === "INPUT") {
                // hapus 1 karakter
                input.value = input.value.slice(0, -1);
                var evt = new KeyboardEvent('input', {bubbles:true});
                input.dispatchEvent(evt);
                var evtUp = new KeyboardEvent('keyup', {key:'Backspace', code:'Backspace', keyCode:8, which:8, bubbles:true});
                input.dispatchEvent(evtUp);
            }
            """
        elif key == "Space":
            js = """
            var input = document.activeElement;
            if (input && input.tagName === "INPUT") {
                input.value = input.value + " ";
                var evtDown = new KeyboardEvent('keydown', {key:' ', code:'Space', keyCode:32, which:32, bubbles:true});
                var evtUp = new KeyboardEvent('keyup', {key:' ', code:'Space', keyCode:32, which:32, bubbles:true});
                input.dispatchEvent(evtDown);
                input.dispatchEvent(evtUp);
            }
            """
        else:
            js = f"""
            var input = document.activeElement;
            if (input && input.tagName === "INPUT") {{
                input.value = input.value + "{key}";
                // trigger input & key events
                var evtInput = new Event('input', {{ bubbles: true }});
                input.dispatchEvent(evtInput);

                var evtDown = new KeyboardEvent('keydown', {{key:'{key}', code:'Key{key.upper()}', keyCode:{ord(key)}, which:{ord(key)}, bubbles:true}});
                var evtUp = new KeyboardEvent('keyup', {{key:'{key}', code:'Key{key.upper()}', keyCode:{ord(key)}, which:{ord(key)}, bubbles:true}});
                input.dispatchEvent(evtDown);
                input.dispatchEvent(evtUp);
            }}
            """
        self.browser.page().runJavaScript(js)


    def handle_rfid(self, rfid_data):
        print("?? Dari ESP32:", rfid_data)
        js = f"""
        var input = document.activeElement;
        if (input && input.tagName === "INPUT") {{
            input.value = "{rfid_data}";
        }}
        """
        self.browser.page().runJavaScript(js)

    def closeEvent(self, event):
        self.serial_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebApp()
    sys.exit(app.exec_())

