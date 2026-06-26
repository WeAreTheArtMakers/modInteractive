# modInteractive - Temiz Kod Yeniden Yazma Planı

## Yapılacaklar

- [x] Mevcut kodu analiz et
- [x] **main.py** - Temiz, basit ana giriş noktası
- [x] **app.py** - Basitleştirilmiş uygulama kontrolcüsü
- [x] **core/__init__.py** - Core paket tanımı
- [x] **core/config.py** - Config yükleme/saklama (JSON tabanlı, basit)
- [x] **core/logger.py** - Loglama sistemi (console + file)
- [x] **core/detector.py** - Hareket/insan algılama (OpenCV + isteğe bağlı YOLO)
- [x] **core/player.py** - Video oynatma (mpv ile)
- [x] **config.json** - Temiz yapılandırma
- [x] **requirements.txt** - Minimal bağımlılıklar
- [x] **install.sh** - Sağlam, idempotent kurulum scripti
- [x] **systemd/modinteractive.service** - Düzgün systemd servisi
- [x] **README.md** - Kapsamlı dokümantasyon
- [x] **videos/.gitkeep** + **videos/README.md** - Video klasörü
- [x] **logs/.gitkeep** - Log klasörü
- [x] Eski/artık dosyaları temizle
- [x] Python compile testi (Tüm dosyalar OK)
- [x] Shell syntax testi (install.sh OK)
- [x] pip install testi (requirements.txt OK)
- [x] --check modu testi (Çalışıyor)
- [ ] GitHub'a yükle