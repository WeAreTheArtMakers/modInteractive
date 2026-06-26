# Video Files for modInteractive

Place your video files in this directory.

## Default Video

The application looks for `videos/selamlama.mp4` by default.
You can change the path in `config.json`:

```json
{
  "video": {
    "path": "videos/selamlama.mp4"
  }
}
```

## Supported Formats

The application uses `mpv` for playback, supporting most common formats:
- MP4 (H.264/H.265)
- AVI, MKV, MOV, WebM

## Notes

- Videos play in fullscreen mode by default
- One video plays per motion detection
- After playback, cooldown period starts before re-detection
- Video files are not tracked in git (see `.gitignore`)