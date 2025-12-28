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
let hlsInstances = {};
let logsInterval = null;

// --- Initialization ---
async function init() {
    await fetchCameras();
    setupEventListeners();
    setupKeyboardShortcuts();
    setInterval(pollStatus, 3000);

    // Logs Toggle
    const logsBtn = document.getElementById('logs-toggle-btn');
    if (logsBtn) {
        logsBtn.onclick = () => {
            const drawer = document.getElementById('logs-drawer');
            if (!drawer) return;
            drawer.classList.toggle('open');
            if (drawer.classList.contains('open')) {
                fetchLogs();
                if (!logsInterval) logsInterval = setInterval(fetchLogs, 2000);
            } else {
                if (logsInterval) clearInterval(logsInterval);
                logsInterval = null;
            }
        };
    }
}

async function fetchLogs() {
    try {
        const res = await fetch(`${API_BASE}/logs?limit=100`);
        const logs = await res.json();
        const container = document.getElementById('logs-list');
        container.innerHTML = logs.map(l => `
            <div class="log-entry ${l.level.toLowerCase()}">
                <span class="log-ts">${new Date(l.ts).toLocaleTimeString()}</span>
                <span style="font-weight:bold">[${l.level}]</span>
                ${l.camera_id ? `[${l.camera_id}]` : ''}: ${l.message}
            </div>
        `).join('');
    } catch (e) { console.error(e); }
}

// --- API Calls ---
async function fetchCameras() {
    try {
        const res = await fetch(`${API_BASE}/cameras`);
        cameras = await res.json();
        renderGrid();
    } catch (e) {
        console.error("Failed to fetch cameras", e);
        // Show error? For now update status
    }
}

async function pollStatus() {
    // Lightweight refresh - just get cameras again to update status
    try {
        const res = await fetch(`${API_BASE}/cameras`);
        const newData = await res.json();

        // Merge status only, avoid re-rendering video players if possible
        // Ideally we diff, but for now simple re-render of labels/status
        cameras = newData;
        updateStatusIndicators();
    } catch (e) {
        console.error("Poll failed", e);
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

async function fetchPresets(camId, force = false) {
    try {
        const endpoint = force ? `${API_BASE}/cameras/${camId}/presets/refresh` : `${API_BASE}/cameras/${camId}/presets`;
        const method = force ? 'POST' : 'GET';

        const res = await fetch(endpoint, { method });
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
    const slots = [0, 1, 2, 3];

    slots.forEach(i => {
        const cam = cameras[i];
        const cell = document.createElement('div');
        cell.className = 'video-cell';

        if (cam) {
            cell.dataset.id = cam.id;
            cell.onclick = (e) => {
                if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
                selectCamera(cam);
            };

            // Status Badge Container
            const statusBadge = document.createElement('div');
            statusBadge.className = 'status-badges';
            statusBadge.style.cssText = "position:absolute; top:5px; left:5px; z-index:20; display:flex; gap:5px;";

            // Generate Badges (filled by updateStatusIndicators)
            cell.appendChild(statusBadge);

            // Header Container (Name + Edit/Del)
            const header = document.createElement('div');
            header.className = 'cam-header';
            header.style.position = 'absolute';
            header.style.top = '0';
            header.style.right = '0'; // Move to right
            header.style.padding = '5px';
            header.style.display = 'flex';
            header.style.zIndex = '10';
            header.style.background = 'rgba(0,0,0,0.5)';
            header.style.borderRadius = '0 0 0 4px';

            const editBtn = document.createElement('button');
            editBtn.innerText = '⚙️';
            editBtn.onclick = () => openEditModal(cam);

            const delBtn = document.createElement('button');
            delBtn.innerText = '🗑️';
            delBtn.onclick = () => deleteCamera(cam.id);

            header.appendChild(editBtn);
            header.appendChild(delBtn);

            cell.appendChild(header);

            // Name Label (Bottom Left)
            const label = document.createElement('div');
            label.className = 'cam-label';
            label.innerText = cam.name;
            cell.appendChild(label);

            // Player Logic
            let playerEl;
            const url = cam.stream_url;

            // Only show player if preview is NOT offline/error? 
            // Better: Show error placeholder if URL empty.
            if (!url) {
                const rs = document.createElement('div');
                rs.className = 'status-indicator offline';
                rs.innerText = "PREVIEW OFFLINE";
                playerEl = rs;
            } else if (url.includes('mjpeg')) {
                playerEl = document.createElement('img');
                playerEl.className = 'video-player';
                playerEl.src = url;
                playerEl.style.objectFit = 'contain';
                playerEl.onerror = () => {
                    // Handle broken MJPEG
                    // Don't hide, but maybe overlay?
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

    updateStatusIndicators();

    if (selectedCamId && cameras.find(c => c.id === selectedCamId)) {
        highlightCamera(selectedCamId);
    } else {
        selectedCamId = null;
        updateControlsUI();
    }
}

function updateStatusIndicators() {
    cameras.forEach(cam => {
        const cell = document.querySelector(`.video-cell[data-id="${cam.id}"]`);
        if (!cell) return;

        const badgeContainer = cell.querySelector('.status-badges');
        if (!badgeContainer) return;

        // Control Status (PTZ)
        const cStat = cam.control_status || 'offline';
        const cColor = cStat === 'ok' ? '#10b981' : (cStat === 'error' ? '#ef4444' : '#6b7280');

        // Preview Status
        const pStat = cam.preview_status || 'offline';
        const pColor = pStat === 'ok' ? '#10b981' : (pStat === 'starting' ? '#eab308' : '#ef4444');

        badgeContainer.innerHTML = `
            <div title="Control: ${cStat}" style="width:10px; height:10px; border-radius:50%; background:${cColor}; border:1px solid #fff;"></div>
            <div title="Preview: ${pStat}" style="width:10px; height:10px; border-radius:50%; background:${pColor}; border:1px solid #fff;"></div>
        `;
    });
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

// --- Keyboard Shortcuts ---
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        if (!selectedCamId) return;
        if (e.target.tagName === 'INPUT') return; // Don't trigger if typing

        // Prevent scrolling with arrows/space
        if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].indexOf(e.code) > -1) {
            e.preventDefault();
        }

        const speed = parseFloat(document.getElementById('speed-slider').value);

        switch (e.code) {
            case 'ArrowUp': ptzAction('move', { pan: 0, tilt: 1, speed }); break;
            case 'ArrowDown': ptzAction('move', { pan: 0, tilt: -1, speed }); break;
            case 'ArrowLeft': ptzAction('move', { pan: -1, tilt: 0, speed }); break;
            case 'ArrowRight': ptzAction('move', { pan: 1, tilt: 0, speed }); break;
            // Zoom +/- keys? (Equal/Minus)
            case 'Equal': ptzAction('zoom', { zoom: 1, speed }); break;
            case 'Minus': ptzAction('zoom', { zoom: -1, speed }); break;
            case 'Space': ptzAction('stop'); break;
        }
    });

    document.addEventListener('keyup', (e) => {
        if (!selectedCamId) return;
        // Stop on release of movement keys
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Equal', 'Minus'].includes(e.code)) {
            ptzAction('stop');
        }
    });
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
    // form.password.value = ""; // Don't show password

    // Preview
    const pType = cam.preview?.type || 'rtsp';
    document.getElementById('source-type-select').value = pType;

    if (pType === 'ndi') {
        document.getElementById('ndi-fields').style.display = 'block';
        document.getElementById('rtsp-fields').style.display = 'none';
        // Try to set NDI source name.
        // We'll create an option for it temporarily so it shows up.
        if (cam.preview?.ndi_source) {
            const select = document.getElementById('ndi-source-select');
            select.innerHTML = `<option value="${cam.preview.ndi_source}" selected>${cam.preview.ndi_source}</option>`;
        }
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

        // Touch support
        btn.onmousedown = startMove;
        btn.onmouseup = stopMove;
        btn.onmouseleave = stopMove;
        btn.ontouchstart = (e) => { e.preventDefault(); startMove(); };
        btn.ontouchend = (e) => { e.preventDefault(); stopMove(); };
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
        btn.ontouchstart = (e) => { e.preventDefault(); startZoom(); };
        btn.ontouchend = (e) => { e.preventDefault(); stopZoom(); };
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
            setTimeout(() => fetchPresets(selectedCamId, true), 1000); // refresh
        }
    };

    // Refresh Presets Btn
    // Add logic to UI for refresh button? 
    // Assuming UI has one or we add it dynamically?
    // Let's create one dynamically in the preset controls if missing.
    const presetContainer = document.querySelector('.preset-controls');
    if (presetContainer && !document.getElementById('refresh-preset-btn')) {
        const refBtn = document.createElement('button');
        refBtn.id = 'refresh-preset-btn';
        refBtn.innerText = '↻';
        refBtn.title = "Refresh Presets";
        refBtn.onclick = () => { if (selectedCamId) fetchPresets(selectedCamId, true); };
        presetContainer.appendChild(refBtn);
    }
}

window.onload = init;
