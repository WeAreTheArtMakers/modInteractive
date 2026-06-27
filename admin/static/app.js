document.addEventListener("DOMContentLoaded", () => {
    bindTabs();
    bindForm();
    bindButtons();
    bindSensitivitySlider();

    loadConfig();
    loadStatus();
    loadLogs();

    window.setInterval(loadStatus, 8000);
});

function bindTabs() {
    document.querySelectorAll(".tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            const targetId = tab.dataset.tab;

            document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach((content) => content.classList.remove("active"));

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
}

function bindForm() {
    const form = document.getElementById("config-form");

    if (!form) {
        return;
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        saveConfig();
    });
}

function bindButtons() {
    const refreshStatus = document.getElementById("refresh-status");
    const refreshLogs = document.getElementById("refresh-logs");
    const testVideoButton = document.getElementById("test-video");
    const reloadConfigButton = document.getElementById("reload-config");

    if (refreshStatus) {
        refreshStatus.addEventListener("click", loadStatus);
    }

    if (refreshLogs) {
        refreshLogs.addEventListener("click", loadLogs);
    }

    if (testVideoButton) {
        testVideoButton.addEventListener("click", testVideo);
    }

    if (reloadConfigButton) {
        reloadConfigButton.addEventListener("click", async () => {
            await loadConfig();
            await loadStatus();
        });
    }
}

function bindSensitivitySlider() {
    const slider = document.getElementById("motion-sensitivity");
    const value = document.getElementById("motion-sensitivity-value");

    if (!slider || !value) {
        return;
    }

    slider.addEventListener("input", () => {
        value.textContent = slider.value;
    });
}

function showStatus(message, type = "info") {
    const element = document.getElementById("save-status");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.className = `status-msg ${type}`;

    window.setTimeout(() => {
        element.className = "status-msg";
    }, 6000);
}

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...options,
    });

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
}

async function loadConfig() {
    try {
        const config = await apiFetch("/api/config");

        setValue("trigger-source", getNested(config, "trigger.source", "pir"));

        setValue("camera-index", getNested(config, "camera.index", 0));
        setValue("camera-width", getNested(config, "camera.width", 640));
        setValue("camera-height", getNested(config, "camera.height", 480));
        setValue("camera-fps", getNested(config, "camera.fps", 15));

        setValue("pir-gpio-pin", getNested(config, "pir.gpio_pin", 17));
        setChecked("pir-active-high", getNested(config, "pir.active_high", true));
        setChecked("pir-pull-up", getNested(config, "pir.pull_up", false));
        setValue("pir-bounce-time", getNested(config, "pir.bounce_time_ms", 500));
        setValue("pir-settle-seconds", getNested(config, "pir.settle_seconds", 30));
        setValue("pir-poll-interval", getNested(config, "pir.poll_interval", 0.05));

        const sensitivity = getNested(config, "detection.motion_sensitivity", 500);
        setValue("motion-sensitivity", sensitivity);
        setText("motion-sensitivity-value", sensitivity);

        setValue("min-motion-area", getNested(config, "detection.min_motion_area", 1500));
        setValue("cooldown-seconds", getNested(config, "detection.cooldown_seconds", 10));
        setValue("frame-skip", getNested(config, "detection.frame_skip", 3));

        setValue("video-path", getNested(config, "video.path", "videos/selamlama.mp4"));
        setValue("video-volume", getNested(config, "video.volume", 90));
        setChecked("video-fullscreen", getNested(config, "video.fullscreen", true));

        updateHero(config);
        showStatus("Ayarlar yüklendi", "success");
    } catch (error) {
        showStatus(`Ayarlar yüklenemedi: ${error.message}`, "error");
    }
}

async function saveConfig() {
    const config = {
        system: {
            log_level: "INFO",
            project_name: "modInteractive",
            version: "1.1.0",
        },
        trigger: {
            source: readSelect("trigger-source", "pir", ["camera", "pir"]),
        },
        camera: {
            index: readCameraIndex("camera-index", 0),
            width: readInt("camera-width", 640, 160, 3840),
            height: readInt("camera-height", 480, 120, 2160),
            fps: readInt("camera-fps", 15, 1, 60),
            backend: "v4l2",
        },
        pir: {
            gpio_pin: readInt("pir-gpio-pin", 17, 0, 27),
            active_high: readChecked("pir-active-high", true),
            pull_up: readChecked("pir-pull-up", false),
            bounce_time_ms: readInt("pir-bounce-time", 500, 0, 5000),
            settle_seconds: readInt("pir-settle-seconds", 30, 0, 120),
            poll_interval: readFloat("pir-poll-interval", 0.05, 0.01, 5),
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

    try {
        const data = await apiFetch("/api/config/update", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(config),
        });

        if (data.status === "ok") {
            updateHero(config);
            showStatus("Ayarlar kaydedildi. Değişikliklerin tamamı için servisi restart et.", "success");
            await loadStatus();
        } else {
            showStatus(data.error || "Ayar kaydetme başarısız", "error");
        }
    } catch (error) {
        showStatus(`Kaydedilemedi: ${error.message}`, "error");
    }
}

async function loadStatus() {
    const container = document.getElementById("status-content");

    if (!container) {
        return;
    }

    try {
        const status = await apiFetch("/api/status");
        const source = status.trigger_source || "pir";
        const items = [
            {
                label: "Trigger",
                value: source === "pir" ? "PIR GPIO" : "Camera",
                fail: false,
            },
            {
                label: "PIR",
                value: status.pir_available
                    ? `GPIO ${status.pir_gpio_pin} • ${formatPirState(status.pir_state)}`
                    : source === "pir"
                        ? (status.pir_error || "Hazır değil")
                        : "Kullanılmıyor",
                fail: source === "pir" && !status.pir_available,
            },
            {
                label: "Video",
                value: status.video_exists
                    ? `Hazır • ${status.video_size_mb || "?"} MB`
                    : "Bulunamadı",
                fail: !status.video_exists,
            },
            {
                label: "mpv",
                value: status.mpv_available ? "Hazır" : "Eksik",
                fail: !status.mpv_available,
            },
            {
                label: "Camera",
                value: source === "camera"
                    ? (status.camera_available ? "Hazır" : "Bulunamadı")
                    : "Kullanılmıyor",
                fail: source === "camera" && !status.camera_available,
            },
            {
                label: "OpenCV",
                value: status.opencv_available
                    ? `Hazır ${status.opencv_version || ""}`
                    : source === "camera"
                        ? "Eksik"
                        : "PIR modunda gerekmez",
                fail: source === "camera" && !status.opencv_available,
            },
            {
                label: "Video Path",
                value: status.video_path || "N/A",
                fail: false,
            },
            {
                label: "Config",
                value: status.config_path || "N/A",
                fail: false,
            },
        ];

        container.innerHTML = items.map((item) => createStatusItem(item.label, item.value, item.fail)).join("");
    } catch (error) {
        container.innerHTML = createStatusItem("Hata", error.message, true);
    }
}

async function loadLogs() {
    const logContent = document.getElementById("log-content");
    const logContainer = document.getElementById("log-container");

    if (!logContent) {
        return;
    }

    try {
        const data = await apiFetch("/api/logs?limit=180");
        const logs = Array.isArray(data.logs) ? data.logs : [];

        logContent.textContent = logs.length > 0 ? logs.join("\n") : "Log bulunamadı.";

        if (logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    } catch (error) {
        logContent.textContent = `Log okunamadı: ${error.message}`;
    }
}

async function testVideo() {
    const button = document.getElementById("test-video");

    if (!button) {
        return;
    }

    const originalText = button.textContent;
    button.textContent = "Test ediliyor...";
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

        showStatus(data.message || "Video başlatıldı", "success");
    } catch (error) {
        showStatus(`Video testi başarısız: ${error.message}`, "error");
    } finally {
        window.setTimeout(() => {
            button.textContent = originalText || "Test Video";
            button.disabled = false;
        }, 1500);
    }
}

function createStatusItem(label, value, fail = false) {
    const className = fail ? "status-card fail" : "status-card ok";

    return `
        <div class="${className}">
            <span class="label">${escapeHtml(String(label))}</span>
            <span class="value">${escapeHtml(String(value))}</span>
        </div>
    `;
}

function updateHero(config) {
    setText("hero-source", String(getNested(config, "trigger.source", "pir")).toUpperCase());
    setText("hero-video", getNested(config, "video.path", "videos/selamlama.mp4"));
}

function formatPirState(value) {
    if (value === true) {
        return "HIGH";
    }

    if (value === false) {
        return "LOW";
    }

    if (value === "managed_by_application") {
        return "Uygulama yönetiyor";
    }

    if (value === null || typeof value === "undefined") {
        return "Bilinmiyor";
    }

    return String(value);
}

function getNested(object, path, fallback) {
    const parts = path.split(".");
    let value = object;

    for (const key of parts) {
        if (value && Object.prototype.hasOwnProperty.call(value, key)) {
            value = value[key];
        } else {
            return fallback;
        }
    }

    return value;
}

function setValue(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.value = value;
    }
}

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function setChecked(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.checked = Boolean(value);
    }
}

function readString(id, fallback) {
    const element = document.getElementById(id);

    if (!element) {
        return fallback;
    }

    const value = String(element.value || "").trim();
    return value || fallback;
}

function readSelect(id, fallback, allowed) {
    const value = readString(id, fallback).toLowerCase();

    if (Array.isArray(allowed) && allowed.includes(value)) {
        return value;
    }

    return fallback;
}

function readCameraIndex(id, fallback) {
    const value = readString(id, String(fallback));

    if (/^\d+$/.test(value)) {
        return Number.parseInt(value, 10);
    }

    return value;
}

function readChecked(id, fallback) {
    const element = document.getElementById(id);

    if (!element) {
        return fallback;
    }

    return Boolean(element.checked);
}

function normalizeNumeric(value) {
    return String(value || "").trim().replace(",", ".");
}

function readInt(id, fallback, minimum, maximum) {
    const element = document.getElementById(id);

    if (!element) {
        return fallback;
    }

    let value = Number.parseInt(normalizeNumeric(element.value), 10);

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
}

function readFloat(id, fallback, minimum, maximum) {
    const element = document.getElementById(id);

    if (!element) {
        return fallback;
    }

    let value = Number.parseFloat(normalizeNumeric(element.value));

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
}

function escapeHtml(value) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
