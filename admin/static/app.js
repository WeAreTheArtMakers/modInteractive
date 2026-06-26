document.addEventListener("DOMContentLoaded", () => {
bindTabs();
bindForm();
bindButtons();
bindSensitivitySlider();

```
loadConfig();
loadStatus();
loadLogs();
```

});

function bindTabs() {
document.querySelectorAll(".tab").forEach((tab) => {
tab.addEventListener("click", () => {
const targetId = tab.dataset.tab;

```
        document.querySelectorAll(".tab").forEach((item) => {
            item.classList.remove("active");
        });

        document.querySelectorAll(".tab-content").forEach((content) => {
            content.classList.remove("active");
        });

        tab.classList.add("active");

        const target = document.getElementById(targetId);
        if (target) {
            target.classList.add("active");
        }

        if (targetId === "status") {
            loadStatus();
        }

        if (targetId === "logs") {
            loadLogs();
        }
    });
});
```

}

function bindForm() {
const form = document.getElementById("config-form");

```
if (!form) {
    return;
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    saveConfig();
});
```

}

function bindButtons() {
const refreshStatus = document.getElementById("refresh-status");
const refreshLogs = document.getElementById("refresh-logs");
const testVideoButton = document.getElementById("test-video");

```
if (refreshStatus) {
    refreshStatus.addEventListener("click", loadStatus);
}

if (refreshLogs) {
    refreshLogs.addEventListener("click", loadLogs);
}

if (testVideoButton) {
    testVideoButton.addEventListener("click", testVideo);
}
```

}

function bindSensitivitySlider() {
const slider = document.getElementById("motion-sensitivity");
const value = document.getElementById("motion-sensitivity-value");

```
if (!slider || !value) {
    return;
}

slider.addEventListener("input", () => {
    value.textContent = slider.value;
});
```

}

function showStatus(message, type = "info") {
const element = document.getElementById("save-status");

```
if (!element) {
    return;
}

element.textContent = message;
element.className = `status-msg ${type}`;

window.setTimeout(() => {
    element.className = "status-msg";
}, 5000);
```

}

async function apiFetch(url, options = {}) {
const response = await fetch(url, {
cache: "no-store",
...options,
});

```
let data = {};

try {
    data = await response.json();
} catch (_error) {
    data = {};
}

if (!response.ok) {
    const message = data.error || `${response.status} ${response.statusText}`;
    throw new Error(message);
}

return data;
```

}

async function loadConfig() {
try {
const config = await apiFetch("/api/config");

```
    setValue("camera-index", getNested(config, "camera.index", 0));
    setValue("camera-width", getNested(config, "camera.width", 640));
    setValue("camera-height", getNested(config, "camera.height", 480));
    setValue("camera-fps", getNested(config, "camera.fps", 15));

    const sensitivity = getNested(config, "detection.motion_sensitivity", 500);
    setValue("motion-sensitivity", sensitivity);
    setText("motion-sensitivity-value", sensitivity);

    setValue("min-motion-area", getNested(config, "detection.min_motion_area", 1500));
    setValue("cooldown-seconds", getNested(config, "detection.cooldown_seconds", 10));
    setValue("frame-skip", getNested(config, "detection.frame_skip", 3));

    setValue("video-path", getNested(config, "video.path", "videos/selamlama.mp4"));
    setValue("video-volume", getNested(config, "video.volume", 90));
    setChecked("video-fullscreen", getNested(config, "video.fullscreen", true));

    showStatus("Configuration loaded", "success");
} catch (error) {
    showStatus(`Failed to load config: ${error.message}`, "error");
}
```

}

async function saveConfig() {
const config = {
system: {
log_level: "INFO",
project_name: "modInteractive",
version: "1.0.0",
},
camera: {
index: readInt("camera-index", 0, 0, 20),
width: readInt("camera-width", 640, 160, 3840),
height: readInt("camera-height", 480, 120, 2160),
fps: readInt("camera-fps", 15, 1, 60),
backend: "v4l2",
},
detection: {
enabled: true,
mode: "motion",
motion_sensitivity: readInt("motion-sensitivity", 500, 1, 100000),
min_motion_area: readInt("min-motion-area", 1500, 1, 100000),
frame_skip: readInt("frame-skip", 3, 1, 30),
warmup_seconds: 2,
cooldown_seconds: readInt("cooldown-seconds", 10, 0, 600),
},
video: {
path: readString("video-path", "videos/selamlama.mp4"),
fullscreen: readChecked("video-fullscreen", true),
volume: readInt("video-volume", 90, 0, 100),
player: "mpv",
},
admin: {
enabled: true,
host: "0.0.0.0",
port: 8080,
},
};

```
try {
    const data = await apiFetch("/api/config/update", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });

    if (data.status === "ok") {
        showStatus("Configuration saved successfully", "success");
        await loadStatus();
    } else {
        showStatus(data.error || "Configuration save failed", "error");
    }
} catch (error) {
    showStatus(`Failed to save: ${error.message}`, "error");
}
```

}

async function loadStatus() {
const container = document.getElementById("status-content");

```
if (!container) {
    return;
}

container.innerHTML = createStatusItem("Loading", "Please wait", false);

try {
    const status = await apiFetch("/api/status");

    const items = [
        {
            label: "OpenCV",
            value: status.opencv_available
                ? `Available (${status.opencv_version || "unknown"})`
                : "Not available",
            fail: !status.opencv_available,
        },
        {
            label: "Camera",
            value: status.camera_available ? "Available" : "Not available",
            fail: !status.camera_available,
        },
        {
            label: "Camera Resolution",
            value: status.camera_resolution || "N/A",
            fail: false,
        },
        {
            label: "Video File",
            value: status.video_exists ? "Found" : "Not found",
            fail: !status.video_exists,
        },
        {
            label: "Video Path",
            value: status.video_path || "N/A",
            fail: false,
        },
        {
            label: "mpv Player",
            value: status.mpv_available ? `Available (${status.mpv_path || "mpv"})` : "Not available",
            fail: !status.mpv_available,
        },
        {
            label: "Config Path",
            value: status.config_path || "N/A",
            fail: false,
        },
    ];

    container.innerHTML = items
        .map((item) => createStatusItem(item.label, item.value, item.fail))
        .join("");
} catch (error) {
    container.innerHTML = createStatusItem("Error", error.message, true);
}
```

}

async function loadLogs() {
const logContent = document.getElementById("log-content");
const logContainer = document.getElementById("log-container");

```
if (!logContent) {
    return;
}

try {
    const data = await apiFetch("/api/logs?limit=150");
    const logs = Array.isArray(data.logs) ? data.logs : [];

    if (logs.length > 0) {
        logContent.textContent = logs.join("\n");
    } else {
        logContent.textContent = "No log entries found.";
    }

    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
} catch (error) {
    logContent.textContent = `Error loading logs: ${error.message}`;
}
```

}

async function testVideo() {
const button = document.getElementById("test-video");

```
if (!button) {
    return;
}

const originalText = button.textContent;
button.textContent = "Testing...";
button.disabled = true;

try {
    const data = await apiFetch("/api/test-video", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            path: readString("video-path", "videos/selamlama.mp4"),
        }),
    });

    showStatus(data.message || "Video playback started", "success");
} catch (error) {
    showStatus(`Test failed: ${error.message}`, "error");
} finally {
    window.setTimeout(() => {
        button.textContent = originalText || "Test Video";
        button.disabled = false;
    }, 1500);
}
```

}

function createStatusItem(label, value, fail = false) {
const safeLabel = escapeHtml(String(label));
const safeValue = escapeHtml(String(value));

```
return `
    <div class="status-item">
        <span class="label">${safeLabel}</span>
        <span class="value ${fail ? "fail" : "ok"}">${safeValue}</span>
    </div>
`;
```

}

function getNested(object, path, fallback) {
return path.split(".").reduce((value, key) => {
if (value && Object.prototype.hasOwnProperty.call(value, key)) {
return value[key];
}

```
    return fallback;
}, object);
```

}

function setValue(id, value) {
const element = document.getElementById(id);

```
if (element) {
    element.value = value;
}
```

}

function setText(id, value) {
const element = document.getElementById(id);

```
if (element) {
    element.textContent = value;
}
```

}

function setChecked(id, value) {
const element = document.getElementById(id);

```
if (element) {
    element.checked = Boolean(value);
}
```

}

function readString(id, fallback) {
const element = document.getElementById(id);

```
if (!element) {
    return fallback;
}

const value = String(element.value || "").trim();
return value || fallback;
```

}

function readChecked(id, fallback) {
const element = document.getElementById(id);

```
if (!element) {
    return fallback;
}

return Boolean(element.checked);
```

}

function readInt(id, fallback, minimum, maximum) {
const element = document.getElementById(id);

```
if (!element) {
    return fallback;
}

let value = Number.parseInt(element.value, 10);

if (Number.isNaN(value)) {
    value = fallback;
}

if (typeof minimum === "number" && value < minimum) {
    value = minimum;
}

if (typeof maximum === "number" && value > maximum) {
    value = maximum;
}

return value;
```

}

function escapeHtml(value) {
return value
.replaceAll("&", "&")
.replaceAll("<", "<")
.replaceAll(">", ">")
.replaceAll('"', """)
.replaceAll("'", "'");
}
