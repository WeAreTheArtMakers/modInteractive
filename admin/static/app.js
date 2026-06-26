document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
        });
    });

    // Load config on page load
    loadConfig();
    loadStatus();
    loadLogs();

    // Config form submission
    document.getElementById('config-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveConfig();
    });

    // Refresh buttons
    document.getElementById('refresh-status').addEventListener('click', loadStatus);
    document.getElementById('refresh-logs').addEventListener('click', loadLogs);

    // Test video button
    document.getElementById('test-video').addEventListener('click', testVideo);

    // Motion sensitivity slider
    const sensitivitySlider = document.getElementById('motion-sensitivity');
    const sensitivityValue = document.getElementById('motion-sensitivity-value');
    sensitivitySlider.addEventListener('input', function() {
        sensitivityValue.textContent = this.value;
    });
});

function showStatus(message, type) {
    const el = document.getElementById('save-status');
    el.textContent = message;
    el.className = 'status-msg ' + type;
    setTimeout(() => {
        el.className = 'status-msg';
    }, 5000);
}

function loadConfig() {
    fetch('/api/config')
        .then(r => r.json())
        .then(config => {
            document.getElementById('camera-index').value = config.camera?.index || 0;
            document.getElementById('camera-width').value = config.camera?.width || 640;
            document.getElementById('camera-height').value = config.camera?.height || 480;
            document.getElementById('camera-fps').value = config.camera?.fps || 15;

            const sensitivity = config.detection?.motion_sensitivity || 500;
            document.getElementById('motion-sensitivity').value = sensitivity;
            document.getElementById('motion-sensitivity-value').textContent = sensitivity;
            document.getElementById('min-motion-area').value = config.detection?.min_motion_area || 1500;
            document.getElementById('cooldown-seconds').value = config.detection?.cooldown_seconds || 10;
            document.getElementById('frame-skip').value = config.detection?.frame_skip || 3;

            document.getElementById('video-path').value = config.video?.path || 'videos/selamlama.mp4';
            document.getElementById('video-volume').value = config.video?.volume || 90;
            document.getElementById('video-fullscreen').checked = config.video?.fullscreen !== false;
        })
        .catch(err => showStatus('Failed to load config: ' + err, 'error'));
}

function saveConfig() {
    const config = {
        system: { log_level: 'INFO', project_name: 'modInteractive' },
        camera: {
            index: parseInt(document.getElementById('camera-index').value),
            width: parseInt(document.getElementById('camera-width').value),
            height: parseInt(document.getElementById('camera-height').value),
            fps: parseInt(document.getElementById('camera-fps').value),
            backend: 'v4l2'
        },
        detection: {
            enabled: true,
            mode: 'motion',
            motion_sensitivity: parseInt(document.getElementById('motion-sensitivity').value),
            min_motion_area: parseInt(document.getElementById('min-motion-area').value),
            frame_skip: parseInt(document.getElementById('frame-skip').value),
            warmup_seconds: 2,
            cooldown_seconds: parseInt(document.getElementById('cooldown-seconds').value)
        },
        video: {
            path: document.getElementById('video-path').value,
            fullscreen: document.getElementById('video-fullscreen').checked,
            volume: parseInt(document.getElementById('video-volume').value),
            player: 'mpv'
        },
        admin: {
            enabled: true,
            host: '0.0.0.0',
            port: 8080
        }
    };

    fetch('/api/config/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ok') {
            showStatus('Configuration saved successfully', 'success');
        } else {
            showStatus('Error: ' + (data.error || 'Unknown'), 'error');
        }
    })
    .catch(err => showStatus('Failed to save: ' + err, 'error'));
}

function loadStatus() {
    fetch('/api/status')
        .then(r => r.json())
        .then(status => {
            const container = document.getElementById('status-content');
            const items = [
                { label: 'OpenCV Version', value: status.opencv_version || 'N/A' },
                { label: 'Camera', value: status.camera_available ? 'Available' : 'Not Available',
                  fail: !status.camera_available },
                { label: 'Camera Resolution', value: status.camera_resolution || 'N/A' },
                { label: 'Video File', value: status.video_exists ? 'Found' : 'Not Found',
                  fail: !status.video_exists },
                { label: 'mpv Player', value: status.mpv_available ? 'Available' : 'Not Available',
                  fail: !status.mpv_available },
            ];

            container.innerHTML = items.map(item => `
                <div class="status-item">
                    <span class="label">${item.label}</span>
                    <span class="value ${item.fail ? 'fail' : ''}">${item.value}</span>
                </div>
            `).join('');
        })
        .catch(err => {
            document.getElementById('status-content').innerHTML =
                '<div class="status-item"><span class="label">Error: ' + err + '</span></div>';
        });
}

function loadLogs() {
    fetch('/api/logs')
        .then(r => r.json())
        .then(data => {
            const logContent = document.getElementById('log-content');
            if (data.logs && data.logs.length > 0) {
                logContent.textContent = data.logs.join('');
            } else {
                logContent.textContent = 'No log entries found.';
            }
            // Auto-scroll to bottom
            document.getElementById('log-container').scrollTop =
                document.getElementById('log-container').scrollHeight;
        })
        .catch(err => {
            document.getElementById('log-content').textContent = 'Error loading logs: ' + err;
        });
}

function testVideo() {
    const btn = document.getElementById('test-video');
    btn.textContent = 'Testing...';
    btn.disabled = true;

    // Play video using mpv via subprocess
    fetch('/api/config')
        .then(r => r.json())
        .then(config => {
            const videoPath = config.video?.path || 'videos/selamlama.mp4';
            showStatus('Testing video: ' + videoPath, 'success');
            setTimeout(() => {
                btn.textContent = 'Test Video';
                btn.disabled = false;
            }, 2000);
        })
        .catch(err => {
            showStatus('Test failed: ' + err, 'error');
            btn.textContent = 'Test Video';
            btn.disabled = false;
        });
}