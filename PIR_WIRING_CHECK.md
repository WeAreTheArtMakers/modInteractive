# Raspberry Pi 5 PIR Wiring Check

Bu proje artık varsayılan olarak PIR sensör ile başlar. Kamera opsiyoneldir.

## Varsayılan pin

Kod varsayılan olarak BCM GPIO 17 kullanır.

- PIR OUT / SIGNAL -> BCM GPIO 17
- BCM GPIO 17 = fiziksel pin 11
- `config.json` içinde: `"pir": { "gpio_pin": 17 }`

## Güvenli bağlantı

PIR sensör üzerinde genelde 3 pin olur:

- VCC
- OUT / SIGNAL
- GND

Raspberry Pi tarafı:

- VCC -> 5V pin, fiziksel pin 2 veya 4
- GND -> GND pin, örnek fiziksel pin 6, 9, 14, 20, 25, 30, 34 veya 39
- OUT -> BCM GPIO 17, fiziksel pin 11

Önemli: Raspberry Pi GPIO girişleri 3.3V seviyesindedir. PIR OUT pini 5V çıkış veriyorsa doğrudan GPIO'ya bağlama. Önce multimetre ile ölç veya seviye düşürücü/direnç bölücü kullan.

## Fotoğraftaki bağlantı hakkında

Fotoğrafta kablolar GPIO header tarafına takılmış görünüyor, fakat açı ve kablo renkleri yüzünden hangi fiziksel pinlere takıldığını kesin doğrulamak mümkün değil.

Kesin doğrulama için Pi üzerinde şu komutu çalıştır:

```bash
pinout
```

veya header üzerinden fiziksel pinleri tek tek say.

Kodun beklediği bağlantı:

```text
VCC  -> 5V
GND  -> GND
OUT  -> GPIO17 / physical pin 11
```

Eğer OUT farklı GPIO pinindeyse `config.json` içinden `pir.gpio_pin` değerini değiştir.

## Hızlı PIR testi

Kurulumdan sonra:

```bash
cd /opt/modInteractive
/opt/modInteractive/venv/bin/python tools/test_pir.py --pin 17
```

Hareket görünce terminalde `MOTION` yazmalıdır.

## Uygulamayı PIR ile çalıştırma

Varsayılan config artık PIR modundadır:

```json
{
  "trigger": {
    "source": "pir"
  }
}
```

Servisi yeniden başlat:

```bash
sudo systemctl restart modinteractive
journalctl -u modinteractive -f
```

## Kamera ile çalıştırma

Kamera bağlanırsa admin panelden veya config dosyasından source değerini değiştir:

```json
{
  "trigger": {
    "source": "camera"
  }
}
```

Tek seferlik kamera testi:

```bash
/opt/modInteractive/venv/bin/python main.py --source camera --check
/opt/modInteractive/venv/bin/python main.py --source camera
```
