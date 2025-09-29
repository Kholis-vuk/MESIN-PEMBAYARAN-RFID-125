////https://microcontrollerslab.com/rdm6300-rdm630-rfid-reader-esp32-tutorial/
//
//// Sketch ESP32 untuk pembaca RFID (mengganti SoftwareSerial -> Serial2)
//#include <Arduino.h>
//
//// Pilih pin RX2 dan TX2 (ubah sesuai wiring kamu)
////const int RX2_PIN = 1; // terima dari modul RFID TX
////const int TX2_PIN = 0; // kirim ke modul RFID RX (kalo perlu)
//const int RX2_PIN = 16; // terima dari modul RFID TX
//const int TX2_PIN = 17; // kirim ke modul RFID RX (kalo perlu)
//HardwareSerial RFID(2);  // gunakan Serial2 -> instance 2
//
//String textBuffer = "";
//String CardNumber = "1100773C55"; // contoh ID akses yang diterima
//
//void setup() {
//  // Serial USB untuk debug
//  Serial.begin(115200);
////  while(!Serial) delay(10);ioy
//
//  // Serial2 (RFID) pake baud 9600 (sesuaikan modul)
//  RFID.begin(9600, SERIAL_8N1, RX2_PIN, TX2_PIN);
////  Serial.println("Bring your RFID Card Closer...");
//}
//
//unsigned long lastReadMillis = 0;
//const unsigned long readTimeout = 100; // ms, jeda untuk menganggap frame selesai
//
//void loop() {
//  // baca semua byte yang masuk dari RFID
//  while (RFID.available() > 0) {
//    char c = (char)RFID.read();
//    textBuffer += c;
//    lastReadMillis = millis();
//  }
//
//  // jika buffer berisi data dan sudah melewati timeout -> proses
//  if (textBuffer.length() > 0 && (millis() - lastReadMillis) > readTimeout) {
//    // bersihkan whitespace di ujung
//    textBuffer.trim();
//
//    // jika panjangnya mencukupi (>20 seperti kode original), lakukan check
//    if (textBuffer.length() > 20) {
//      checkCard(textBuffer);
//    } else {
////      Serial.printf("Data pendek diterima (%u): %s\n", (unsigned)textBuffer.length(), textBuffer.c_str());
//    }
//
//    // kosongkan buffer utk frame selanjutnya
//    textBuffer = "";
//  }
//
//  // sedikit delay agar loop tidak makan CPU 100%
//  delay(5);
//}
//
//void checkCard(const String& raw) {
//  // sesuai kode asal: ambil substring dari index 1 sampai 10 (panjang 10)
//  // pastikan panjang cukup dulu
//  if (raw.length() >= 11) {
//    String cardId = raw.substring(1, 11); // karakter [1..10]
////    Serial.println("Card raw : " + raw);
//    Serial.println(cardId);
////    Serial.println("Access ID: " + CardNumber);
//
//    if (CardNumber.indexOf(cardId) >= 0) {
////      Serial.println("Access accepted");
//    } else {
////      Serial.println("Access denied");
//    }
//  } else {
////    Serial.println("Format data RFID tidak sesuai: " + raw);
//  }
//
////  Serial.println();
////  Serial.println("Bring your RFID card closer …");
//  delay(2000); // delay seperti original
//}
