# Video Files for modInteractive

Place your video files in this directory.

## Required Video

By default, the application looks for `selamlama.mp4` in this directory.
You can change the video path in `config.json`:

```json
{
  "video_path": "videos/selamlama.mp4"
}
```

## Supported Formats

The application uses `mpv` for playback, which supports most common video formats:
- MP4 (H.264/H.265)
- AVI
- MKV
- MOV
- WebM

## Notes

- Videos play in fullscreen mode by default (configurable in `config.json`)
- The video plays once per detection, then returns to detection mode
- Add your own greeting/promotional videos here
- Video files are not tracked in git (see `.gitignore`)