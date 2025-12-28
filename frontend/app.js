const API_BASE = '/api';
const VIDEO_GRID = document.getElementById('video-grid');
const PTZ_CONTROLS = document.getElementById('ptz-controls');
const SELECTED_CAM_NAME = document.getElementById('selected-cam-name');
const MODAL = document.getElementById('add-camera-modal');
const PRESET_SELECT = document.getElementById('preset-select');
const MODAL_TITLE = document.querySelector('#add-camera-modal h2');
const ADD_BTN = document.querySelector('#add-camera-form button[type="submit"]');

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
        // Show error in grid
        VIDEO_GRID.innerHTML = '<div class="error-state">Failed to load cameras. Backend offline?</div>';
    }
}

async function saveCamera(formData) {
    const isEdit = !!formData.id && cameras.some(c => c.id === formData.id);
    const method = isEdit ? 'PUT' : 'POST';
    const url = isEdit ? `${API_BASE}/cameras/${formData.id}` : `${API_BASE}/cameras`;

    // Construct Payload
    const payload = {
        id: formData.id || 'cam_' + Math.floor(Math.random() * 10000),
        name: formData.name,
        ip: formData.ip,
        onvif_port: parseInt(formData.onvif_port),
        username: formData.username,
        password: formData.password,
        control_protocol: 'onvif',
        preview: {
            type: formData.video_source_type,
            ndi_source: formData.ndi_source_name || null,
            rtsp_url: formData.rtsp_url || null
        }
    };

    try {
        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('Save failed');

        closeModal();
        await fetchCameras();
    } catch (e) {
        console.error(e);
        alert("Failed to save camera");
    }
}

async function deleteCamera(id) {
    if (!confirm("Are you sure?")) return;
    await fetch(`${API_BASE}/cameras/${id}`, { method: 'DELETE' });
    if (selectedCamId === id) {
        selectedCamId = null;
        updateControlsUI();
    }
    await fetchCameras();
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
        const res = await fetch(`${API_BASE}/ndi/sources`);
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

    // Always render 4 slots
    const slots = [0, 1, 2, 3];

    slots.forEach(i => {
        const cam = cameras[i];
        const cell = document.createElement('div');
        cell.className = 'video-cell';

        if (cam) {
            cell.dataset.id = cam.id;
            cell.onclick = (e) => {
                // Ignore clicks on buttons
                if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
                selectCamera(cam);
            };

            // Header Container (Name + Edit/Del)
            const header = document.createElement('div');
            header.className = 'cam-header';
            header.style.position = 'absolute';
            header.style.top = '0';
            header.style.left = '0';
            header.style.right = '0';
            header.style.padding = '5px';
            header.style.display = 'flex';
            header.style.justifyContent = 'space-between';
            header.style.zIndex = '10';
            header.style.background = 'rgba(0,0,0,0.5)';

            const label = document.createElement('span');
            label.innerText = cam.name;
            label.style.fontWeight = 'bold';

            const actions = document.createElement('div');

            const editBtn = document.createElement('button');
            editBtn.innerText = '⚙️';
            editBtn.onclick = () => openEditModal(cam);

            const delBtn = document.createElement('button');
            delBtn.innerText = '🗑️';
            delBtn.onclick = () => deleteCamera(cam.id);

            actions.appendChild(editBtn);
            actions.appendChild(delBtn);

            header.appendChild(label);
            header.appendChild(actions);
            cell.appendChild(header);

            // Player Logic
            let playerEl;
            const url = cam.stream_url;

            if (!url) {
                const rs = document.createElement('div');
                rs.className = 'status-indicator offline';
                rs.innerText = "OFFLINE";
                playerEl = rs;
            } else if (url.includes('mjpeg')) {
                playerEl = document.createElement('img');
                playerEl.className = 'video-player';
                playerEl.src = url;
                playerEl.style.objectFit = 'contain';
                playerEl.onerror = () => {
                    playerEl.style.display = 'none';
                    const err = document.createElement('div');
                    err.className = 'status-indicator error';
                    err.innerText = "PREVIEW ERROR";
                    cell.appendChild(err);
                };
            } else {
                playerEl = document.createElement('video');
                playerEl.className = 'video-player';
                playerEl.muted = true;
                playerEl.autoplay = true;
                playerEl.playsInline = true;

                if (Hls.isSupported() && url.includes('.m3u8')) {
                    const hls = new Hls({ lowLatencyMode: true });
                    hls.loadSource(url);
                    hls.attachMedia(playerEl);
                    hls.on(Hls.Events.MANIFEST_PARSED, () => playerEl.play().catch(e => console.log(e)));
                    hls.on(Hls.Events.ERROR, () => {
                        const err = document.createElement('div');
                        err.className = 'status-indicator error';
                        err.innerText = "STREAM ERROR";
                        if (!cell.querySelector('.error')) cell.appendChild(err);
                    });
                    hlsInstances[cam.id] = hls;
                } else if (playerEl.canPlayType('application/vnd.apple.mpegurl')) {
                    playerEl.src = url;
                }
            }
            cell.appendChild(playerEl);

        } else {
            // Empty Slot
            cell.className += ' empty-slot';
            cell.innerHTML = '<div style="color:#444; font-size:2em;">+</div>';
            cell.onclick = () => openAddModal();
        }

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
    SELECTED_CAM_NAME.innerText = cam.name + (cam.capabilities?.presets ? "" : " (No Presets)");
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

// --- Modal Handling ---
function openAddModal() {
    MODAL_TITLE.innerText = "Add Camera";
    ADD_BTN.innerText = "Add";
    document.getElementById('add-camera-form').reset();
    document.querySelector('input[name="id"]').value = "";
    document.getElementById('rtsp-fields').style.display = 'block';
    document.getElementById('ndi-fields').style.display = 'none';
    MODAL.style.display = 'flex';
}

function openEditModal(cam) {
    MODAL_TITLE.innerText = "Edit Camera";
    ADD_BTN.innerText = "Save";

    const form = document.getElementById('add-camera-form');
    form.id.value = cam.id;
    form.name.value = cam.name;
    form.ip.value = cam.ip;
    form.onvif_port.value = cam.onvif_port;
    form.username.value = cam.username;
    form.password.value = ""; // Don't show password

    // Preview
    const pType = cam.preview?.type || 'rtsp';
    document.getElementById('source-type-select').value = pType;

    if (pType === 'ndi') {
        document.getElementById('ndi-fields').style.display = 'block';
        document.getElementById('rtsp-fields').style.display = 'none';
        // Populate specific fields if we can (harder with dynamic DOM for NDI select)
        // We set the select manually after scan? Or just leave blank to force re-select.
        // Let's try to set value if we scan.
    } else {
        document.getElementById('rtsp-fields').style.display = 'block';
        document.getElementById('ndi-fields').style.display = 'none';
        form.rtsp_url.value = cam.preview?.rtsp_url || "";
    }

    MODAL.style.display = 'flex';
}

function closeModal() {
    MODAL.style.display = 'none';
}

// --- Event Listeners ---
function setupEventListeners() {
    document.getElementById('add-camera-btn').onclick = openAddModal;
    document.getElementById('cancel-add-btn').onclick = closeModal;
    document.getElementById('scan-ndi-btn').onclick = scanNDI;

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
        saveCamera(data); // Handles Add and Edit
    };

    // PTZ Controls... (Keep existing logic)
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

window.onload = init;
