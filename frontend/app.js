const API_BASE = '/api';
const VIDEO_GRID = document.getElementById('video-grid');
const PTZ_CONTROLS = document.getElementById('ptz-controls');
const SELECTED_CAM_NAME = document.getElementById('selected-cam-name');
const MODAL = document.getElementById('add-camera-modal');
const PRESET_SELECT = document.getElementById('preset-select');

let selectedCamId = null;
let cameras = [];
let hlsInstances = {}; // Map camId -> hls instance

// --- Initialization ---
async function init() {
    await fetchCameras();
    setupEventListeners();
}

// --- API Calls ---
async function fetchCameras() {
    try {
        const res = await fetch(`${API_BASE}/cameras`);
        cameras = await res.json();
        renderGrid();
    } catch (e) {
        console.error("Failed to fetch cameras", e);
    }
}

async function addCamera(formData) {
    try {
        // Construct Payload matching new Schema
        const payload = {
            id: formData.id || 'cam_' + Math.floor(Math.random() * 10000),
            name: formData.name,
            ip: formData.ip,
            onvif_port: parseInt(formData.onvif_port),
            username: formData.username,
            password: formData.password,
            control_protocol: 'onvif', // Default for now
            preview: {
                type: formData.video_source_type, // 'ndi' or 'rtsp'
                ndi_source: formData.ndi_source_name || null,
                rtsp_url: formData.rtsp_url || null
            }
        };

        const res = await fetch(`${API_BASE}/cameras`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('Add failed');

        closeModal();
        fetchCameras();
    } catch (e) {
        console.error(e);
        alert("Failed to add camera");
    }
}

async function ptzAction(action, params = {}) {
    if (!selectedCamId) return;
    try {
        await fetch(`${API_BASE}/cameras/${selectedCamId}/ptz`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, ...params })
        });
    } catch (e) {
        console.error("PTZ failed", e);
    }
}

async function fetchPresets(camId) {
    try {
        const res = await fetch(`${API_BASE}/cameras/${camId}/presets`);
        const presets = await res.json();
        renderPresets(presets);
    } catch (e) {
        console.error("Failed to fetch presets", e);
        renderPresets([]);
    }
}

async function scanNDI() {
    const btn = document.getElementById('scan-ndi-btn');
    const select = document.getElementById('ndi-source-select');
    btn.innerText = "Scanning...";
    try {
        const res = await fetch(`${API_BASE}/ndi/sources`); // New Endpoint
        const sources = await res.json();
        select.innerHTML = '<option value="">Select NDI Source...</option>';
        sources.forEach(src => {
            const opt = document.createElement('option');
            opt.value = src;
            opt.innerText = src;
            select.appendChild(opt);
        });
        if (sources.length === 0) {
            const opt = document.createElement('option');
            opt.innerText = "No sources found";
            select.appendChild(opt);
        }
    } catch (e) {
        console.error("NDI Scan error", e);
        alert("Failed to scan NDI sources");
    } finally {
        btn.innerText = "Scan";
    }
}

// --- Rendering ---
function renderGrid() {
    VIDEO_GRID.innerHTML = '';
    if (cameras.length === 0) {
        VIDEO_GRID.innerHTML = '<div class="empty-state">No Cameras Configured</div>';
        return;
    }

    cameras.forEach(cam => {
        const cell = document.createElement('div');
        cell.className = 'video-cell';
        cell.dataset.id = cam.id;
        cell.onclick = () => selectCamera(cam);

        const label = document.createElement('div');
        label.className = 'cam-label';
        label.innerText = cam.name;

        // Player Logic
        let playerEl;
        const url = cam.stream_url;

        if (!url) {
            // Offline
            const offline = document.createElement('div');
            offline.className = "offline-msg";
            offline.innerText = "Offline";
            offline.style.cssText = "display:flex; justify-content:center; align-items:center; width:100%; height:100%; color:#6b7280; font-size:1.2em;";
            playerEl = offline;
        } else if (url.includes('mjpeg')) {
            // MJPEG
            playerEl = document.createElement('img');
            playerEl.className = 'video-player';
            playerEl.src = url;
            playerEl.style.objectFit = 'contain';
        } else {
            // HLS / RTSP
            playerEl = document.createElement('video');
            playerEl.className = 'video-player';
            playerEl.muted = true;
            playerEl.autoplay = true;
            playerEl.playsInline = true;

            if (Hls.isSupported() && url.includes('.m3u8')) {
                const hls = new Hls({ lowLatencyMode: true });
                hls.loadSource(url);
                hls.attachMedia(playerEl);
                hls.on(Hls.Events.MANIFEST_PARSED, () => playerEl.play().catch(e => console.log("Autoplay blocked", e)));
                hlsInstances[cam.id] = hls;
            } else if (playerEl.canPlayType('application/vnd.apple.mpegurl')) {
                playerEl.src = url;
            }
        }

        cell.appendChild(playerEl);
        cell.appendChild(label);
        VIDEO_GRID.appendChild(cell);
    });

    if (selectedCamId && cameras.find(c => c.id === selectedCamId)) {
        highlightCamera(selectedCamId);
    } else {
        selectedCamId = null;
        updateControlsUI();
    }
}

function selectCamera(cam) {
    selectedCamId = cam.id;
    SELECTED_CAM_NAME.innerText = cam.name;
    highlightCamera(cam.id);
    updateControlsUI();
    fetchPresets(cam.id);
}

function highlightCamera(id) {
    document.querySelectorAll('.video-cell').forEach(el => {
        el.classList.remove('selected');
        if (el.dataset.id === id) el.classList.add('selected');
    });
}

function renderPresets(presets) {
    PRESET_SELECT.innerHTML = '<option value="">Select Preset...</option>';
    if (!presets) return;
    presets.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.innerText = p.name;
        PRESET_SELECT.appendChild(opt);
    });
}

function updateControlsUI() {
    if (selectedCamId) {
        PTZ_CONTROLS.style.opacity = '1';
        PTZ_CONTROLS.style.pointerEvents = 'auto';
    } else {
        PTZ_CONTROLS.style.opacity = '0.5';
        PTZ_CONTROLS.style.pointerEvents = 'none';
        SELECTED_CAM_NAME.innerText = "Select a Camera";
    }
}

// --- Event Listeners ---
function setupEventListeners() {
    document.getElementById('add-camera-btn').onclick = () => MODAL.style.display = 'flex';
    document.getElementById('cancel-add-btn').onclick = closeModal;

    // Scan NDI
    document.getElementById('scan-ndi-btn').onclick = scanNDI;

    // Toggle fields based on type
    const sourceTypeSelect = document.getElementById('source-type-select');
    if (sourceTypeSelect) {
        sourceTypeSelect.onchange = (e) => {
            const type = e.target.value;
            if (type === 'ndi') {
                document.getElementById('rtsp-fields').style.display = 'none';
                document.getElementById('ndi-fields').style.display = 'block';
            } else {
                document.getElementById('rtsp-fields').style.display = 'block';
                document.getElementById('ndi-fields').style.display = 'none';
            }
        };
    }

    document.getElementById('add-camera-form').onsubmit = (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const data = Object.fromEntries(fd.entries());
        addCamera(data);
    };

    // PTZ Controls
    document.querySelectorAll('.ptz-btn').forEach(btn => {
        const action = btn.dataset.action;
        if (action === 'stop') {
            btn.onclick = () => ptzAction('stop');
            return;
        }
        const pan = parseFloat(btn.dataset.pan || 0);
        const tilt = parseFloat(btn.dataset.tilt || 0);

        const startMove = () => {
            const speed = parseFloat(document.getElementById('speed-slider').value);
            ptzAction('move', { pan, tilt, speed });
        };
        const stopMove = () => ptzAction('stop');

        btn.onmousedown = startMove;
        btn.onmouseup = stopMove;
        btn.onmouseleave = stopMove;
    });

    document.querySelectorAll('.ptz-zoom-btn').forEach(btn => {
        const zoom = parseFloat(btn.dataset.zoom || 0);
        const startZoom = () => {
            const speed = parseFloat(document.getElementById('speed-slider').value);
            ptzAction('zoom', { zoom, speed });
        };
        const stopZoom = () => ptzAction('stop');

        btn.onmousedown = startZoom;
        btn.onmouseup = stopZoom;
        btn.onmouseleave = stopZoom;
    });

    document.getElementById('speed-slider').oninput = (e) => {
        document.getElementById('speed-val').innerText = e.target.value;
    };

    document.getElementById('goto-preset-btn').onclick = () => {
        const pid = PRESET_SELECT.value;
        if (pid) fetch(`${API_BASE}/cameras/${selectedCamId}/presets/${pid}/goto`, { method: 'POST' });
    };

    document.getElementById('set-preset-btn').onclick = () => {
        const name = prompt("Enter Preset Name:");
        if (name) {
            fetch(`${API_BASE}/cameras/${selectedCamId}/presets/${name}/set`, { method: 'POST' });
            setTimeout(() => fetchPresets(selectedCamId), 1000);
        }
    };
}

function closeModal() {
    MODAL.style.display = 'none';
    document.getElementById('add-camera-form').reset();
    // Reset Visibility
    document.getElementById('rtsp-fields').style.display = 'block';
    document.getElementById('ndi-fields').style.display = 'none';
}

window.onload = init;
