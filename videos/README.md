# Video Files

Bu klasöre modInteractive sisteminin oynatacağı video dosyalarını koy.

Varsayılan video dosyası:

`videos/selamlama.mp4`

## Varsayılan Video

Uygulama varsayılan olarak şu dosyayı arar:

`videos/selamlama.mp4`

Farklı bir video yolu kullanmak için `config.json` içinde şu alanı değiştir:

`video.path`

Örnek değer:

`videos/selamlama.mp4`

## Desteklenen Formatlar

Video oynatma için `mpv` kullanılır. Genellikle şu formatlar desteklenir:

* MP4
* MOV
* MKV
* AVI
* WebM

Önerilen format:

* `.mp4`
* H.264 video codec
* AAC audio codec
* 1080p veya daha düşük çözünürlük

## Kullanım

Kendi videonu varsayılan video olarak kullanmak için:

`selamlama.mp4`

adıyla bu klasöre koy.

Kurulumdan önce:

`videos/selamlama.mp4`

Kurulumdan sonra Raspberry Pi üzerinde:

`/opt/modInteractive/videos/selamlama.mp4`

## Notlar

* Video hareket algılanınca bir kez oynatılır.
* Video oynarken yeni hareket tetiklemesi alınmaz.
* Video bittikten sonra cooldown süresi başlar.
* Cooldown bitince kamera tekrar hareket algılamaya devam eder.
* Video dosyaları Git deposunda takip edilmez.
* Bu klasörde sadece `.gitkeep` ve bu README dosyası takip edilir.
