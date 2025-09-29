//https://microcontrollerslab.com/rdm6300-rdm630-rfid-reader-esp32-tutorial/

// Sketch ESP32 untuk pembaca RFID (mengganti SoftwareSerial -> Serial2)
#include <Arduino.h>

// Pilih pin RX2 dan TX2 (ubah sesuai wiring kamu)
const int RX2_PIN = 0; // terima dari modul RFID TX
const int TX2_PIN = 1; // kirim ke modul RFID RX (kalo perlu)
//const int RX2_PIN = 16; // terima dari modul RFID TX
//const int TX2_PIN = 17; // kirim ke modul RFID RX (kalo perlu)
HardwareSerial RFID(1);  // gunakan Serial2 -> instance 2

String textBuffer = "";
String CardNumber = "1100773C55"; // contoh ID akses yang diterima

void setup() {
  // Serial USB untuk debug
  Serial.begin(115200);
//  while(!Serial) delay(10);ioy

  // Serial2 (RFID) pake baud 9600 (sesuaikan modul)
  RFID.begin(9600, SERIAL_8N1, RX2_PIN, TX2_PIN);
//  Serial.println("Bring your RFID Card Closer...");
}

unsigned long lastReadMillis = 0;
const unsigned long readTimeout = 100; // ms, jeda untuk menganggap frame selesai

// ... bagian atas tetap sama ...
String buffer = "";

void loop() {
  // baca semua byte yang masuk dari RFID
//  Serial.println("Bring your RFID Card Closer...");
  while (RFID.available() > 0) {
    char c = (char)RFID.read();
    buffer += c;
  }

  // kalau buffer punya frame lengkap (STX .. ETX), proses secara langsung
  // STX = 0x02, ETX = 0x03
  int stxPos = buffer.indexOf((char)0x02);
  int etxPos = buffer.indexOf((char)0x03);

  // proses semua frame lengkap yang ada (bisa lebih dari 1)
  while (stxPos != -1 && etxPos != -1 && etxPos > stxPos) {
    String frame = buffer.substring(stxPos, etxPos + 1); // termasuk ETX
    processFrame(frame);
    // hapus bagian yang sudah diproses dari buffer
    buffer = buffer.substring(etxPos + 1);
    // cari lagi
    stxPos = buffer.indexOf((char)0x02);
    etxPos = buffer.indexOf((char)0x03);
  }

  delay(5); // ringan, agar cpu tidak 100%
}

unsigned long lastPrintMillis = 0;
const unsigned long printInterval = 2000; // 2 detik

void processFrame(const String &raw) {
  if (raw.length() >= 12) {
    String cardId = raw.substring(1, 11);

    unsigned long now = millis();
    if (now - lastPrintMillis >= printInterval) {
      Serial.println(cardId);   // cuma cetak sekali tiap 2 detik
      lastPrintMillis = now;

      if (CardNumber.indexOf(cardId) >= 0) {
        // akses diterima
      } else {
        // akses ditolak
      }
    }
  }
}


//void processFrame(const String &raw) {
//  // raw misal: [STX]YYYYYYYYYYCC[ETX]  - tergantung modul
//  // contoh: ambil substring 1..10 (karakter ID) jika sesuai
//  if (raw.length() >= 12) { // minimal panjang valid; sesuaikan jika perlu
//    String cardId = raw.substring(1, 11); // indices 1..10
//    Serial.println(cardId);
//
//    // contoh pengecekan access
//    if (CardNumber.indexOf(cardId) >= 0) {
//      // akses diterima
//    } else {
//      // akses ditolak
//    }
//  } else {
//    // debug: frame pendek/tidak valid
//    // Serial.println("Frame pendek: " + raw);
//  }
//  // jangan delay panjang di proses rutin (biar tidak telat memproses frame berikutnya)
//}
