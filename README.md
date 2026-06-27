<p align="center">
  <img src="assets/modinteractive-logo.png" alt="modInteractive logo" width="760">
</p>

# modInteractive

Raspberry Pi 5 üzerinde çalışan PIR sensör veya kamera hareket algılama ile HDMI ekranda tam ekran video oynatan kiosk / digital signage uygulaması.

Bu sürümde varsayılan tetik kaynağı **PIR sensör** olarak ayarlanmıştır. Kamera opsiyoneldir; kullanıcı isterse `config.json`, admin panel veya komut satırı üzerinden kamera moduna geçebilir.

## Temel Mantık

1. Raspberry Pi 5 açılır.
2. `modinteractive` systemd servisi otomatik başlar.
3. Uygulama varsayılan olarak PIR sensörü dinler.
4. PIR hareket algıladığında `videos/selamlama.mp4` dosyası HDMI ekranda tam ekran oynatılır.
5. Video bitince sistem cooldown süresine girer.
6. Cooldown bitince yeniden hareket bekler.

## Trigger Seçenekleri

| Mod | Açıklama |
|---|---|
| `pir` | PIR GPIO sensörü ile hareket algılama. Varsayılan mod budur. |
| `camera` | Kamera/OpenCV ile görüntü üzerinden hareket algılama. |

Varsayılan config:

```json
{
  "trigger": {
    "source": "pir"
  }
}
```

Tek seferlik PIR modu:

```bash
python main.py --source pir
```

Tek seferlik kamera modu:

```bash
python main.py --source camera
```

## PIR Bağlantısı

Kod varsayılan olarak **BCM GPIO 17** kullanır.

```text
PIR VCC  -> Raspberry Pi 5V
PIR GND  -> Raspberry Pi GND
PIR OUT  -> BCM GPIO 17 / fiziksel pin 11
```

Önemli: Raspberry Pi GPIO pinleri 3.3V seviyesindedir. PIR OUT hattı 5V çıkış veriyorsa doğrudan GPIO'ya bağlanmamalıdır.

Detay için:

```text
PIR_WIRING_CHECK.md
PIR_SENSOR_NOTES.md
```

## Donanım Gereksinimleri

- Raspberry Pi 5
- PIR sensör
- HDMI ekran / TV / Smart Monitor
- microSD kart
- Güçlü Raspberry Pi 5 adaptörü
- Opsiyonel USB webcam veya Raspberry Pi Camera
- Opsiyonel USB bellek veya ağ üzerinden video aktarımı

## Yazılım Gereksinimleri

- Raspberry Pi OS
- Python 3
- Flask
- mpv
- systemd
- gpiozero / lgpio
- Kamera modu için OpenCV, NumPy, v4l-utils

Kurulum scripti gerekli paketleri kurar.

## Hızlı Kurulum

```bash
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive
cp /path/to/video.mp4 videos/selamlama.mp4
sudo bash install.sh
sudo systemctl start modinteractive
sudo systemctl status modinteractive
```

## PIR Test

```bash
cd /opt/modInteractive
/opt/modInteractive/venv/bin/python tools/test_pir.py --pin 17
```

Hareket algılanırsa terminalde `MOTION` görünür.

## Sağlık Kontrolü

PIR modu:

```bash
cd /opt/modInteractive
/opt/modInteractive/venv/bin/python main.py --source pir --check
```

Kamera modu:

```bash
cd /opt/modInteractive
/opt/modInteractive/venv/bin/python main.py --source camera --check
```

## Servis Komutları

```bash
sudo systemctl start modinteractive
sudo systemctl stop modinteractive
sudo systemctl restart modinteractive
sudo systemctl status modinteractive
journalctl -u modinteractive -f
```

## Admin Panel

Varsayılan port:

```text
http://PI_IP_ADRESI:8080
```

Admin panelden şu ayarlar yapılabilir:

- Trigger source: PIR veya camera
- PIR GPIO pin
- PIR active_high / pull_up
- PIR bounce ve warmup
- Kamera index / çözünürlük / FPS
- Video yolu
- Ses seviyesi
- Fullscreen
- Cooldown

Trigger source değiştirildikten sonra servisi yeniden başlat:

```bash
sudo systemctl restart modinteractive
```

## Video Dosyası

Varsayılan video yolu:

```text
videos/selamlama.mp4
```

Kurulumdan sonra video değiştirme:

```bash
sudo cp your_video.mp4 /opt/modInteractive/videos/selamlama.mp4
sudo chown pi:pi /opt/modInteractive/videos/selamlama.mp4
sudo systemctl restart modinteractive
```

Video elle test:

```bash
mpv --fs /opt/modInteractive/videos/selamlama.mp4
```

## Proje Yapısı

```text
modInteractive/
├── main.py
├── app.py
├── config.json
├── requirements.txt
├── install.sh
├── README.md
├── PIR_WIRING_CHECK.md
├── PIR_SENSOR_NOTES.md
├── tools/
│   └── test_pir.py
├── assets/
│   └── modinteractive-logo.png
├── core/
│   ├── config.py
│   ├── camera.py
│   ├── detector.py
│   ├── pir.py
│   ├── player.py
│   ├── logger.py
│   └── healthcheck.py
├── admin/
│   ├── server.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── style.css
│       └── app.js
├── systemd/
│   └── modinteractive.service
└── videos/
    └── selamlama.mp4
```

## Sorun Giderme

PIR görünmüyorsa:

```bash
sudo apt install -y python3-gpiozero python3-lgpio
cd /opt/modInteractive
/opt/modInteractive/venv/bin/python tools/test_pir.py --pin 17
```

Video oynamıyorsa:

```bash
ls -lh /opt/modInteractive/videos/
mpv --version
mpv --fs /opt/modInteractive/videos/selamlama.mp4
```

Servis başlamıyorsa:

```bash
sudo systemctl status modinteractive
journalctl -u modinteractive -f
sudo -u pi /opt/modInteractive/venv/bin/python /opt/modInteractive/main.py --source pir --check
```

Kamera kullanılacaksa:

```bash
ls -la /dev/video*
v4l2-ctl --list-devices
/opt/modInteractive/venv/bin/python main.py --source camera --check
```

## Lisans

MIT License

<!-- REMOTE_ADMIN_PANEL_START -->
## Uzaktan Admin Panel

modInteractive, Raspberry Pi 5 üzerinde çalışan modern bir web admin paneli içerir. Aynı Wi-Fi veya yerel ağdaki telefon, tablet, laptop veya masaüstü bilgisayardan kontrol edilebilir.

Admin paneli açmak için:

    http://<RASPBERRY_PI_IP>:8080

Örnek:

    http://192.168.0.30:8080

Raspberry Pi IP adresini öğrenmek için:

    hostname -I

### Panelden yapılabilen işlemler

- Tetik kaynağı seçimi: PIR GPIO sensor veya Camera motion detection
- PIR ayarları: BCM GPIO pin, bounce time, warmup, poll interval, active-high, internal pull-up
- Video ayarları: video path, volume, fullscreen playback
- Algılama ayarları: cooldown, motion sensitivity, minimum motion area, frame skip
- Tarayıcıdan video testi
- Sistem durumu görüntüleme
- Uygulama loglarını görüntüleme
- Telefon, tablet veya bilgisayardan uzaktan kontrol

PIR ile Camera arasında geçiş yaptıktan sonra ayarları kaydedip servisi yeniden başlatmak gerekir:

    sudo systemctl restart modinteractive

### Mobil ve masaüstü ekran görüntüleri

<p align="center">
  <img src="docs/images/admin-mobile-status.png" alt="modInteractive mobile admin status screen" width="260">
</p>

<p align="center">
  <img src="docs/images/admin-desktop-config-overview.png" alt="modInteractive desktop admin configuration overview" width="820">
</p>

<p align="center">
  <img src="docs/images/admin-desktop-config-settings.png" alt="modInteractive desktop PIR and video settings" width="820">
</p>

<p align="center">
  <img src="docs/images/admin-desktop-status.png" alt="modInteractive desktop system status" width="820">
</p>

<p align="center">
  <img src="docs/images/admin-desktop-logs.png" alt="modInteractive desktop logs screen" width="820">
</p>

### Kullanım komutları

Uygulamayı cihaz açılışında otomatik başlatmak için:

    sudo systemctl enable modinteractive
    sudo systemctl restart modinteractive
    sudo systemctl status modinteractive --no-pager

Canlı log izleme:

    journalctl -u modinteractive -f

Uygulamayı durdurma:

    sudo systemctl stop modinteractive

Ayar değişikliğinden sonra yeniden başlatma:

    sudo systemctl restart modinteractive
<!-- REMOTE_ADMIN_PANEL_END -->

<!-- WATAM_LICENSE_START -->
## Lisans

WATAM
<!-- WATAM_LICENSE_END -->

Built with ❤️ by WATAM
