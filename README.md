# modInteractive - Motion Triggered Video Display for Raspberry Pi

**Raspberry Pi 5** üzerinde çalışan, kamera hareket algılayınca **HDMI ekranda tam ekran video oynatan** cafe/mağaza ekran sistemi.

HDMI ekran veya TV; touchscreen gerekli değildir.

## Özellikler

- **Hareket Algılama**: OpenCV MOG2 background subtraction + frame differencing
- **Video Oynatma**: mpv ile tam ekran, donanım hızlandırmalı
- **Cooldown Sistemi**: Video sonrası tekrar tetiklenmeyi önler
- **Çift Loglama**: Konsol + rotasyonlu dosya (`logs/modinteractive.log`)
- **Sistem Sağlık Kontrolü**: `python main.py --check` ile tüm bileşenleri test eder
- **Web Admin Paneli**: Telefondan/tabletten ayar yapma (opsiyonel, port 8080)
- **Systemd Servisi**: Otomatik başlatma ve restart
- **Idempotent Kurulum**: `install.sh` defalarca çalıştırılabilir

## Donanım Gereksinimleri

- Raspberry Pi 5 (8GB önerilen)
- Raspberry Pi Camera Module veya USB webcam
- HDMI ekran veya TV
- MicroSD kart (32GB+)

## Hızlı Kurulum

```bash
# Repo'yu klonla
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive

# Video dosyanı ekle (kendi videonla değiştir)
cp /path/to/greeting.mp4 videos/selamlama.mp4

# Kurulumu çalıştır
sudo ./install.sh

# Servisi başlat
sudo systemctl start modinteractive

# Durumu kontrol et
sudo systemctl status modinteractive
```

## Manuel Kurulum

```bash
# 1. Sistem bağımlılıkları
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-opencv python3-numpy mpv v4l-utils

# 2. Virtual environment (system-site-packages ile)
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 3. Python bağımlılıkları
pip install -r requirements.txt

# 4. Video dosyası ekle
cp /path/to/greeting.mp4 videos/selamlama.mp4

# 5. Test et
python main.py

# 6. Systemd servisi kur (opsiyonel)
sudo cp systemd/modinteractive.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable modinteractive
sudo systemctl start modinteractive
```

## Kullanım

```bash
# Normal çalıştırma
python main.py

# Sistem kontrolü
python main.py --check

# Özel config ile
python main.py --config /path/to/config.json

# Servis yönetimi
sudo systemctl start modinteractive
sudo systemctl stop modinteractive
sudo systemctl status modinteractive
journalctl -u modinteractive -f
```

## Yapılandırma

`config.json` dosyasını düzenleyerek ayarları değiştirebilirsin:

```json
{
  "system": {
    "log_level": "INFO"
  },
  "camera": {
    "index": 0,
    "width": 640,
    "height": 480,
    "fps": 15
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

### Açıklamalar

| Anahtar | Varsayılan | Açıklama |
|---------|-----------|----------|
| `camera.index` | `0` | Kamera cihaz indeksi |
| `camera.width` | `640` | Kamera çözünürlük genişlik |
| `camera.height` | `480` | Kamera çözünürlük yükseklik |
| `camera.fps` | `15` | Kamera FPS |
| `detection.motion_sensitivity` | `500` | Hareket hassasiyeti (düşük = daha hassas) |
| `detection.min_motion_area` | `1500` | Minimum hareket alanı (piksel) |
| `detection.cooldown_seconds` | `10` | Video sonrası bekleme süresi |
| `video.path` | `videos/selamlama.mp4` | Video dosyası yolu |
| `video.fullscreen` | `true` | Tam ekran oynatma |
| `video.volume` | `90` | Ses seviyesi (0-100) |

## Admin Paneli

Web tabanlı admin paneli `http://raspberrypi.local:8080` adresinde çalışır.

Özellikler:
- Video yolu değiştirme
- Kamera indeks ayarlama
- Hareket hassasiyeti ayarlama
- Cooldown süresi ayarlama
- Sistem durumu görüntüleme
- Log görüntüleme

Admin panel **opsiyoneldir**; panel bozulsa bile ana video sistemi çalışmaya devam eder.

## Proje Yapısı

```
modInteractive/
├── main.py                  # Giriş noktası
├── app.py                   # Uygulama kontrolcüsü
├── config.json              # Yapılandırma
├── requirements.txt         # Python bağımlılıkları
├── install.sh               # Kurulum scripti
├── uninstall.sh             # Kaldırma scripti
├── README.md
├── core/
│   ├── __init__.py
│   ├── config.py            # Config yönetimi
│   ├── camera.py            # Kamera işlemleri
│   ├── detector.py          # Hareket algılama
│   ├── player.py            # Video oynatma (mpv)
│   ├── logger.py            # Loglama
│   └── healthcheck.py       # Sistem kontrolü
├── admin/
│   ├── server.py            # Flask admin panel
│   ├── templates/
│   │   └── index.html       # Admin UI
│   └── static/
│       ├── style.css        # Koyu tema CSS
│       └── app.js           # Admin JS
├── systemd/
│   └── modinteractive.service
├── videos/
│   ├── .gitkeep
│   └── selamlama.mp4        # Senin videon (git'te takip edilmez)
└── logs/
    └── .gitkeep
```

## Sorun Giderme

### Kamera açılmıyor

```bash
# Kamerayı kontrol et
ls -la /dev/video*
v4l2-ctl --list-devices

# Kullanıcıyı video grubuna ekle
sudo usermod -a -G video $USER

# Raspberry Pi'de kamerayı etkinleştir
sudo raspi-config  # → Interface Options → Camera → Enable

# Yeniden başlat
sudo reboot
```

### Video oynatmıyor

```bash
# Video dosyası var mı?
ls -la /opt/modInteractive/videos/

# mpv kurulu mu?
mpv --version

# Elle test et
mpv --fs /opt/modInteractive/videos/selamlama.mp4
```

### Servis başlamıyor

```bash
# Servis durumu
sudo systemctl status modinteractive

# Logları görüntüle
journalctl -u modinteractive -f

# Elle test et
sudo -u pi /opt/modInteractive/venv/bin/python /opt/modInteractive/main.py --check
```

### Permission hatası

```bash
sudo chown -R pi:pi /opt/modInteractive
sudo usermod -a -G video pi
```

## Geliştirme

```bash
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Lisans

MIT License

## Gelecek Planları

- [ ] YOLO ile insan algılama desteği
- [ ] Çoklu video playlist
- [ ] Ses çıkış desteği
- [ ] İstatistik toplama
- [ ] Uzaktan yönetim API'si