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

    // Fetch and display audio files
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
                
                data.files.forEach(fileInfo => {
                    const { filename, is_default, has_timestamps } = fileInfo;
                    if (audioFileList) {
                        const li = document.createElement('li');
                        li.className = 'list-group-item d-flex justify-content-between align-items-center flex-wrap';
                        
                        let fileLabel = filename;
                        if (is_default) {
                            fileLabel += ' <span class="badge bg-primary ms-1">Default</span>';
                        }
                        
                        const fileSpan = document.createElement('span');
                        fileSpan.innerHTML = fileLabel; // Use innerHTML for badges

                        const buttonGroup = document.createElement('div');
                        buttonGroup.className = 'btn-group mt-1 mt-md-0'; // Responsive margin

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

                        const delBtn = document.createElement('button');
                        delBtn.className = 'btn btn-sm btn-danger btn-delete-audio';
                        delBtn.textContent = 'Delete';
                        delBtn.dataset.filename = filename;
                        delBtn.onclick = function() { deleteAudioFile(filename); };
                        buttonGroup.appendChild(delBtn);

                        li.appendChild(fileSpan);
                        li.appendChild(buttonGroup);
                        audioFileList.appendChild(li);
                    }

                    if (selectDefaultAudio) {
                        const opt = document.createElement('option');
                        opt.value = filename;
                        opt.textContent = filename;
                        if (is_default) opt.selected = true;
                        selectDefaultAudio.appendChild(opt);
                    }
                });
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
        if (!filename) { alert("Please select an audio file."); return; }
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
            } else {
                alert(data.error || 'Failed to set default audio.');
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
                loadAudioFiles();
            } else {
                alert(data.error || 'Failed to delete file.');
            }
        })
        .catch(err => alert(`Error deleting file: ${err}`))
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
            } else {
                alert(data.error || 'Failed to set volume');
            }
        });
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
                        alert(data.message || 'System is rebooting. This page will become unresponsive.');
                        // Disable UI as system goes down
                        document.body.innerHTML = '<div class="container mt-5 alert alert-info"><h1>Rebooting...</h1><p>Please wait for the system to restart. You may need to manually refresh this page after a few minutes.</p></div>';
                    } else {
                        alert(data.message || 'Reboot failed.');
                    }
                })
                .catch(err => {
                    alert('Failed to send reboot command: ' + err);
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
                    if (cooldownStatus) cooldownStatus.textContent = 'Cooldown updated!';
                } else {
                    if (cooldownStatus) cooldownStatus.textContent = data.error || 'Failed to update cooldown.';
                }
            })
            .catch(() => {
                if (cooldownStatus) cooldownStatus.textContent = 'Request error.';
            });
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
                    if (idleStatus) idleStatus.textContent = 'Idle behavior settings updated!';
                } else {
                    if (idleStatus) idleStatus.textContent = data.error || 'Failed to update idle behavior.';
                }
            })
            .catch(() => {
                if (idleStatus) idleStatus.textContent = 'Request error.';
            });
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

    function generateTimestamps(filename) {
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
        const statusElement = document.getElementById('upload-status'); 

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
                if (statusElement) displayMessage(statusElement, `Timestamps generated for ${filename}. Output: ${data.output || ''}`, true);
                else alert(`Timestamps generated for ${filename}.`);
                loadAudioFiles(); // Refresh list to show new timestamp status
                loadStatus(); // Also refresh general status
            } else {
                // data.error should be primary, data.details for more specifics
                const errorMessage = `Error: ${data.error || 'Failed to generate timestamps.'} ${data.details ? 'Details: ' + data.details : ''}`;
                if (statusElement) displayMessage(statusElement, errorMessage, false);
                else alert(errorMessage);
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
            
            if (statusElement) displayMessage(statusElement, errorMessage, false);
            else alert(errorMessage);
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
            const tbody = tableTriggers.querySelector('tbody');
            tbody.innerHTML = '';
            const filesRes = await fetch('/api/audio/files');
            const filesData = await filesRes.json();
            const fileMap = new Map(filesData.files.map(f => [f.filename, f]));
            (data.triggers || []).forEach(tr => {
                const row = document.createElement('tr');
                // Name
                const tdName = document.createElement('td');
                const inputName = document.createElement('input');
                inputName.type = 'text';
                inputName.className = 'form-control form-control-sm';
                inputName.value = tr.name || '';
                tdName.appendChild(inputName);
                row.appendChild(tdName);
                // Audio select
                const tdAudio = document.createElement('td');
                const selectAudio = document.createElement('select');
                selectAudio.className = 'form-select form-select-sm';
                filesData.files.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.filename;
                    opt.textContent = f.filename;
                    if (f.filename === tr.audio_file) opt.selected = true;
                    selectAudio.appendChild(opt);
                });
                tdAudio.appendChild(selectAudio);
                row.appendChild(tdAudio);
                // Timestamp column
                const tdTs = document.createElement('td');
                const info = fileMap.get(tr.audio_file);
                if (info && info.has_timestamps) {
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-info';
                    badge.textContent = 'Has Timestamps';
                    tdTs.appendChild(badge);
                } else {
                    const btnGen = document.createElement('button');
                    btnGen.className = 'btn btn-sm btn-info';
                    btnGen.textContent = 'Gen Timestamps';
                    btnGen.addEventListener('click', () => generateTimestamps(selectAudio.value));
                    tdTs.appendChild(btnGen);
                }
                row.appendChild(tdTs);
                // Enabled toggle
                const tdEnabled = document.createElement('td');
                const chkEnabled = document.createElement('input');
                chkEnabled.type = 'checkbox';
                chkEnabled.className = 'form-check-input';
                chkEnabled.checked = !!tr.enabled;
                tdEnabled.appendChild(chkEnabled);
                row.appendChild(tdEnabled);
                // ID column
                const tdId = document.createElement('td');
                const codeId = document.createElement('code');
                codeId.textContent = tr.id;
                tdId.appendChild(codeId);
                row.appendChild(tdId);
                // Actions (Save + dropdown for others)
                const tdActions = document.createElement('td');
                const btnSave = document.createElement('button');
                btnSave.className = 'btn btn-sm btn-success me-2';
                btnSave.textContent = 'Save';
                btnSave.addEventListener('click', async () => {
                    try {
                        const payload = { name: inputName.value, audio_file: selectAudio.value, enabled: chkEnabled.checked };
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
                const group = document.createElement('div');
                group.className = 'btn-group';
                const btnMore = document.createElement('button');
                btnMore.type = 'button';
                btnMore.className = 'btn btn-sm btn-secondary dropdown-toggle';
                btnMore.setAttribute('data-bs-toggle', 'dropdown');
                btnMore.textContent = 'More';
                const menu = document.createElement('ul');
                menu.className = 'dropdown-menu';
                const mkItem = (label, onClick, isDanger=false) => {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    a.href = '#';
                    a.className = 'dropdown-item' + (isDanger ? ' text-danger' : '');
                    a.textContent = label;
                    a.addEventListener('click', (e) => { e.preventDefault(); onClick(); });
                    li.appendChild(a);
                    return li;
                };
                menu.appendChild(mkItem('Test Trigger', async () => {
                    try {
                        const resp = await fetch(`/api/network_triggers/${tr.id}/fire`, { method: 'POST' });
                        const result = await resp.json();
                        if (resp.ok && result.success) displayTriggerMessage('Trigger fired');
                        else displayTriggerMessage(result.message || result.error || 'Busy/failed', true);
                    } catch (e) { displayTriggerMessage('Fire failed', true); }
                }));
                menu.appendChild(mkItem('Copy ID', async () => {
                    const ok = await copyToClipboard(tr.id);
                    displayTriggerMessage(ok ? 'ID copied' : 'Copy failed', !ok);
                }));
                menu.appendChild(mkItem('Copy URL', async () => {
                    try {
                        const portRes = await fetch('/api/network_triggers');
                        const portData = await portRes.json();
                        const host = window.location.hostname || 'ghosthost.local';
                        const url = `http://${host}:${portData.port}/api/trigger/${tr.id}/play`;
                        const ok = await copyToClipboard(url);
                        displayTriggerMessage(ok ? 'URL copied' : 'Copy failed', !ok);
                    } catch (e) { displayTriggerMessage('Copy failed', true); }
                }));
                menu.appendChild(mkItem('Delete', async () => {
                    if (!confirm('Delete this trigger?')) return;
                    try {
                        const resp = await fetch(`/api/network_triggers/${tr.id}`, { method: 'DELETE' });
                        const result = await resp.json();
                        if (resp.ok && result.success) { displayTriggerMessage('Trigger deleted'); loadTriggers(); }
                        else displayTriggerMessage(result.error || 'Delete failed', true);
                    } catch (e) { displayTriggerMessage('Delete failed', true); }
                }, true));
                group.appendChild(btnMore);
                group.appendChild(menu);
                tdActions.appendChild(btnSave);
                tdActions.appendChild(group);
                row.appendChild(tdActions);
                tbody.appendChild(row);
            });
        } catch (e) {
            console.error('Failed to load triggers', e);
        }
    }

    if (btnAddTrigger) {
        btnAddTrigger.addEventListener('click', async () => {
            try {
                const filesRes = await fetch('/api/audio/files');
                const filesData = await filesRes.json();
                const defaultAudio = (filesData.files && filesData.files[0] && filesData.files[0].filename) || null;
                if (!defaultAudio) { displayTriggerMessage('No audio files available. Upload first.', true); return; }
                const name = prompt('Enter trigger name:', 'New Trigger');
                if (name === null) return;
                const audio = prompt('Enter audio filename to assign (exact name):', defaultAudio);
                if (audio === null) return;
                const secret = prompt('Optional secret (leave blank for none):', '');
                const payload = { name, audio_file: audio, secret: secret || '', enabled: true };
                const resp = await fetch('/api/network_triggers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const result = await resp.json();
                if (resp.ok && result.success) { displayTriggerMessage('Trigger created'); loadTriggers(); }
                else displayTriggerMessage(result.error || 'Create failed', true);
            } catch (e) { displayTriggerMessage('Create failed', true); }
        });
    }

    // Load triggers on page load
    loadTriggers();
}); 