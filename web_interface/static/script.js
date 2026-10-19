// Custom JavaScript for Ghost Host 

// Audio Management Logic for Ghost Host

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const audioFileList = document.getElementById('audio-file-list');
    const selectDefaultAudio = document.getElementById('select-default-audio');
    const btnSetDefaultAudio = document.getElementById('btn-set-default-audio');
    const audioUploadInput = document.getElementById('audio-upload');
    const btnUploadAudio = document.getElementById('btn-upload-audio');
    const uploadStatus = document.getElementById('upload-status');
    const audioVolumeSlider = document.getElementById('audio-volume');
    const audioVolumeValue = document.getElementById('audio-volume-value');
    const btnSetVolume = document.getElementById('btn-set-volume');
    const currentDefaultAudio = document.getElementById('current-default-audio');
    const currentVolumeSpan = document.getElementById('current-volume');
    const defaultStatus = document.getElementById('default-status');
    const volumeStatus = document.getElementById('volume-status');
    const btnAddTrigger = document.getElementById('btn-add-trigger');
    const triggerStatus = document.getElementById('trigger-status');
    const tableTriggers = document.getElementById('table-triggers');

    // --- STATUS SECTION LOGIC ---
    const statusNetwork = document.getElementById('status-network');
    const statusIp = document.getElementById('status-ip');
    const statusApMode = document.getElementById('status-ap-mode');

    function updateStatusUI(data) {
        // Network (use config default if not present)
        if (data.current_network_ssid) {
            statusNetwork.textContent = data.current_network_ssid;
        } else {
            statusNetwork.textContent = 'Homenet1';
        }
        // IP Address
        if (data.ip_address) {
            statusIp.textContent = data.ip_address;
        } else {
            statusIp.textContent = '192.168.128.105';
        }
        if (statusApMode) {
            if (data.ap_mode_active) {
                statusApMode.textContent = `Active (${data.ap_mode_ssid || DEFAULT_AP_SETUP_SSID} at ${data.ap_mode_ip || 'N/A'})`;
                statusApMode.className = 'text-warning';
            } else {
                statusApMode.textContent = 'Inactive';
                statusApMode.className = 'text-muted';
            }
        }
        // Update overall UI based on AP mode (some is handled by Jinja, this can be supplemental)
        if (IS_AP_MODE) {
            // Optional: additional JS-based UI adjustments if Jinja isn't enough
            // e.g., specifically disable buttons that might still be visible
            if(btnSetDefaultAudio) btnSetDefaultAudio.disabled = true;
            if(btnUploadAudio) btnUploadAudio.disabled = true;
            if(btnSetVolume) btnSetVolume.disabled = true;
            if(btnReboot) btnReboot.disabled = true;
            if(btnConnectSaved) btnConnectSaved.disabled = true;
            if(btnDisconnectNetwork) btnDisconnectNetwork.disabled = true;
            if(btnDeleteSaved) btnDeleteSaved.disabled = true;
        }
    }

    function loadStatus() {
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                updateStatusUI(data);
                // Update default audio and volume from status if available (or make separate calls)
                if (currentDefaultAudio) currentDefaultAudio.textContent = data.default_audio_file || 'None';
                if (currentVolumeSpan) currentVolumeSpan.textContent = data.volume !== undefined ? data.volume + '%' : '--%';
                if (audioVolumeSlider && data.volume !== undefined) {
                    audioVolumeSlider.value = data.volume;
                    if(audioVolumeValue) audioVolumeValue.textContent = data.volume;
                } else if (audioVolumeSlider) {
                    // Fallback if not in status, load separately
                    loadVolume();
                }
            })
            .catch(() => {
                updateStatusUI({}); 
                if (currentDefaultAudio) currentDefaultAudio.textContent = 'Error loading';
                if (currentVolumeSpan) currentVolumeSpan.textContent = 'Error';
            });
    }

    // --- SHARED UI HELPERS ---
    // One way to report a result: a status line next to the thing you just touched.
    function flash(el, message, isError = false) {
        if (!el) return;
        el.textContent = message;
        el.className = 'form-text ' + (isError ? 'text-danger' : 'text-success');
        clearTimeout(el._flashTimer);
        el._flashTimer = setTimeout(() => { el.textContent = ''; }, 5000);
    }
    const audioFilesMsg = document.getElementById('audio-files-msg');

    // --- NOW PLAYING / STOP ---
    // Anything the prop speaks (a button here, a sensor, a network request, a timed trigger)
    // shows the bar at the top of every tab with a Stop button.
    let nowPlaying = { performing: false, file: null };
    function syncPlayButtons() {
        document.querySelectorAll('button[data-play-file]').forEach(b => {
            const on = nowPlaying.performing && nowPlaying.file === b.dataset.playFile;
            if (on) b.dataset.playing = '1'; else delete b.dataset.playing;
            b.textContent = on ? 'Stop' : 'Play on prop';
            b.classList.toggle('btn-danger', on);
            b.classList.toggle('btn-info', !on);
        });
    }
    async function stopProp() {
        try { await fetch('/api/live/stop', { method: 'POST' }); } catch (e) {}
        await refreshNow();
    }
    async function refreshNow() {
        let h;
        try { h = await (await fetch('/api/health')).json(); } catch (e) { return null; }
        nowPlaying = { performing: !!h.performing, file: h.now_playing || null };
        const bar = document.getElementById('nowbar');
        if (bar) {
            bar.hidden = !h.performing;
            const descs = {};
            audioFilesData.forEach(f => { descs[f.filename] = f.description; });
            document.getElementById('nowbar-text').textContent = h.performing
                ? 'Speaking: ' + (h.now_playing ? (descs[h.now_playing] || h.now_playing) : 'playing now') : '';
        }
        syncPlayButtons();
        return h;
    }
    const btnNowbarStop = document.getElementById('btn-nowbar-stop');
    if (btnNowbarStop) btnNowbarStop.addEventListener('click', stopProp);
    // Previews in the browser are separate from the prop: stop them when leaving the Media tab
    document.querySelectorAll('nav.tabs a[data-tab]').forEach(a => a.addEventListener('click', () => {
        document.querySelectorAll('audio').forEach(p => p.pause());
    }));

    // Fetch and display audio files
    let audioFilesData = [];
    const audioSort = document.getElementById('audio-sort');
    const audioPoolFilter = document.getElementById('audio-pool-filter');

    function fmtDuration(sec) {
        if (sec == null) return '';
        const m = Math.floor(sec / 60), s = Math.round(sec % 60);
        return `${m}:${String(s).padStart(2, '0')}`;
    }

    function refreshPoolFilter() {
        if (!audioPoolFilter) return;
        const names = new Map();
        audioFilesData.forEach(f => f.pools.forEach(p => names.set(p.id, p.name)));
        const current = audioPoolFilter.value;
        audioPoolFilter.innerHTML = '<option value="">All files</option><option value="__none__">Not in any pool</option>';
        names.forEach((name, id) => {
            const o = document.createElement('option');
            o.value = id; o.textContent = 'In pool: ' + name;
            audioPoolFilter.appendChild(o);
        });
        audioPoolFilter.value = names.has(current) || current === '__none__' ? current : '';
    }

    function renderAudioList() {
        if (!audioFileList) return;
        const poolId = audioPoolFilter ? audioPoolFilter.value : '';
        const sortBy = audioSort ? audioSort.value : 'name';
        let files = audioFilesData.filter(f =>
            !poolId || (poolId === '__none__' ? f.pools.length === 0 : f.pools.some(p => p.id === poolId)));
        const posIn = f => (f.pools.find(p => p.id === poolId) || {}).position || 0;
        const cmp = {
            name: (a, b) => a.filename.localeCompare(b.filename),
            newest: (a, b) => (b.modified || 0) - (a.modified || 0),
            oldest: (a, b) => (a.modified || 0) - (b.modified || 0),
            longest: (a, b) => (b.duration || 0) - (a.duration || 0),
            shortest: (a, b) => (a.duration || 0) - (b.duration || 0),
            pool: (a, b) => (a.pools[0] ? a.pools[0].name : '\uffff').localeCompare(b.pools[0] ? b.pools[0].name : '\uffff') || a.filename.localeCompare(b.filename),
            order: (a, b) => posIn(a) - posIn(b),
        }[sortBy] || (() => 0);
        files = files.slice().sort(cmp);
        audioFileList.innerHTML = '';
        if (!files.length) {
            audioFileList.innerHTML = '<li class="list-group-item text-muted">No files match.</li>';
            return;
        }
        files.forEach(fileInfo => {
            const { filename, is_default, has_timestamps } = fileInfo;
            const li = document.createElement('li');
            li.className = 'list-group-item';

            const head = document.createElement('div');
            head.className = 'd-flex justify-content-between align-items-start flex-wrap';
            const title = document.createElement('div');
            const nameEl = document.createElement('strong');
            nameEl.textContent = filename;
            title.appendChild(nameEl);
            const addBadge = (text, cls) => {
                const b = document.createElement('span');
                b.className = 'badge ms-1 ' + cls;
                b.textContent = text;
                title.appendChild(b);
            };
            if (is_default) addBadge('Default', 'bg-primary');
            fileInfo.pools.forEach(p => addBadge(poolId === p.id ? `${p.name} #${p.position}` : p.name, 'bg-secondary'));
            if (!fileInfo.pools.length) addBadge('No pool', 'bg-light text-dark border');
            const meta = document.createElement('div');
            meta.className = 'form-text';
            const added = fileInfo.modified ? new Date(fileInfo.modified * 1000).toLocaleDateString() : '';
            meta.textContent = [fmtDuration(fileInfo.duration), added && 'added ' + added].filter(Boolean).join(' · ');
            title.appendChild(meta);

            const buttonGroup = document.createElement('div');
            buttonGroup.className = 'btn-group mt-1 mt-md-0';
            if (!has_timestamps) {
                const generateBtn = document.createElement('button');
                generateBtn.className = 'btn btn-sm btn-info me-1 btn-generate-timestamps';
                generateBtn.textContent = 'Gen Timestamps';
                generateBtn.dataset.filename = filename;
                generateBtn.onclick = function() { generateTimestamps(filename); };
                buttonGroup.appendChild(generateBtn);
            } else {
                const timestampsBadge = document.createElement('span');
                timestampsBadge.className = 'badge bg-info me-1 align-self-center';
                timestampsBadge.textContent = 'Has Timestamps';
                buttonGroup.appendChild(timestampsBadge);
            }
            const playBtn = document.createElement('button');
            playBtn.type = 'button';
            playBtn.className = 'btn btn-sm btn-info me-1';
            playBtn.dataset.playFile = filename;
            playBtn.textContent = 'Play on prop';
            playBtn.addEventListener('click', async () => {
                if (playBtn.dataset.playing) { await stopProp(); return; }
                const r = await postJson('/api/live/play', { audio_file: filename });
                flash(audioFilesMsg, r.result.success ? 'Playing ' + filename + ' on the prop' : (r.result.message || 'Could not play'), !r.result.success);
                refreshNow();
            });
            buttonGroup.appendChild(playBtn);
            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn-sm btn-danger btn-delete-audio';
            delBtn.textContent = 'Delete';
            delBtn.dataset.filename = filename;
            delBtn.onclick = function() { deleteAudioFile(filename); };
            buttonGroup.appendChild(delBtn);
            head.appendChild(title);
            head.appendChild(buttonGroup);
            li.appendChild(head);

            const desc = document.createElement('input');
            desc.type = 'text';
            desc.className = 'form-control form-control-sm mt-2';
            desc.placeholder = 'Description (e.g. Clue 3: glass T)';
            desc.value = fileInfo.description || '';
            desc.addEventListener('change', async () => {
                const resp = await fetch('/api/audio/description', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename, description: desc.value }) });
                if (resp.ok) { fileInfo.description = desc.value.trim(); desc.classList.add('is-valid'); setTimeout(() => desc.classList.remove('is-valid'), 1500); }
                else desc.classList.add('is-invalid');
            });
            li.appendChild(desc);

            const liveWrap = document.createElement('label');
            liveWrap.className = 'form-check mt-2';
            const liveChk = document.createElement('input');
            liveChk.type = 'checkbox';
            liveChk.className = 'form-check-input';
            liveChk.checked = !!fileInfo.live;
            liveChk.addEventListener('change', async () => {
                await fetch('/api/live/favorite', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename, on: liveChk.checked }) });
                fileInfo.live = liveChk.checked;
            });
            liveWrap.appendChild(liveChk);
            liveWrap.appendChild(document.createTextNode(' Live button (show on the Live tab)'));
            li.appendChild(liveWrap);

            // Per-file boost: the system volume tops out, this raises just this clip
            const gainRow = document.createElement('div');
            gainRow.className = 'gain-row mt-2';
            const gainLbl = document.createElement('label');
            gainLbl.textContent = 'Boost';
            gainLbl.style.margin = '0';
            const gainSlider = document.createElement('input');
            gainSlider.type = 'range';
            gainSlider.min = -10; gainSlider.max = 20; gainSlider.step = 1;
            gainSlider.value = fileInfo.gain_db || 0;
            const gainVal = document.createElement('span');
            gainVal.className = 'form-text';
            const fmtGain = v => (v > 0 ? '+' : '') + v + ' dB' + (v == 0 ? ' (original)' : '');
            gainVal.textContent = fmtGain(+gainSlider.value);
            gainSlider.addEventListener('input', () => { gainVal.textContent = fmtGain(+gainSlider.value); });
            gainSlider.addEventListener('change', async () => {
                gainVal.textContent = 'rendering...';
                gainSlider.disabled = true;
                try {
                    const resp = await fetch('/api/audio/gain', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename, gain_db: +gainSlider.value }) });
                    const result = await resp.json();
                    if (resp.ok && result.success) {
                        fileInfo.gain_db = result.gain_db;
                        gainVal.textContent = fmtGain(result.gain_db) + ' saved';
                        player.src = (result.gain_db ? '/api/audio/preview/' : '/SoundFiles/') + encodeURIComponent(filename) + '?t=' + Date.now();
                    } else gainVal.textContent = result.error || 'failed';
                } catch (e) { gainVal.textContent = 'failed'; }
                gainSlider.disabled = false;
            });
            gainRow.appendChild(gainLbl);
            gainRow.appendChild(gainSlider);
            gainRow.appendChild(gainVal);
            li.appendChild(gainRow);

            const player = document.createElement('audio');
            player.controls = true;
            player.preload = 'none';
            player.className = 'w-100 mt-2';
            player.src = (fileInfo.gain_db ? '/api/audio/preview/' : '/SoundFiles/') + encodeURIComponent(filename);
            // Only one file plays at a time
            player.addEventListener('play', () => {
                audioFileList.querySelectorAll('audio').forEach(a => { if (a !== player) a.pause(); });
            });
            li.appendChild(player);
            audioFileList.appendChild(li);
        });
        syncPlayButtons();
    }
    if (audioSort) audioSort.addEventListener('change', renderAudioList);
    if (audioPoolFilter) audioPoolFilter.addEventListener('change', renderAudioList);

    function loadAudioFiles() {
        if (IS_AP_MODE) { // Don't load audio files if in AP mode
            if(audioFileList) audioFileList.innerHTML = '<li class="list-group-item">Audio management disabled in AP Mode.</li>';
            return;
        }
        fetch('/api/audio/files')
            .then(res => res.json())
            .then(data => {
                if(audioFileList) audioFileList.innerHTML = '';
                if(selectDefaultAudio) selectDefaultAudio.innerHTML = '';
                
                audioFilesData = data.files;
                renderAudioList();
                data.files.forEach(fileInfo => {
                    if (selectDefaultAudio) {
                        const opt = document.createElement('option');
                        opt.value = fileInfo.filename;
                        opt.textContent = fileInfo.filename;
                        if (fileInfo.is_default) opt.selected = true;
                        selectDefaultAudio.appendChild(opt);
                    }
                });
                refreshPoolFilter();
                if (currentDefaultAudio) {
                    currentDefaultAudio.textContent = data.default || 'None';
                }
            })
            .catch(err => {
                if(audioFileList) audioFileList.innerHTML = '<li class="list-group-item text-danger">Error loading audio files.</li>';
                console.error("Error loading audio files:", err);
            });
    }

    // Set default audio file
    btnSetDefaultAudio.addEventListener('click', function() {
        const filename = selectDefaultAudio.value;
        if (!filename) { flash(defaultStatus, 'Please select an audio file.', true); return; }
        fetch('/api/audio/default', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadAudioFiles();
                loadStatus(); // Refresh status to get new default audio
                loadPools();  // the sensor dropdowns name the default
                flash(defaultStatus, 'Default audio set to ' + filename);
            } else {
                flash(defaultStatus, data.error || 'Failed to set default audio.', true);
            }
        });
    });

    // Upload audio file
    btnUploadAudio.addEventListener('click', function() {
        if (!audioUploadInput || !audioUploadInput.files[0]) {
            displayMessage(uploadStatus, 'No file selected.', false);
            return;
        }
        const file = audioUploadInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        btnUploadAudio.disabled = true;
        btnUploadAudio.textContent = 'Uploading...';
        displayMessage(uploadStatus, 'Uploading file...', true);

        fetch('/api/audio/upload', { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                displayMessage(uploadStatus, `Upload successful: ${data.filename}`, true);
                loadAudioFiles();
                audioUploadInput.value = ''; // Clear file input
            } else {
                displayMessage(uploadStatus, data.error || 'Upload failed.', false);
            }
        })
        .catch(err => {
             displayMessage(uploadStatus, `Upload request error: ${err}`, false);
        })
        .finally(() => {
            btnUploadAudio.disabled = false;
            btnUploadAudio.textContent = 'Upload';
        });
    });

    // Delete audio file
    function deleteAudioFile(filename) {
        if (!confirm(`Are you sure you want to delete ${filename}? This will also delete its timestamp file if it exists.`)) return;
        fetch(`/api/audio/delete/${encodeURIComponent(filename)}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                flash(audioFilesMsg, 'Deleted ' + filename);
                loadAudioFiles();
            } else {
                flash(audioFilesMsg, data.error || 'Failed to delete file.', true);
            }
        })
        .catch(err => flash(audioFilesMsg, `Error deleting file: ${err}`, true))
    }

    // Fetch and display volume
    function loadVolume() {
        if (IS_AP_MODE) return;
        fetch('/api/audio/volume')
            .then(res => res.json())
            .then(data => {
                if (audioVolumeSlider) audioVolumeSlider.value = data.volume;
                if (audioVolumeValue) audioVolumeValue.textContent = data.volume;
                if (currentVolumeSpan) currentVolumeSpan.textContent = data.volume + '%';
            })
            .catch(err => {
                if (currentVolumeSpan) currentVolumeSpan.textContent = 'Error';
                console.error("Error loading volume:", err);
            });
    }
    audioVolumeSlider.addEventListener('input', function() {
        if(audioVolumeValue) audioVolumeValue.textContent = this.value;
    });
    btnSetVolume.addEventListener('click', function() {
        const volume = parseInt(audioVolumeSlider.value, 10);
        fetch('/api/audio/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ volume })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadVolume(); // Reload to confirm
                if (currentVolumeSpan) currentVolumeSpan.textContent = data.volume + '%';
                flash(volumeStatus, 'Volume set to ' + data.volume + '%');
            } else {
                flash(volumeStatus, data.error || 'Failed to set volume', true);
            }
        })
        .catch(() => flash(volumeStatus, 'Request error.', true));
    });

    // --- WIFI MANAGEMENT LOGIC ---
    const selectAvailableNetworks = document.getElementById('select-available-networks');
    const inputAvailablePassword = document.getElementById('input-available-password');
    const btnConnectAvailable = document.getElementById('btn-connect-available');
    const selectSavedNetworks = document.getElementById('select-saved-networks');
    const btnConnectSaved = document.getElementById('btn-connect-saved');
    const btnDisconnectNetwork = document.getElementById('btn-disconnect-network');
    const btnDeleteSaved = document.getElementById('btn-delete-saved');
    const inputNewSsid = document.getElementById('input-new-ssid');
    const inputNewPassword = document.getElementById('input-new-password');
    const checkboxNewAutoconnect = document.getElementById('checkbox-new-autoconnect');
    const btnSaveOrConnectNewNetwork = document.getElementById('btn-save-or-connect-new-network');
    const btnRefreshWifiLists = document.getElementById('btn-refresh-wifi-lists');
    const wifiStatusMessage = document.getElementById('wifi-status-message');

    function displayMessage(element, message, isSuccess) {
        if (element) {
            element.textContent = message;
            element.className = isSuccess ? 'form-text text-success' : 'form-text text-danger';
        }
    }

    function displayTriggerMessage(message, isError = false) {
        if (triggerStatus) {
            triggerStatus.textContent = message;
            triggerStatus.className = `form-text ${isError ? 'text-danger' : 'text-success'}`;
            setTimeout(() => { triggerStatus.textContent = ''; }, 4000);
        }
    }

    async function copyToClipboard(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            }
        } catch (e) {
            // fall through to legacy method
        }
        try {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-9999px';
            textArea.style.top = '0';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            return successful;
        } catch (e) {
            return false;
        }
    }

    function displayWifiMessage(message, isError = false) {
        if (wifiStatusMessage) {
            wifiStatusMessage.textContent = message;
            wifiStatusMessage.className = `alert ${isError ? 'alert-danger' : 'alert-success'}`;
            wifiStatusMessage.style.display = 'block';
            setTimeout(() => { wifiStatusMessage.style.display = 'none'; }, 5000);
        }
    }

    async function loadWiFiNetworks() {
        try {
            const response = await fetch('/api/networks');
            const data = await response.json();

            if (selectAvailableNetworks) {
                selectAvailableNetworks.innerHTML = '<option value="">Select an available network...</option>';
                if (data.available_networks && data.available_networks.length > 0) {
                    data.available_networks.forEach(net => {
                        const opt = document.createElement('option');
                        opt.value = net.ssid;
                        opt.textContent = `${net.ssid} (${net.signal}%, ${net.security || 'Open'})`;
                        selectAvailableNetworks.appendChild(opt);
                    });
                } else {
                    selectAvailableNetworks.innerHTML = '<option value="">No networks found, try refresh.</option>';
                }
            }

            if (selectSavedNetworks && !IS_AP_MODE) { // Only populate if not in AP mode
                selectSavedNetworks.innerHTML = '<option value="">Select a saved network...</option>';
                if (data.saved_networks && data.saved_networks.length > 0) {
                    data.saved_networks.forEach(net => {
                        const opt = document.createElement('option');
                        opt.value = net.uuid; // Use UUID for saved operations
                        opt.textContent = net.name;
                        selectSavedNetworks.appendChild(opt);
                    });
                } else {
                    selectSavedNetworks.innerHTML = '<option value="">No saved networks.</option>';
                }
            }
        } catch (error) {
            console.error('Failed to load WiFi networks:', error);
            if(selectAvailableNetworks) selectAvailableNetworks.innerHTML = '<option>Error loading networks</option>';
            if(selectSavedNetworks && !IS_AP_MODE) selectSavedNetworks.innerHTML = '<option>Error loading networks</option>';
            displayWifiMessage('Failed to load WiFi networks list.', true);
        }
    }

    btnRefreshWifiLists.addEventListener('click', loadWiFiNetworks);

    async function handleNetworkConnection(endpoint, payload) {
        displayWifiMessage('Processing network request...', false);
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.success) {
                displayWifiMessage(result.message || 'Network operation successful!', false);
                // If AP mode was active and we just connected, the page might reload or redirect
                // due to network change. For now, just reload status and wifi lists.
                if (IS_AP_MODE && endpoint === '/api/networks/connect') {
                    // After successful connection from AP mode, inform user page will reload or they need to reconnect
                    displayWifiMessage('Connected to new network! System will switch. You may need to reconnect to the new network and refresh this page or navigate to ghosthost.local.', false);
                    // Optionally, trigger a page reload after a delay
                    setTimeout(() => window.location.reload(), 8000);
                } else {
                    loadStatus();
                    loadWiFiNetworks();
                }
            } else {
                displayWifiMessage(result.message || 'Network operation failed.', true);
            }
        } catch (error) {
            console.error('Network operation error:', error);
            displayWifiMessage('Request failed: ' + error, true);
        }
    }
    
    if (btnConnectAvailable) {
        btnConnectAvailable.addEventListener('click', function() {
            const ssid = selectAvailableNetworks.value;
            const password = inputAvailablePassword.value;
            if (!ssid) { displayWifiMessage('Please select a network.', true); return; }
            // Password might be optional for open networks, API should handle.
            handleNetworkConnection('/api/networks/connect', { ssid_or_uuid: ssid, password });
        });
    }

    if (btnSaveOrConnectNewNetwork) {
        btnSaveOrConnectNewNetwork.addEventListener('click', function() {
            const ssid = inputNewSsid.value.trim();
            const password = inputNewPassword.value;
            const autoconnect = checkboxNewAutoconnect ? checkboxNewAutoconnect.checked : true;

            if (!ssid) { displayWifiMessage('SSID cannot be empty.', true); return; }
            // Password might be optional for open networks, but usually required for saving.
            // For AP mode connection, password might be required by the target network.

            if (IS_AP_MODE) {
                // In AP mode, this button connects to the specified network
                if (!password) { displayWifiMessage('Password required to connect.', true); return; }
                handleNetworkConnection('/api/networks/connect', { ssid_or_uuid: ssid, password });
            } else {
                // In client mode, this button saves a network profile
                if (!password) { displayWifiMessage('Password required to save network profile.', true); return; }
                handleNetworkConnection('/api/networks/save', { ssid, password, autoconnect });
            }
        });
    }

    if (btnConnectSaved && !IS_AP_MODE) { // Button might not exist/be relevant in AP mode
        btnConnectSaved.addEventListener('click', function() {
            const uuid = selectSavedNetworks.value;
            if (!uuid) { displayWifiMessage('Please select a saved network.', true); return; }
            handleNetworkConnection('/api/networks/connect', { ssid_or_uuid: uuid }); // No password needed for saved
        });
    }

    if (btnDisconnectNetwork && !IS_AP_MODE) {
        btnDisconnectNetwork.addEventListener('click', function() {
            // Disconnects the current active connection
            if (confirm('Are you sure you want to disconnect from the current network?')) {
                handleNetworkConnection('/api/networks/disconnect', {}); 
            }
        });
    }

    if (btnDeleteSaved && !IS_AP_MODE) {
        btnDeleteSaved.addEventListener('click', function() {
            const uuid = selectSavedNetworks.value;
            if (!uuid) { displayWifiMessage('Please select a saved network to delete.', true); return; }
            if (confirm(`Are you sure you want to delete the saved network: ${selectSavedNetworks.options[selectSavedNetworks.selectedIndex].text}?`)) {
                handleNetworkConnection('/api/networks/delete', { name_or_uuid: uuid });
            }
        });
    }
    
    // Removed event listeners for btnActivateAp and btnDeactivateAp as buttons are removed.

    // --- SYSTEM REBOOT --- 
    const btnReboot = document.getElementById('btn-reboot');
    if (btnReboot && !IS_AP_MODE) {
        btnReboot.addEventListener('click', function() {
            if (confirm('Are you sure you want to reboot the system?')) {
                fetch('/api/system/reboot', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        // Disable UI as system goes down
                        document.body.innerHTML = '<div class="container mt-5 alert alert-info"><h1>Rebooting...</h1><p>Please wait for the system to restart. You may need to manually refresh this page after a few minutes.</p></div>';
                    } else {
                        flash(document.getElementById('reboot-msg'), data.message || 'Reboot failed.', true);
                    }
                })
                .catch(err => {
                    flash(document.getElementById('reboot-msg'), 'Failed to send reboot command: ' + err, true);
                });
            }
        });
    }

    // --- COOLDOWN PERIOD LOGIC ---
    const cooldownInput = document.getElementById('cooldown-period-input');
    const btnSetCooldown = document.getElementById('btn-set-cooldown');
    const cooldownStatus = document.getElementById('cooldown-status');

    function loadCooldown() {
        fetch('/api/config/cooldown')
            .then(res => res.json())
            .then(data => {
                if (cooldownInput) cooldownInput.value = data.cooldown_period;
            })
            .catch(() => {
                if (cooldownStatus) cooldownStatus.textContent = 'Error loading cooldown value.';
            });
    }

    if (btnSetCooldown) {
        btnSetCooldown.addEventListener('click', function() {
            const value = parseInt(cooldownInput.value, 10);
            fetch('/api/config/cooldown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cooldown_period: value })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    flash(cooldownStatus, 'Cooldown updated');
                } else {
                    flash(cooldownStatus, data.error || 'Failed to update cooldown.', true);
                }
            })
            .catch(() => flash(cooldownStatus, 'Request error.', true));
        });
    }

    // --- IDLE BEHAVIOR LOGIC ---
    const idleEnabled = document.getElementById('idle-enabled');
    const idleInterval = document.getElementById('idle-interval');
    const idleDuration = document.getElementById('idle-duration');
    const btnSaveIdle = document.getElementById('btn-save-idle');
    const idleStatus = document.getElementById('idle-status');

    function loadIdleBehavior() {
        fetch('/api/idle_behavior')
            .then(res => res.json())
            .then(data => {
                if (idleEnabled) idleEnabled.checked = !!data.enabled;
                if (idleInterval) idleInterval.value = data.interval_seconds;
                if (idleDuration) idleDuration.value = data.duration_seconds;
            })
            .catch(() => {
                if (idleStatus) idleStatus.textContent = 'Error loading idle behavior settings.';
            });
    }

    if (btnSaveIdle) {
        btnSaveIdle.addEventListener('click', function() {
            const enabled = !!idleEnabled.checked;
            const interval = parseInt(idleInterval.value, 10);
            const duration = parseInt(idleDuration.value, 10);
            fetch('/api/idle_behavior', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled, interval_seconds: interval, duration_seconds: duration })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    flash(idleStatus, 'Idle behavior saved');
                } else {
                    flash(idleStatus, data.error || 'Failed to update idle behavior.', true);
                }
            })
            .catch(() => flash(idleStatus, 'Request error.', true));
        });
    }

    // Initial data loads
    loadStatus(); // This will also trigger initial volume load if needed
    loadAudioFiles();
    loadWiFiNetworks(); // Load WiFi networks on page load

    // Call loadCooldown on page load
    loadCooldown();

    // Call loadIdleBehavior on page load
    loadIdleBehavior();

    function generateTimestamps(filename, statusEl) {
        console.log("generateTimestamps called for:", filename);
        if (!filename) return;

        // Attempt to select the specific button to give visual feedback
        const generateButton = audioFileList.querySelector(`.btn-generate-timestamps[data-filename="${filename}"]`);
        const originalButtonText = generateButton ? generateButton.textContent : '';

        if(generateButton) {
            generateButton.disabled = true;
            generateButton.textContent = 'Generating...';
        }

        // Use 'uploadStatus' for messages, assuming it exists and is suitable
        const statusElement = statusEl || audioFilesMsg;

        fetch(`/api/audio/generate_timestamps/${encodeURIComponent(filename)}`, { 
            method: 'POST'
        })
        .then(res => {
            if (!res.ok) { // Check for non-2xx responses
                return res.json().then(errData => {
                    throw { status: res.status, data: errData }; // Throw an object to be caught
                });
            }
            return res.json();
        })
        .then(data => {
            if (data.success) {
                flash(statusElement, `Timestamps generated for ${filename}`);
                loadAudioFiles(); // Refresh list to show new timestamp status
                loadStatus(); // Also refresh general status
            } else {
                // data.error should be primary, data.details for more specifics
                const errorMessage = `Error: ${data.error || 'Failed to generate timestamps.'} ${data.details ? 'Details: ' + data.details : ''}`;
                flash(statusElement, errorMessage, true);
                console.error("Timestamp generation failed:", data);
            }
        })
        .catch(error => {
            let errorMessage = 'Request error generating timestamps.';
            if (error.status && error.data && error.data.error) { // From our custom thrown error
                 errorMessage = `Error ${error.status}: ${error.data.error}. ${error.data.details ? 'Details: ' + error.data.details : ''}`;
            } else if (error.message) { // Standard JS error
                errorMessage += ` ${error.message}`;
            }
            
            flash(statusElement, errorMessage, true);
            console.error("Timestamp generation request failed:", error);
        })
        .finally(() => {
            if(generateButton) {
                generateButton.disabled = false;
                generateButton.textContent = originalButtonText; 
            }
        });
    }

    // --- NETWORK TRIGGERS UI LOGIC ---
    async function loadTriggers() {
        if (!tableTriggers) return;
        try {
            const res = await fetch('/api/network_triggers');
            const data = await res.json();
            const filesRes = await fetch('/api/audio/files');
            const filesData = await filesRes.json();
            const fileMap = new Map(filesData.files.map(f => [f.filename, f]));
            const pools = await fetchPools();
            // Clear only now: loads overlap (several cards refresh each other), and clearing
            // before the awaits let two of them each append a full set of rows.
            tableTriggers.innerHTML = '';
            if (!(data.triggers || []).length) {
                tableTriggers.innerHTML = '<p class="form-text">No network triggers yet.</p>';
            }
            const mkField = (label, control, extra) => {
                const col = document.createElement('div');
                const l = document.createElement('label');
                l.textContent = label;
                col.appendChild(l);
                col.appendChild(control);
                if (extra) col.appendChild(extra);
                return col;
            };
            (data.triggers || []).forEach(tr => {
                const box = document.createElement('div');
                box.className = 'trigger-box';

                // Header: name, enabled, short id
                const head = document.createElement('div');
                head.className = 'trigger-head';
                const inputName = document.createElement('input');
                inputName.type = 'text';
                inputName.value = tr.name || '';
                inputName.setAttribute('aria-label', 'Trigger name');
                const enabledWrap = document.createElement('label');
                enabledWrap.className = 'trigger-enabled';
                const chkEnabled = document.createElement('input');
                chkEnabled.type = 'checkbox';
                chkEnabled.checked = !!tr.enabled;
                enabledWrap.appendChild(chkEnabled);
                enabledWrap.appendChild(document.createTextNode(' Enabled'));
                const codeId = document.createElement('code');
                codeId.textContent = String(tr.id).slice(0, 8);
                codeId.title = tr.id;
                head.appendChild(inputName);
                head.appendChild(enabledWrap);
                head.appendChild(codeId);
                box.appendChild(head);

                // Settings grid
                const grid = document.createElement('div');
                grid.className = 'trigger-grid';
                const selectAction = document.createElement('select');
                [['play', 'Play audio'], ['advance', 'Advance Step'], ['auto', 'Return to Automatic']].forEach(([v, t]) => {
                    const o = document.createElement('option');
                    o.value = v; o.textContent = t;
                    if ((tr.action || 'play') === v) o.selected = true;
                    selectAction.appendChild(o);
                });
                const selectAudio = document.createElement('select');
                fillAudioOptions(selectAudio, filesData, pools, tr.pool_id || (tr.audio_file ? 'file:' + tr.audio_file : ''), null);
                const tsNote = document.createElement('div');
                tsNote.className = 'form-text';
                const syncState = () => {
                    const isPlay = selectAction.value === 'play';
                    selectAudio.disabled = !isPlay;
                    const info = selectAudio.value.startsWith('file:') ? fileMap.get(selectAudio.value.slice(5)) : null;
                    tsNote.innerHTML = '';
                    if (isPlay && info && !info.has_timestamps) {
                        const btnGen = document.createElement('button');
                        btnGen.type = 'button';
                        btnGen.className = 'btn btn-sm btn-info';
                        btnGen.textContent = 'Gen Timestamps';
                        btnGen.addEventListener('click', () => generateTimestamps(info.filename, triggerStatus));
                        tsNote.appendChild(btnGen);
                    }
                };
                selectAction.addEventListener('change', syncState);
                selectAudio.addEventListener('change', syncState);
                syncState();
                grid.appendChild(mkField('Action', selectAction));
                grid.appendChild(mkField('Audio', selectAudio, tsNote));
                box.appendChild(grid);

                // Buttons
                const actions = document.createElement('div');
                actions.className = 'btn-row';
                const mkBtn = (label, cls, onClick) => {
                    const b = document.createElement('button');
                    b.type = 'button';
                    b.className = 'btn btn-sm ' + cls;
                    b.textContent = label;
                    b.addEventListener('click', onClick);
                    actions.appendChild(b);
                };
                mkBtn('Save', 'btn-success', async () => {
                    try {
                        const payload = { name: inputName.value, action: selectAction.value, enabled: chkEnabled.checked };
                        if (selectAction.value === 'play') {
                            if (selectAudio.value.startsWith('file:')) { payload.audio_file = selectAudio.value.slice(5); payload.pool_id = ''; }
                            else payload.pool_id = selectAudio.value;
                        }
                        const resp = await fetch(`/api/network_triggers/${tr.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                        const result = await resp.json();
                        if (resp.ok && result.success) {
                            displayTriggerMessage('Trigger saved');
                            loadTriggers();
                            loadAudioFiles();
                        } else {
                            displayTriggerMessage(result.error || 'Failed to save trigger', true);
                        }
                    } catch (e) { displayTriggerMessage('Save failed', true); }
                });
                mkBtn('Test', 'btn-secondary', async () => {
                    try {
                        const resp = await fetch(`/api/network_triggers/${tr.id}/fire`, { method: 'POST' });
                        const result = await resp.json();
                        if (resp.ok && result.success) { displayTriggerMessage('Trigger fired'); refreshNow(); }
                        else displayTriggerMessage(result.message || result.error || 'Busy/failed', true);
                    } catch (e) { displayTriggerMessage('Fire failed', true); }
                });
                mkBtn('Copy ID', 'btn-secondary', async () => {
                    const ok = await copyToClipboard(tr.id);
                    displayTriggerMessage(ok ? 'ID copied' : 'Copy failed', !ok);
                });
                mkBtn('Copy URL', 'btn-secondary', async () => {
                    try {
                        const host = window.location.hostname || 'ghosthost.local';
                        const url = `http://${host}:${data.port}/api/trigger/${tr.id}/play`;
                        const ok = await copyToClipboard(url);
                        displayTriggerMessage(ok ? 'URL copied' : 'Copy failed', !ok);
                    } catch (e) { displayTriggerMessage('Copy failed', true); }
                });
                mkBtn('Delete', 'btn-danger', async () => {
                    if (!confirm('Delete this trigger?')) return;
                    try {
                        const resp = await fetch(`/api/network_triggers/${tr.id}`, { method: 'DELETE' });
                        const result = await resp.json();
                        if (resp.ok && result.success) { displayTriggerMessage('Trigger deleted'); loadTriggers(); }
                        else displayTriggerMessage(result.error || 'Delete failed', true);
                    } catch (e) { displayTriggerMessage('Delete failed', true); }
                });
                box.appendChild(actions);
                tableTriggers.appendChild(box);
            });
        } catch (e) {
            console.error('Failed to load triggers', e);
        }
    }

    // Shared by the Add forms: label + control in the same grid the saved cards use
    function formField(label, control) {
        const col = document.createElement('div');
        const l = document.createElement('label');
        l.textContent = label;
        col.appendChild(l);
        col.appendChild(control);
        return col;
    }
    function formButtons(createLabel, onCreate, onCancel) {
        const row = document.createElement('div');
        row.className = 'btn-row';
        const create = document.createElement('button');
        create.type = 'button'; create.className = 'btn btn-sm btn-success'; create.textContent = createLabel;
        create.addEventListener('click', onCreate);
        const cancel = document.createElement('button');
        cancel.type = 'button'; cancel.className = 'btn btn-sm btn-secondary'; cancel.textContent = 'Cancel';
        cancel.addEventListener('click', onCancel);
        row.appendChild(create); row.appendChild(cancel);
        return row;
    }

    if (btnAddTrigger) {
        const form = document.getElementById('trigger-add-form');
        const close = () => { form.hidden = true; form.innerHTML = ''; btnAddTrigger.disabled = false; };
        btnAddTrigger.addEventListener('click', async () => {
            let filesData, poolsData;
            try {
                filesData = await (await fetch('/api/audio/files')).json();
                poolsData = await fetchPools();
            } catch (e) { displayTriggerMessage('Could not load audio files', true); return; }
            if (!(filesData.files || []).length) { displayTriggerMessage('No audio files available. Upload one on the Media tab first.', true); return; }
            btnAddTrigger.disabled = true;
            form.innerHTML = '';
            const name = document.createElement('input');
            name.type = 'text'; name.value = 'New Trigger'; name.setAttribute('aria-label', 'Trigger name');
            const action = document.createElement('select');
            [['play', 'Play audio'], ['advance', 'Advance Step'], ['auto', 'Return to Automatic']].forEach(([v, t]) => {
                const o = document.createElement('option'); o.value = v; o.textContent = t; action.appendChild(o);
            });
            const audio = document.createElement('select');
            fillAudioOptions(audio, filesData, poolsData, 'file:' + filesData.files[0].filename, null);
            const secret = document.createElement('input');
            secret.type = 'text'; secret.placeholder = 'Optional';
            action.addEventListener('change', () => { audio.disabled = action.value !== 'play'; });
            const grid = document.createElement('div');
            grid.className = 'trigger-grid';
            grid.appendChild(formField('Name', name));
            grid.appendChild(formField('Action', action));
            grid.appendChild(formField('Audio', audio));
            grid.appendChild(formField('Secret (callers must send it)', secret));
            form.appendChild(grid);
            form.appendChild(formButtons('Create trigger', async () => {
                const payload = { name: name.value.trim() || 'New Trigger', action: action.value, secret: secret.value, enabled: true };
                if (action.value === 'play') {
                    if (audio.value.startsWith('file:')) payload.audio_file = audio.value.slice(5);
                    else { payload.pool_id = audio.value; payload.audio_file = filesData.files[0].filename; }
                }
                const { ok, result } = await postJson('/api/network_triggers', payload);
                if (ok) { close(); displayTriggerMessage('Trigger created'); loadTriggers(); }
                else displayTriggerMessage(result.error || 'Create failed', true);
            }, close));
            form.hidden = false;
            name.focus(); name.select();
        });
    }

    // --- GREETING POOLS LOGIC ---
    const poolList = document.getElementById('pool-list');
    const poolStatus = document.getElementById('pool-status');
    const btnAddPool = document.getElementById('btn-add-pool');

    function displayPoolMessage(message, isError = false) {
        if (!poolStatus) return;
        poolStatus.textContent = message;
        poolStatus.className = 'form-text mb-2 ' + (isError ? 'text-danger' : 'text-success');
        setTimeout(() => { poolStatus.textContent = ''; }, 4000);
    }

    async function fetchPools() {
        try {
            const res = await fetch('/api/greeting_pools');
            return await res.json();
        } catch (e) {
            return { pools: [], sensor_pools: {} };
        }
    }

    function fillPoolOptions(select, poolsData, selectedId, noneLabel) {
        select.innerHTML = '';
        const none = document.createElement('option');
        none.value = '';
        none.textContent = noneLabel;
        select.appendChild(none);
        (poolsData.pools || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.name} (${(p.files || []).length})`;
            if (p.id === selectedId) opt.selected = true;
            select.appendChild(opt);
        });
        if ((poolsData.schedules || []).length) {
            const group = document.createElement('optgroup');
            group.label = 'Schedules';
            poolsData.schedules.forEach(sc => {
                const opt = document.createElement('option');
                opt.value = 'schedule:' + sc.id;
                opt.textContent = 'Schedule: ' + sc.name;
                if (opt.value === selectedId) opt.selected = true;
                group.appendChild(opt);
            });
            select.appendChild(group);
        }
    }

    // One dropdown for "what plays": audio files, pools and schedules in labelled groups.
    // Values: 'file:<name>' for a clip, a pool id, or 'schedule:<id>'; '' for noneLabel.
    function fillAudioOptions(select, filesData, poolsData, selected, noneLabel) {
        select.innerHTML = '';
        if (noneLabel) {
            const none = document.createElement('option');
            none.value = '';
            none.textContent = noneLabel;
            select.appendChild(none);
        }
        const group = (label, items) => {
            if (!items.length) return;
            const g = document.createElement('optgroup');
            g.label = label;
            items.forEach(([value, text]) => {
                const o = document.createElement('option');
                o.value = value;
                o.textContent = text;
                if (value === selected) o.selected = true;
                g.appendChild(o);
            });
            select.appendChild(g);
        };
        group('Pools (random or in order)', (poolsData.pools || []).map(p =>
            [p.id, 'Pool: ' + p.name + ' (' + (p.files || []).length + ' clips)']));
        group('Schedules (pool changes by time)', (poolsData.schedules || []).map(sc =>
            ['schedule:' + sc.id, 'Schedule: ' + sc.name]));
        group('Audio files', (filesData.files || []).map(f =>
            ['file:' + f.filename, f.description ? f.description + ' (' + f.filename + ')' : f.filename]));
    }

    async function loadPools() {
        if (!poolList) return;
        try {
            const poolsData = await fetchPools();
            const filesRes = await fetch('/api/audio/files');
            const filesData = await filesRes.json();
            poolList.innerHTML = '';
            (poolsData.pools || []).forEach(pool => {
                const box = document.createElement('div');
                box.className = 'border rounded p-3 mb-3';

                const nameGroup = document.createElement('div');
                nameGroup.className = 'input-group mb-2';
                const inputName = document.createElement('input');
                inputName.type = 'text';
                inputName.className = 'form-control';
                inputName.value = pool.name || '';
                nameGroup.appendChild(inputName);
                box.appendChild(nameGroup);

                const orderGroup = document.createElement('div');
                orderGroup.className = 'input-group input-group-sm mb-2';
                const orderLbl = document.createElement('span');
                orderLbl.className = 'input-group-text';
                orderLbl.textContent = 'Play order';
                const selectOrder = document.createElement('select');
                selectOrder.className = 'form-select';
                [['shuffle', 'Shuffle'], ['in_order', 'In order']].forEach(([v, t]) => {
                    const o = document.createElement('option');
                    o.value = v; o.textContent = t;
                    if ((pool.order || 'shuffle') === v) o.selected = true;
                    selectOrder.appendChild(o);
                });
                orderGroup.appendChild(orderLbl);
                orderGroup.appendChild(selectOrder);
                box.appendChild(orderGroup);

                const checks = [];
                filesData.files.forEach(f => {
                    const wrap = document.createElement('div');
                    wrap.className = 'form-check';
                    const chk = document.createElement('input');
                    chk.type = 'checkbox';
                    chk.className = 'form-check-input';
                    chk.value = f.filename;
                    chk.checked = (pool.files || []).includes(f.filename);
                    const lbl = document.createElement('label');
                    lbl.className = 'form-check-label';
                    lbl.textContent = f.filename;
                    if (!f.has_timestamps) {
                        const warn = document.createElement('span');
                        warn.className = 'badge bg-warning text-dark ms-2';
                        warn.textContent = 'No timestamps - mouth will not move';
                        lbl.appendChild(warn);
                    }
                    wrap.appendChild(chk);
                    wrap.appendChild(lbl);
                    box.appendChild(wrap);
                    checks.push(chk);
                });

                const actions = document.createElement('div');
                actions.className = 'mt-2';
                const btnSave = document.createElement('button');
                btnSave.className = 'btn btn-sm btn-success me-2';
                btnSave.textContent = 'Save Pool';
                btnSave.addEventListener('click', async () => {
                    try {
                        const payload = { name: inputName.value, order: selectOrder.value, files: checks.filter(c => c.checked).map(c => c.value) };
                        const resp = await fetch(`/api/greeting_pools/${pool.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                        const result = await resp.json();
                        if (resp.ok && result.success) { displayPoolMessage('Pool saved'); loadAudioFiles(); loadPools(); loadTriggers(); loadSchedules(); }
                        else displayPoolMessage(result.error || 'Save failed', true);
                    } catch (e) { displayPoolMessage('Save failed', true); }
                });
                const btnDelete = document.createElement('button');
                btnDelete.className = 'btn btn-sm btn-danger';
                btnDelete.textContent = 'Delete Pool';
                btnDelete.addEventListener('click', async () => {
                    if (!confirm('Delete this pool? Sensor ports and network triggers using it will go back to the default audio (or their own file), and timed triggers using it are switched off.')) return;
                    try {
                        const resp = await fetch(`/api/greeting_pools/${pool.id}`, { method: 'DELETE' });
                        const result = await resp.json();
                        if (resp.ok && result.success) { displayPoolMessage('Pool deleted'); loadAudioFiles(); loadPools(); loadTriggers(); loadSchedules(); }
                        else displayPoolMessage(result.error || 'Delete failed', true);
                    } catch (e) { displayPoolMessage('Delete failed', true); }
                });
                actions.appendChild(btnSave);
                actions.appendChild(btnDelete);
                box.appendChild(actions);
                poolList.appendChild(box);
            });

            // Sensor assignment selects
            document.querySelectorAll('select[data-sensor]').forEach(sel => {
                const sensor = sel.getAttribute('data-sensor');
                const defFile = (filesData.files || []).find(f => f.filename === filesData.default);
                const defLabel = filesData.default
                    ? 'Default audio: ' + (defFile && defFile.description ? defFile.description + ' (' + filesData.default + ')' : filesData.default)
                    : 'Default audio (none set)';
                fillAudioOptions(sel, filesData, poolsData, (poolsData.sensor_pools || {})[sensor], defLabel);
                sel.onchange = async () => {
                    try {
                        const resp = await fetch('/api/sensor_pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sensor, pool_id: sel.value }) });
                        const result = await resp.json();
                        if (resp.ok && result.success) flash(document.getElementById('sensor-msg'), 'Saved');
                        else flash(document.getElementById('sensor-msg'), result.error || 'Save failed', true);
                    } catch (e) { flash(document.getElementById('sensor-msg'), 'Save failed', true); }
                };
            });
        } catch (e) {
            console.error('Failed to load pools', e);
        }
    }

    if (btnAddPool) {
        btnAddPool.addEventListener('click', async () => {
            const nameInput = document.getElementById('new-pool-name');
            const name = (nameInput && nameInput.value.trim()) || 'New Pool';
            try {
                const resp = await fetch('/api/greeting_pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, files: [] }) });
                const result = await resp.json();
                if (resp.ok && result.success) { displayPoolMessage(`Pool '${name}' created - tick the greetings to include, then Save Pool`); if (nameInput) nameInput.value = ''; loadPools(); }
                else displayPoolMessage(result.error || 'Create failed', true);
            } catch (e) { displayPoolMessage('Create failed', true); }
        });
    }

    // Load pools on page load
    loadPools();

    // Load triggers on page load
    loadTriggers();

    // --- SCHEDULES LOGIC ---
    const scheduleList = document.getElementById('schedule-list');
    const scheduleMsg = document.getElementById('schedule-msg');
    const schedMsg = document.getElementById('sched-status-msg');

    function showMsg(el, message, isError = false) {
        if (!el) return;
        el.textContent = message;
        el.className = 'form-text ' + (isError ? 'text-danger' : 'text-success');
        setTimeout(() => { el.textContent = ''; }, 4000);
    }

    async function postJson(url, body, method = 'POST') {
        const resp = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
        let result = {};
        try { result = await resp.json(); } catch (e) {}
        return { ok: resp.ok && result.success, result };
    }

    async function loadSchedules() {
        if (!scheduleList) return;
        try {
            const poolsData = await fetchPools();
            const res = await fetch('/api/schedules');
            const data = await res.json();
            scheduleList.innerHTML = '';
            (data.schedules || []).forEach(sc => {
                const box = document.createElement('div');
                box.className = 'border rounded p-3 mb-3';

                const inputName = document.createElement('input');
                inputName.type = 'text';
                inputName.className = 'form-control mb-2';
                inputName.value = sc.name || '';
                box.appendChild(inputName);

                const opts = document.createElement('div');
                opts.className = 'row g-2 mb-2';
                const mkField = (label, input) => {
                    const col = document.createElement('div');
                    col.className = 'col-sm-6';
                    const l = document.createElement('label');
                    l.className = 'form-label form-text mb-0';
                    l.textContent = label;
                    col.appendChild(l);
                    col.appendChild(input);
                    opts.appendChild(col);
                };
                const inputDate = document.createElement('input');
                inputDate.type = 'date';
                inputDate.className = 'form-control form-control-sm';
                inputDate.value = sc.active_date || '';
                mkField('Active date (blank = every night)', inputDate);
                const inputRoll = document.createElement('input');
                inputRoll.type = 'time';
                inputRoll.className = 'form-control form-control-sm';
                inputRoll.value = sc.night_rollover || '06:00';
                mkField('Night rollover', inputRoll);
                box.appendChild(opts);

                const rowsDiv = document.createElement('div');
                box.appendChild(rowsDiv);
                const addRow = (step) => {
                    const row = document.createElement('div');
                    row.className = 'input-group input-group-sm mb-1';
                    const t = document.createElement('input');
                    t.type = 'time';
                    t.className = 'form-control';
                    t.value = step.at || '';
                    t.style.maxWidth = '9rem';
                    const sel = document.createElement('select');
                    sel.className = 'form-select';
                    (poolsData.pools || []).forEach(p => {
                        const o = document.createElement('option');
                        o.value = p.id; o.textContent = p.name;
                        if (p.id === step.pool_id) o.selected = true;
                        sel.appendChild(o);
                    });
                    const rm = document.createElement('button');
                    rm.type = 'button';
                    rm.className = 'btn btn-outline-danger';
                    rm.textContent = 'Remove';
                    rm.addEventListener('click', () => row.remove());
                    row.appendChild(t); row.appendChild(sel); row.appendChild(rm);
                    rowsDiv.appendChild(row);
                };
                (sc.steps || []).forEach(addRow);

                if (sc.missing_timestamps && sc.missing_timestamps.length) {
                    const warn = document.createElement('div');
                    warn.className = 'badge bg-warning text-dark mt-1';
                    warn.textContent = 'No timestamps: ' + sc.missing_timestamps.join(', ');
                    box.appendChild(warn);
                }

                const actions = document.createElement('div');
                actions.className = 'mt-2';
                const btnRow = document.createElement('button');
                btnRow.className = 'btn btn-sm btn-outline-primary me-2';
                btnRow.textContent = 'Add Step';
                btnRow.addEventListener('click', () => addRow({ at: '', pool_id: (poolsData.pools[0] || {}).id }));
                const btnSave = document.createElement('button');
                btnSave.className = 'btn btn-sm btn-success me-2';
                btnSave.textContent = 'Save Schedule';
                btnSave.addEventListener('click', async () => {
                    const steps = Array.from(rowsDiv.children).map(r => ({
                        at: r.querySelector('input').value, pool_id: r.querySelector('select').value }));
                    const { ok, result } = await postJson(`/api/schedules/${sc.id}`, {
                        name: inputName.value, active_date: inputDate.value,
                        night_rollover: inputRoll.value, steps }, 'PUT');
                    if (ok) { showMsg(scheduleMsg, 'Schedule saved'); loadSchedules(); loadStatus_schedule(); }
                    else showMsg(scheduleMsg, result.error || 'Save failed', true);
                });
                const btnDelete = document.createElement('button');
                btnDelete.className = 'btn btn-sm btn-danger';
                btnDelete.textContent = 'Delete Schedule';
                btnDelete.addEventListener('click', async () => {
                    if (!confirm('Delete this schedule? Sensor ports and network triggers using it will go back to the default audio, and timed triggers using it are switched off.')) return;
                    const resp = await fetch(`/api/schedules/${sc.id}`, { method: 'DELETE' });
                    const result = await resp.json();
                    if (resp.ok && result.success) { showMsg(scheduleMsg, 'Schedule deleted'); loadSchedules(); loadPools(); loadTriggers(); loadStatus_schedule(); }
                    else showMsg(scheduleMsg, result.error || 'Delete failed', true);
                });
                actions.appendChild(btnRow); actions.appendChild(btnSave); actions.appendChild(btnDelete);
                box.appendChild(actions);
                scheduleList.appendChild(box);
            });
            // Refresh assignment dropdowns that list schedules
            loadPools(); loadTriggers();
        } catch (e) {
            console.error('Failed to load schedules', e);
        }
    }

    const btnAddSchedule = document.getElementById('btn-add-schedule');
    if (btnAddSchedule) {
        btnAddSchedule.addEventListener('click', async () => {
            const nameInput = document.getElementById('new-schedule-name');
            const name = (nameInput && nameInput.value.trim()) || 'New Schedule';
            const { ok, result } = await postJson('/api/schedules', { name });
            if (ok) { showMsg(scheduleMsg, 'Schedule created - set its steps, then Save Schedule'); if (nameInput) nameInput.value = ''; loadSchedules(); }
            else showMsg(scheduleMsg, result.error || 'Create failed', true);
        });
    }

    // --- SCHEDULE STATUS LOGIC ---
    const BADGE = { synced: 'bg-success', manual: 'bg-info', test: 'bg-warning text-dark', unset: 'bg-danger' };

    async function loadStatus_schedule() {
        const timeEl = document.getElementById('sched-time');
        if (!timeEl) return;
        try {
            const res = await fetch('/api/schedule/status');
            const st = await res.json();
            timeEl.textContent = st.time;
            const badge = document.getElementById('sched-clock-badge');
            badge.textContent = st.clock_label;
            badge.className = 'badge ms-2 ' + (BADGE[st.clock_state] || 'bg-secondary');
            const ports = document.getElementById('sched-ports');
            ports.innerHTML = '';
            st.ports.forEach(p => {
                const line = document.createElement('div');
                const name = p.port === 'sensor_port_left' ? 'Left' : 'Right';
                const next = p.next_at ? `next step at ${p.next_at}` : (p.reason === 'time' ? 'last step' : p.reason);
                line.textContent = `${name} port, ${p.schedule}: ${p.pool || '?'} (since ${p.step_at}, ${next})`;
                ports.appendChild(line);
            });
            if (st.override_active) {
                const o = document.createElement('div');
                o.className = 'text-warning';
                o.textContent = 'Manual override active (clears after the night rollover)';
                ports.appendChild(o);
            }
            if (st.test_time) document.getElementById('sched-test-time').value = st.test_time;
        } catch (e) { console.error('Schedule status failed', e); }
    }

    function bindSched(id, fn) {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', fn);
    }
    const afterSched = (ok, result, okText) => {
        showMsg(schedMsg, ok ? okText : (result.error || 'Failed'), !ok);
        loadStatus_schedule();
    };
    bindSched('btn-sched-advance', async () => { const r = await postJson('/api/schedule/advance'); afterSched(r.ok, r.result, 'Advanced'); });
    bindSched('btn-sched-auto', async () => { const r = await postJson('/api/schedule/auto'); afterSched(r.ok, r.result, 'Back to automatic'); });
    bindSched('btn-clock-phone', async () => {
        const r = await postJson('/api/schedule/clock', { epoch: Math.round(Date.now() / 1000) });
        afterSched(r.ok, r.result, 'Clock set from this phone');
    });
    bindSched('btn-clock-manual', async () => {
        const v = document.getElementById('clock-manual-input').value;
        const r = await postJson('/api/schedule/clock', { datetime: v });
        afterSched(r.ok, r.result, 'Clock set');
    });
    bindSched('btn-test-time-set', async () => {
        const r = await postJson('/api/schedule/test_time', { test_time: document.getElementById('sched-test-time').value });
        afterSched(r.ok, r.result, 'Test time on');
    });
    bindSched('btn-test-time-clear', async () => {
        document.getElementById('sched-test-time').value = '';
        const r = await postJson('/api/schedule/test_time', { test_time: '' });
        afterSched(r.ok, r.result, 'Real time restored');
    });

    loadSchedules();
    loadStatus_schedule();
    setInterval(loadStatus_schedule, 15000);

    // --- TIMED TRIGGERS (Triggers tab) ---
    const timedList = document.getElementById('timed-list');
    const timedMsg = document.getElementById('timed-msg');
    const timedBadges = {};

    function timedStatusText(t) {
        const mins = n => (n >= 60 ? Math.floor(n / 60) + ' h ' + (n % 60) + ' min' : n + ' min');
        switch (t.status) {
            case 'waiting': return ['Waiting, in ' + mins(t.in_minutes), 'bg-info'];
            case 'due': return ['Due now, waiting for the prop to be free', 'bg-warning text-dark'];
            case 'played': return ['Played tonight at ' + (t.status_at || ''), 'bg-success'];
            case 'missed': return ['Skipped for tonight (its time passed)', 'bg-secondary'];
            case 'failed': return ['Failed: check the audio file', 'bg-danger'];
            case 'wrong_date': return ['Not tonight (set for ' + t.active_date + ')', 'bg-secondary'];
            default: return ['Off', 'bg-secondary'];
        }
    }

    function renderTimeline(items) {
        const el = document.getElementById('timed-timeline');
        if (!el) return;
        el.innerHTML = '';
        if (!items.length) { el.innerHTML = '<p class="form-text">Nothing scheduled yet.</p>'; return; }
        items.forEach(e => {
            const row = document.createElement('div');
            row.className = 'form-text';
            const what = e.kind === 'announce'
                ? 'plays ' + (e.detail || '?') + ' (' + e.label + ')'
                : 'sensors switch to pool ' + (e.detail || '?') + ' (' + e.label + ')';
            row.textContent = e.at + '  ' + what + (e.date ? '  [' + e.date + ' only]' : '');
            el.appendChild(row);
        });
    }

    async function pollTimed() {
        if (!timedList) return;
        let data;
        try { data = await (await fetch('/api/timed_triggers')).json(); } catch (e) { return; }
        const clock = document.getElementById('timed-clock');
        clock.textContent = data.clock_label;
        clock.className = 'badge ' + (BADGE[data.clock_state] || 'bg-secondary');
        document.getElementById('timed-time').textContent = data.clock_trusted
            ? 'The prop thinks it is ' + data.time : 'The clock is not set, so timed triggers will not fire.';
        document.getElementById('timed-wait-limit').textContent = data.wait_limit;
        (data.triggers || []).forEach(t => {
            const b = timedBadges[t.id];
            if (!b) return;
            const [text, cls] = timedStatusText(t);
            b.textContent = text;
            b.className = 'badge ' + cls;
        });
        renderTimeline(data.timeline || []);
        return data;
    }

    async function loadTimed() {
        if (!timedList) return;
        try {
            const poolsData = await fetchPools();
            const filesData = await (await fetch('/api/audio/files')).json();
            const data = await pollTimed();
            if (!data) return;
            timedList.innerHTML = '';
            Object.keys(timedBadges).forEach(k => delete timedBadges[k]);
            (data.triggers || []).forEach(t => {
                const box = document.createElement('div');
                box.className = 'border rounded p-3 mb-3';

                const name = document.createElement('input');
                name.type = 'text';
                name.className = 'form-control mb-2';
                name.value = t.name || '';
                box.appendChild(name);

                const row = document.createElement('div');
                row.className = 'row g-2 mb-2';
                const field = (label, input, cols) => {
                    const col = document.createElement('div');
                    col.className = cols;
                    const l = document.createElement('label');
                    l.className = 'form-label form-text mb-0';
                    l.textContent = label;
                    col.appendChild(l);
                    col.appendChild(input);
                    row.appendChild(col);
                };
                const time = document.createElement('input');
                time.type = 'time';
                time.className = 'form-control form-control-sm';
                time.value = t.time || '';
                field('Time', time, 'col-sm-3');

                const target = document.createElement('select');
                target.className = 'form-select form-select-sm';
                fillAudioOptions(target, filesData, poolsData, t.pool_id || (t.audio_file ? 'file:' + t.audio_file : ''), null);
                field('Plays', target, 'col-sm-6');

                const date = document.createElement('input');
                date.type = 'date';
                date.className = 'form-control form-control-sm';
                date.value = t.active_date || '';
                field('Only on (blank = every night)', date, 'col-sm-3');
                box.appendChild(row);

                const enabledWrap = document.createElement('label');
                enabledWrap.className = 'form-check mb-2';
                const enabled = document.createElement('input');
                enabled.type = 'checkbox';
                enabled.className = 'form-check-input';
                enabled.checked = t.enabled !== false;
                enabledWrap.appendChild(enabled);
                enabledWrap.appendChild(document.createTextNode(' Enabled'));
                box.appendChild(enabledWrap);

                const badge = document.createElement('span');
                timedBadges[t.id] = badge;
                const [text, cls] = timedStatusText(t);
                badge.textContent = text;
                badge.className = 'badge ' + cls;
                box.appendChild(badge);

                const actions = document.createElement('div');
                actions.className = 'mt-2';
                const mkBtn = (label, cls2, fn) => {
                    const b = document.createElement('button');
                    b.className = 'btn btn-sm ' + cls2 + ' me-2';
                    b.textContent = label;
                    b.addEventListener('click', fn);
                    actions.appendChild(b);
                };
                mkBtn('Save', 'btn-success', async () => {
                    const body = { name: name.value, time: time.value, active_date: date.value, enabled: enabled.checked };
                    if (target.value.startsWith('file:')) body.audio_file = target.value.slice(5);
                    else body.pool_id = target.value;
                    const { ok, result } = await postJson('/api/timed_triggers/' + t.id, body, 'PUT');
                    if (ok) { showMsg(timedMsg, 'Saved'); loadTimed(); }
                    else showMsg(timedMsg, result.error || 'Save failed', true);
                });
                mkBtn('Run now', 'btn-outline-primary', async () => {
                    const r = await fetch('/api/timed_triggers/' + t.id + '/run', { method: 'POST' });
                    let result = {};
                    try { result = await r.json(); } catch (e) {}
                    showMsg(timedMsg, result.success ? 'Playing now (a test: it does not count for tonight)' : (result.message || 'Failed'), !result.success);
                    refreshNow();
                });
                mkBtn('Delete', 'btn-danger', async () => {
                    if (!confirm('Delete this timed trigger?')) return;
                    const r = await fetch('/api/timed_triggers/' + t.id, { method: 'DELETE' });
                    const result = await r.json();
                    if (r.ok && result.success) { showMsg(timedMsg, 'Deleted'); loadTimed(); }
                    else showMsg(timedMsg, result.error || 'Delete failed', true);
                });
                box.appendChild(actions);
                timedList.appendChild(box);
            });
            if (!(data.triggers || []).length) timedList.innerHTML = '<p class="form-text">No timed triggers yet.</p>';
        } catch (e) {
            console.error('Failed to load timed triggers', e);
        }
    }

    const btnAddTimed = document.getElementById('btn-add-timed');
    if (btnAddTimed) {
        const form = document.getElementById('timed-add-form');
        const close = () => { form.hidden = true; form.innerHTML = ''; btnAddTimed.disabled = false; };
        btnAddTimed.addEventListener('click', async () => {
            let filesData, poolsData;
            try {
                filesData = await (await fetch('/api/audio/files')).json();
                poolsData = await fetchPools();
            } catch (e) { showMsg(timedMsg, 'Could not load audio files', true); return; }
            if (!(filesData.files || []).length) { showMsg(timedMsg, 'Upload an audio file on the Media tab first', true); return; }
            btnAddTimed.disabled = true;
            form.innerHTML = '';
            const name = document.createElement('input');
            name.type = 'text'; name.value = 'New Timed Trigger'; name.setAttribute('aria-label', 'Name');
            const time = document.createElement('input');
            time.type = 'time'; time.value = '20:00';
            const target = document.createElement('select');
            fillAudioOptions(target, filesData, poolsData, 'file:' + filesData.files[0].filename, null);
            const date = document.createElement('input');
            date.type = 'date';
            const grid = document.createElement('div');
            grid.className = 'trigger-grid';
            grid.appendChild(formField('Name', name));
            grid.appendChild(formField('Time', time));
            grid.appendChild(formField('Plays', target));
            grid.appendChild(formField('Only on (blank = every night)', date));
            form.appendChild(grid);
            form.appendChild(formButtons('Create timed trigger', async () => {
                const body = { name: name.value.trim() || 'Timed Trigger', time: time.value, active_date: date.value, enabled: true };
                if (target.value.startsWith('file:')) body.audio_file = target.value.slice(5);
                else body.pool_id = target.value;
                const { ok, result } = await postJson('/api/timed_triggers', body);
                if (ok) { close(); showMsg(timedMsg, 'Timed trigger created'); loadTimed(); loadShows(true); }
                else showMsg(timedMsg, result.error || 'Create failed', true);
            }, close));
            form.hidden = false;
            name.focus(); name.select();
        });
    }
    loadTimed();
    // Status only: re-rendering would wipe a row someone is editing
    setInterval(() => { if (!document.hidden) pollTimed(); }, 15000);
    document.querySelectorAll('nav.tabs a[data-tab="triggers"]').forEach(a => a.addEventListener('click', loadTimed));

    // --- SHOWS (Triggers tab) ---
    const showSelect = document.getElementById('show-select');
    const showMsg_ = document.getElementById('show-msg');
    let showsState = { shows: [], active_show: '' };

    function showSummaryText(sh) {
        const m = sh.summary || {};
        const parts = ['Default audio: ' + (m.default_file || 'none'), 'Left sensor: ' + m.left, 'Right sensor: ' + m.right];
        if (m.cooldown != null) parts.push('Cooldown: ' + m.cooldown + 's');
        parts.push((m.timed || []).length ? 'Timed: ' + m.timed.join(', ') : 'No timed triggers');
        return parts.join(' | ');
    }

    function paintShows(keepSelection) {
        const active = showsState.shows.find(x => x.id === showsState.active_show);
        const badge = document.getElementById('show-active');
        badge.textContent = active ? 'Active show: ' + active.name : 'No show saved yet (these settings are not saved as a show)';
        document.getElementById('show-modified').style.display = active && active.modified ? '' : 'none';
        const prev = keepSelection ? showSelect.value : '';
        showSelect.innerHTML = '';
        showsState.shows.forEach(sh => {
            const o = document.createElement('option');
            o.value = sh.id;
            o.textContent = sh.name + (sh.active ? ' (active)' : '');
            showSelect.appendChild(o);
        });
        showSelect.value = (prev && showsState.shows.some(x => x.id === prev)) ? prev : (showsState.active_show || (showsState.shows[0] || {}).id || '');
        const hasShows = showsState.shows.length > 0;
        ['btn-show-switch', 'btn-show-rename', 'btn-show-delete'].forEach(id => { document.getElementById(id).disabled = !hasShows; });
        document.getElementById('btn-show-save').disabled = !active;
        const sel = showsState.shows.find(x => x.id === showSelect.value);
        document.getElementById('show-summary').textContent = sel ? showSummaryText(sel) : '';
    }

    async function loadShows(keepSelection) {
        if (!showSelect) return;
        try { showsState = await (await fetch('/api/shows')).json(); } catch (e) { return; }
        paintShows(keepSelection);
    }

    if (showSelect) {
        showSelect.addEventListener('change', () => paintShows(true));
        const selected = () => showsState.shows.find(x => x.id === showSelect.value);

        document.getElementById('btn-show-new').addEventListener('click', async () => {
            const input = document.getElementById('new-show-name');
            const { ok, result } = await postJson('/api/shows', { name: input.value });
            if (ok) { input.value = ''; showMsg(showMsg_, 'Saved as a new show and made active'); loadShows(); loadTimed(); }
            else showMsg(showMsg_, result.error || 'Could not save', true);
        });
        document.getElementById('btn-show-save').addEventListener('click', async () => {
            const active = showsState.shows.find(x => x.id === showsState.active_show);
            if (!active) return;
            const { ok, result } = await postJson('/api/shows/' + active.id, { save: true }, 'PUT');
            if (ok) { showMsg(showMsg_, 'Saved to ' + active.name); loadShows(true); }
            else showMsg(showMsg_, result.error || 'Could not save', true);
        });
        document.getElementById('btn-show-switch').addEventListener('click', async () => {
            const sh = selected();
            if (!sh) return;
            const active = showsState.shows.find(x => x.id === showsState.active_show);
            if (active && active.modified && active.id !== sh.id &&
                !confirm('"' + active.name + '" has changes that are not saved. Switching will discard them. Switch anyway?')) return;
            const { ok, result } = await postJson('/api/shows/' + sh.id + '/activate');
            if (!ok) { showMsg(showMsg_, result.error || 'Could not switch', true); return; }
            if ((result.warnings || []).length) {
                try { sessionStorage.setItem('gh-show-notes', 'Switched to ' + sh.name + ', with notes: ' + result.warnings.join(' ')); } catch (e) {}
            }
            location.reload();   // every card on the tab reads settings the switch just changed
        });
        const renameRow = document.getElementById('show-rename-row');
        const renameInput = document.getElementById('show-rename-input');
        const closeRename = () => { renameRow.hidden = true; };
        document.getElementById('btn-show-rename').addEventListener('click', () => {
            const sh = selected();
            if (!sh) return;
            renameInput.value = sh.name;
            renameRow.hidden = false;
            renameInput.focus(); renameInput.select();
        });
        document.getElementById('btn-show-rename-cancel').addEventListener('click', closeRename);
        renameInput.addEventListener('keydown', e => {
            if (e.key === 'Enter') document.getElementById('btn-show-rename-save').click();
            if (e.key === 'Escape') closeRename();
        });
        document.getElementById('btn-show-rename-save').addEventListener('click', async () => {
            const sh = selected();
            if (!sh) return;
            const { ok, result } = await postJson('/api/shows/' + sh.id, { name: renameInput.value }, 'PUT');
            if (ok) { closeRename(); showMsg(showMsg_, 'Renamed'); loadShows(true); loadLive(); }
            else showMsg(showMsg_, result.error || 'Could not rename', true);
        });
        try {
            const notes = sessionStorage.getItem('gh-show-notes');
            if (notes) { sessionStorage.removeItem('gh-show-notes'); showMsg_.textContent = notes; showMsg_.className = 'form-text text-warning'; }
        } catch (e) {}
        document.getElementById('btn-show-delete').addEventListener('click', async () => {
            const sh = selected();
            if (!sh) return;
            if (!confirm('Delete the show "' + sh.name + '"? The current settings stay as they are.')) return;
            const resp = await fetch('/api/shows/' + sh.id, { method: 'DELETE' });
            const result = await resp.json();
            if (resp.ok && result.success) { showMsg(showMsg_, 'Deleted'); loadShows(); }
            else showMsg(showMsg_, result.error || 'Could not delete', true);
        });
        loadShows();
        // "Changed since saved" follows edits made in the cards below
        setInterval(() => { if (!document.hidden) loadShows(true); }, 10000);
        document.querySelectorAll('nav.tabs a[data-tab="triggers"]').forEach(a => a.addEventListener('click', () => loadShows(true)));
    }

    // --- LIVE TAB ---
    const liveMessages = document.getElementById('live-messages');
    function liveButton(container, title, sub, onPress) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'bigbtn';
        b.innerHTML = '<span></span><span class="sub"></span>';
        b.firstChild.textContent = title;
        const subEl = b.lastChild;
        subEl.textContent = sub || '';
        b.addEventListener('click', async () => {
            b.disabled = true;
            subEl.textContent = 'sending...';
            b.classList.remove('performed', 'busy', 'refused');
            let r;
            try { r = await onPress(); } catch (e) { r = { success: false, message: 'No answer from the prop' }; }
            b.disabled = false;
            b.classList.add(r.success ? 'performed' : (/active|cooldown/i.test(r.message || '') ? 'busy' : 'refused'));
            subEl.textContent = r.success ? 'playing' : (r.message || 'failed');
            setTimeout(() => { b.classList.remove('performed', 'busy', 'refused'); subEl.textContent = sub || ''; }, 6000);
            loadLiveStatus();
        });
        container.appendChild(b);
    }
    async function loadLive() {
        if (!liveMessages) return;
        let st;
        try { st = await (await fetch('/api/live/state')).json(); } catch (e) { return; }
        const post = (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());
        const empty = (el, text) => { el.innerHTML = ''; return !!(text && (el.innerHTML = '<p class="form-text">' + text + '</p>')); };
        const liveShow = document.getElementById('live-show');
        if (liveShow) liveShow.textContent = st.show ? 'Show: ' + st.show : '';
        liveMessages.innerHTML = '';
        if (!st.messages.length) empty(liveMessages, 'No messages yet. Tick "Live button" on a file in the Media tab.');
        st.messages.forEach(m => liveButton(liveMessages, m.description || m.filename, m.description ? m.filename : '', () => post('/api/live/play', { audio_file: m.filename })));
        const pools = document.getElementById('live-pools');
        pools.innerHTML = '';
        st.pools.forEach(p => liveButton(pools, p.name, p.count + ' clips', () => post('/api/live/play', { pool_id: p.id })));
        st.schedules.forEach(sc => liveButton(pools, 'Schedule: ' + sc.name, 'current step', () => post('/api/live/play', { pool_id: sc.id })));
        if (!st.pools.length) empty(pools, 'No pools yet.');
        const sensors = document.getElementById('live-sensors');
        sensors.innerHTML = '';
        st.sensors.forEach(sn => liveButton(sensors, 'Run ' + sn.label, 'plays: ' + sn.assigned, () => post('/api/live/sensor', { sensor: sn.id })));
    }
    async function loadLiveStatus() {
        const badge = document.getElementById('live-state');
        if (!badge) return;
        try {
            const h = await refreshNow();
            if (!h) return;
            let text = 'Idle', cls = 'bg-primary';
            if (!h.controller_up) { text = 'Prop not responding'; cls = 'bg-danger'; }
            else if (h.performing) { text = 'Speaking'; cls = 'bg-info'; }
            else if (h.cooling_down) { text = 'Cooldown ' + Math.ceil(h.cooldown_remaining) + 's'; cls = 'bg-warning'; }
            badge.textContent = text;
            badge.className = 'badge ' + cls;
        } catch (e) {}
    }
    const btnLiveStop = document.getElementById('btn-live-stop');
    if (btnLiveStop) btnLiveStop.addEventListener('click', async () => {
        await stopProp();
        loadLiveStatus();
    });
    loadLive();
    loadLiveStatus();
    // Poll only while the tab is visible: this page sits open on a phone all evening
    setInterval(() => { if (!document.hidden) loadLiveStatus(); }, 2000);
    document.querySelectorAll('nav.tabs a[data-tab="live"]').forEach(a => a.addEventListener('click', loadLive));

    // --- SENSOR TEST (Live tab) ---
    // Polls only while the Live tab is showing: the pin poll runs on the Pi's own
    // 20ms thread, so brief PIR pulses are kept in its edge log and fetched by sequence.
    const sensorTestPorts = document.getElementById('sensor-test-ports');
    if (sensorTestPorts) {
        const logEl = document.getElementById('sensor-test-log');
        const silent = document.getElementById('sensor-test-silent');
        const silentNote = document.getElementById('sensor-test-silent-note');
        const labels = { sensor_port_left: 'Left port', sensor_port_right: 'Right port' };
        let lastSeq = null, logStarted = false;
        const tabVisible = () => !document.hidden && sensorTestPorts.closest('.tab-pane').classList.contains('active');
        async function pollSensorTest() {
            if (!tabVisible()) return;
            let d;
            try { d = await (await fetch('/api/live/sensors?since=' + (lastSeq || 0))).json(); } catch (e) { return; }
            if (!d.success) return;
            Object.keys(d.levels).forEach(name => {
                let el = document.getElementById('sensor-led-' + name);
                if (!el) {
                    el = document.createElement('div');
                    el.id = 'sensor-led-' + name;
                    el.className = 'sensor-led';
                    el.innerHTML = '<span class="dot"></span><div><div class="name"></div><div class="sub"></div></div>';
                    sensorTestPorts.appendChild(el);
                }
                const lv = d.levels[name];
                el.classList.toggle('high', lv.level === 1);
                el.querySelector('.name').textContent = (labels[name] || name) + ': ' + (lv.level ? 'HIGH' : 'LOW');
                el.querySelector('.sub').textContent = 'GPIO' + lv.pin;
            });
            // First poll only sets the baseline; old edges are not news
            if (lastSeq !== null) {
                d.events.forEach(e => {
                    if (!logStarted) { logEl.innerHTML = ''; logStarted = true; }
                    const row = document.createElement('div');
                    row.textContent = new Date(e.time * 1000).toLocaleTimeString() + '  ' + (labels[e.sensor] || e.sensor) + ' -> ' + (e.level ? 'HIGH' : 'LOW');
                    logEl.insertBefore(row, logEl.firstChild);
                });
                while (logEl.children.length > 50) logEl.removeChild(logEl.lastChild);
            }
            lastSeq = d.seq;
            silent.checked = !!d.test_mode;
            silentNote.textContent = d.test_mode ? '(ends in ' + d.test_mode_remaining + 's)' : '';
        }
        silent.addEventListener('change', async () => {
            await fetch('/api/live/sensor_test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ on: silent.checked }) });
            pollSensorTest();
        });
        setInterval(pollSensorTest, 500);
        pollSensorTest();
    }

    // --- DASHBOARD HEALTH ---
    async function loadHealth() {
        const grid = document.getElementById('health-grid');
        if (!grid) return;
        let h;
        try { h = await (await fetch('/api/health')).json(); } catch (e) { return; }
        const fmtUp = s => { const d = Math.floor(s / 86400), hr = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + 'd ' : '') + hr + 'h ' + m + 'm'; };
        let show = 'Idle', cls = 'bg-primary';
        if (!h.controller_up) { show = 'Controller not responding'; cls = 'bg-danger'; }
        else if (h.performing) { show = 'Performing'; cls = 'bg-info'; }
        else if (h.cooling_down) { show = `Cooldown ${Math.ceil(h.cooldown_remaining)}s`; cls = 'bg-warning'; }
        const items = [
            ['Prop', `<span class="badge ${cls}">${show}</span>`],
            ['Pi uptime', h.uptime_seconds != null ? fmtUp(h.uptime_seconds) : '--'],
            ['CPU temp', h.cpu_temp_c != null ? h.cpu_temp_c.toFixed(1) + ' C' : '--'],
            ['Memory used', h.mem_used_pct != null ? h.mem_used_pct + '%' : '--'],
            ['Disk used', h.disk_used_pct != null ? h.disk_used_pct + '%' : '--'],
            ['Audio files', h.audio_files],
            ['Files w/o timestamps', h.missing_timestamps],
            ['Default audio', h.default_audio || '--'],
        ];
        grid.innerHTML = '';
        items.forEach(([k, v]) => {
            const d = document.createElement('div');
            d.className = 'stat';
            d.innerHTML = '<div class="k"></div><div class="v"></div>';
            d.firstChild.textContent = k;
            d.lastChild.innerHTML = v;
            grid.appendChild(d);
        });
    }
    loadHealth();
    setInterval(loadHealth, 10000);
});
