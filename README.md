# modInteractive

Raspberry Pi 5 üzerinde çalışan, kamera hareket algılayınca HDMI ekranda tam ekran video oynatan cafe, mağaza ve vitrin ekran sistemi.

Touchscreen gerekli değildir. HDMI ekran veya TV yeterlidir.

## Amaç

modInteractive, Raspberry Pi 5'e bağlı kamera ile hareket algılar. Hareket algılandığında belirlenen video dosyasını HDMI ekranda tam ekran oynatır. Video bittikten sonra sistem cooldown süresine girer ve ardından tekrar hareket algılamaya devam eder.

Bu sistem özellikle cafe, restoran, mağaza, karşılama ekranı, vitrin ekranı ve etkileşimli reklam ekranı senaryoları için tasarlanmıştır.

## Özellikler

* OpenCV ile hareket algılama
* MOG2 background subtraction + frame differencing
* mpv ile tam ekran video oynatma
* Cooldown sistemi
* Kamera reconnect desteği
* Video oynarken yeniden tetiklemeyi engelleme
* Konsol + dosya loglama
* Rotasyonlu log dosyası
* Sistem sağlık kontrolü
* Web admin paneli
* Systemd servisi
* Raspberry Pi 5 uyumlu kurulum
* HDMI ekran / TV desteği
* Touchscreen gerektirmez

## Donanım Gereksinimleri

* Raspberry Pi 5
* 8GB RAM önerilir
* Raspberry Pi Camera Module veya USB webcam
* HDMI ekran veya TV
* 32GB veya daha büyük microSD kart
* Güçlü ve kaliteli Raspberry Pi 5 adaptörü
* İnternet bağlantısı

## Yazılım Gereksinimleri

* Raspberry Pi OS
* Python 3
* OpenCV
* NumPy
* Flask
* mpv
* v4l-utils
* systemd

## Hızlı Kurulum

```bash
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive
cp /path/to/greeting.mp4 videos/selamlama.mp4
sudo bash install.sh
sudo systemctl start modinteractive
sudo systemctl status modinteractive
```

## Manuel Kurulum

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-opencv python3-numpy mpv v4l-utils

git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive

python3 -m venv --system-site-packages venv
source venv/bin/activate

pip install -r requirements.txt

cp /path/to/greeting.mp4 videos/selamlama.mp4

python main.py --check
python main.py
```

## Systemd Servisi

Kurulum scripti servisi otomatik kurar ve enable eder. Servisi başlatmak için:

```bash
sudo systemctl start modinteractive
```

Servis durumunu görmek için:

```bash
sudo systemctl status modinteractive
```

Logları canlı takip etmek için:

```bash
journalctl -u modinteractive -f
```

Servisi durdurmak için:

```bash
sudo systemctl stop modinteractive
```

Servisi yeniden başlatmak için:

```bash
sudo systemctl restart modinteractive
```

## Kullanım

Normal çalıştırma:

```bash
python main.py
```

Sistem kontrolü:

```bash
python main.py --check
```

Özel config dosyası ile çalıştırma:

```bash
python main.py --config /path/to/config.json
```

Log seviyesi belirterek çalıştırma:

```bash
python main.py --log-level DEBUG
```

## Admin Panel

Admin panel varsayılan olarak port 8080 üzerinden çalışır.

Aynı ağdaki telefon, tablet veya bilgisayardan şu adreslerden biriyle açılabilir:

```text
http://raspberrypi.local:8080
```

veya:

```text
http://PI_IP_ADRESI:8080
```

Admin panel ile şunlar yapılabilir:

* Kamera index ayarı
* Kamera çözünürlük ayarı
* FPS ayarı
* Hareket hassasiyeti ayarı
* Minimum hareket alanı ayarı
* Cooldown süresi ayarı
* Frame skip ayarı
* Video yolu ayarı
* Ses seviyesi ayarı
* Fullscreen aç/kapat
* Test video oynatma
* Sistem durumunu görme
* Logları görme

Admin panel opsiyoneldir. Panel çalışmasa bile ana kamera ve video sistemi çalışmaya devam eder.

## Config Dosyası

Ana ayarlar `config.json` dosyasındadır.

```json
{
  "system": {
    "log_level": "INFO",
    "project_name": "modInteractive",
    "version": "1.0.0"
  },
  "camera": {
    "index": 0,
    "width": 640,
    "height": 480,
    "fps": 15,
    "backend": "v4l2"
  },
  "detection": {
    "enabled": true,
    "mode": "motion",
    "motion_sensitivity": 500,
    "min_motion_area": 1500,
    "frame_skip": 3,
    "warmup_seconds": 2,
    "cooldown_seconds": 10
  },
  "video": {
    "path": "videos/selamlama.mp4",
    "fullscreen": true,
    "volume": 90,
    "player": "mpv"
  },
  "admin": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8080
  }
}
```

## Config Açıklamaları

| Ayar                           |             Varsayılan | Açıklama                               |
| ------------------------------ | ---------------------: | -------------------------------------- |
| `system.log_level`             |                 `INFO` | Log seviyesi                           |
| `camera.index`                 |                    `0` | Kamera cihaz indeksi                   |
| `camera.width`                 |                  `640` | Kamera görüntü genişliği               |
| `camera.height`                |                  `480` | Kamera görüntü yüksekliği              |
| `camera.fps`                   |                   `15` | Kamera FPS değeri                      |
| `camera.backend`               |                 `v4l2` | Linux kamera backend'i                 |
| `detection.enabled`            |                 `true` | Hareket algılamayı aç/kapat            |
| `detection.mode`               |               `motion` | Algılama modu                          |
| `detection.motion_sensitivity` |                  `500` | Hareket piksel eşiği                   |
| `detection.min_motion_area`    |                 `1500` | Minimum hareket alanı                  |
| `detection.frame_skip`         |                    `3` | Her kaç frame'de bir analiz yapılacağı |
| `detection.warmup_seconds`     |                    `2` | Kamera/detector ısınma süresi          |
| `detection.cooldown_seconds`   |                   `10` | Video sonrası bekleme süresi           |
| `video.path`                   | `videos/selamlama.mp4` | Oynatılacak video dosyası              |
| `video.fullscreen`             |                 `true` | Tam ekran oynatma                      |
| `video.volume`                 |                   `90` | Ses seviyesi                           |
| `video.player`                 |                  `mpv` | Video player                           |
| `admin.enabled`                |                 `true` | Admin panel aç/kapat                   |
| `admin.host`                   |              `0.0.0.0` | Admin panel host                       |
| `admin.port`                   |                 `8080` | Admin panel port                       |

## Video Dosyası

Varsayılan video yolu:

```text
videos/selamlama.mp4
```

Kurulumdan önce veya sonra video dosyanı şu şekilde ekleyebilirsin:

```bash
cp your_video.mp4 videos/selamlama.mp4
```

Kurulum yapıldıktan sonra `/opt/modInteractive` içine video eklemek için:

```bash
sudo cp your_video.mp4 /opt/modInteractive/videos/selamlama.mp4
sudo chown pi:pi /opt/modInteractive/videos/selamlama.mp4
```

Desteklenen video formatları mpv tarafından desteklenen formatlara bağlıdır. Genellikle `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm` kullanılabilir.

## Proje Yapısı

```text
modInteractive/
├── main.py
├── app.py
├── config.json
├── requirements.txt
├── install.sh
├── uninstall.sh
├── README.md
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── camera.py
│   ├── detector.py
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
├── videos/
│   ├── .gitkeep
│   └── selamlama.mp4
└── logs/
    └── .gitkeep
```

## Test Komutları

Kurulumdan önce veya geliştirme sırasında şu komutları çalıştır:

```bash
python3 -m py_compile main.py app.py admin/server.py
python3 -m py_compile core/*.py
bash -n install.sh
bash -n uninstall.sh
python3 main.py --check
```

Systemd dosyasını kontrol etmek için:

```bash
sudo systemd-analyze verify systemd/modinteractive.service
```

Pi üzerindeki kamera cihazlarını görmek için:

```bash
ls -la /dev/video*
v4l2-ctl --list-devices
```

OpenCV ile kamerayı test etmek için:

```bash
python3 -c "import cv2; cap=cv2.VideoCapture(0); print(cap.isOpened()); cap.release()"
```

Videoyu elle test etmek için:

```bash
mpv --fs videos/selamlama.mp4
```

Kurulumdan sonra servis testi:

```bash
sudo systemctl start modinteractive
sudo systemctl status modinteractive
journalctl -u modinteractive -f
```

## Sorun Giderme

### Kamera açılmıyor

Kamera cihazlarını kontrol et:

```bash
ls -la /dev/video*
v4l2-ctl --list-devices
```

Kullanıcıyı video grubuna ekle:

```bash
sudo usermod -a -G video pi
sudo reboot
```

USB kamera kullanıyorsan başka kamera index'i dene:

```json
{
  "camera": {
    "index": 1
  }
}
```

### Raspberry Pi kamera görünmüyor

Raspberry Pi kamera bağlantısını kontrol et.

Raspberry Pi OS üzerinde kamera desteğini test et:

```bash
libcamera-hello
```

OpenCV ile USB kamera daha kolay çalışır. İlk kurulumda USB webcam ile test etmek önerilir.

### Video oynatmıyor

Video dosyası var mı kontrol et:

```bash
ls -la /opt/modInteractive/videos/
```

mpv kurulu mu kontrol et:

```bash
mpv --version
```

Videoyu elle oynat:

```bash
mpv --fs /opt/modInteractive/videos/selamlama.mp4
```

### Servis başlamıyor

Servis durumunu kontrol et:

```bash
sudo systemctl status modinteractive
```

Logları kontrol et:

```bash
journalctl -u modinteractive -f
```

Manuel check çalıştır:

```bash
sudo -u pi /opt/modInteractive/venv/bin/python /opt/modInteractive/main.py --check
```

### Permission hatası

Dosya sahipliğini düzelt:

```bash
sudo chown -R pi:pi /opt/modInteractive
```

Kullanıcıyı gerekli gruplara ekle:

```bash
sudo usermod -a -G video,audio,render,input pi
sudo reboot
```

### Admin panel açılmıyor

Servis loglarını kontrol et:

```bash
journalctl -u modinteractive -f
```

Port dinleniyor mu kontrol et:

```bash
ss -tulpn | grep 8080
```

Pi IP adresini öğren:

```bash
hostname -I
```

Tarayıcıda aç:

```text
http://PI_IP_ADRESI:8080
```

### HDMI ekranda video görünmüyor

Grafik oturumun açık olduğundan emin ol.

DISPLAY değerini kontrol et:

```bash
echo $DISPLAY
```

Manuel mpv testi yap:

```bash
DISPLAY=:0 mpv --fs /opt/modInteractive/videos/selamlama.mp4
```

Bookworm/Wayland ortamında servis üzerinden görüntü alamazsan uygulamayı desktop autostart veya user-level systemd ile başlatmak gerekebilir.

## Geliştirme

```bash
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive

python3 -m venv --system-site-packages venv
source venv/bin/activate

pip install -r requirements.txt

python main.py --check
python main.py
```

## CI Kontrolleri

GitHub Actions şu kontrolleri yapar:

* Python syntax kontrolü
* Shell script syntax kontrolü
* Python dependency kurulumu
* Systemd service doğrulama
* Health check çalıştırma

## Üretim Kurulum Önerileri

* Raspberry Pi 5 için kaliteli güç adaptörü kullan
* HDMI ekranı kurulumdan önce test et
* İlk testte USB webcam kullan
* Video dosyasını düşük/orta bitrate ile encode et
* 1080p video kullanacaksan mpv ile manuel test yap
* Cafe ortamında motion sensitivity değerini ortam ışığına göre ayarla
* Kamera kadrajında sürekli hareket eden obje varsa sensitivity/min_area değerlerini yükselt
* Servis loglarını ilk gün takip et

## Roadmap

* YOLO ile insan algılama
* Çoklu video playlist
* Çalışma saatleri
* Video yükleme ekranı
* Admin panelden servis restart
* İstatistik toplama
* Uzaktan yönetim API'si
* Çoklu ekran desteği

## Lisans

WATAM - WeAreTheArtMakers.com
