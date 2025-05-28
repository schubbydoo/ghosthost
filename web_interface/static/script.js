// Custom JavaScript for Ghost Host 

// Audio Management Logic for Ghost Host

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const audioFileList = document.getElementById('audio-file-list');
    const selectDefaultAudio = document.getElementById('select-default-audio');
    const btnSetDefaultAudio = document.getElementById('btn-set-default-audio');
    const audioUpload = document.getElementById('audio-upload');
    const btnUploadAudio = document.getElementById('btn-upload-audio');
    const uploadStatus = document.getElementById('upload-status');
    const audioVolume = document.getElementById('audio-volume');
    const audioVolumeValue = document.getElementById('audio-volume-value');
    const btnSetVolume = document.getElementById('btn-set-volume');
    const currentDefaultAudio = document.getElementById('current-default-audio');
    const currentVolume = document.getElementById('current-volume');

    // --- STATUS SECTION LOGIC ---
    const statusNetwork = document.getElementById('status-network');
    const statusIp = document.getElementById('status-ip');

    function updateStatusUI(data) {
        // Network (use config default if not present)
        if (data.current_network) {
            statusNetwork.textContent = data.current_network;
        } else {
            statusNetwork.textContent = 'Homenet1';
        }
        // IP Address
        if (data.ip_address) {
            statusIp.textContent = data.ip_address;
        } else {
            statusIp.textContent = '192.168.128.105';
        }
    }

    function loadStatus() {
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                updateStatusUI(data);
            })
            .catch(() => {
                // If backend is not running, show defaults
                updateStatusUI({});
            });
    }

    // Fetch and display audio files
    function loadAudioFiles() {
        fetch('/api/audio/files')
            .then(res => res.json())
            .then(data => {
                // Populate file list
                audioFileList.innerHTML = '';
                data.files.forEach(fileInfo => {
                    const { filename, is_default, has_timestamps } = fileInfo;
                    const li = document.createElement('li');
                    li.className = 'list-group-item d-flex justify-content-between align-items-center';
                    let label = filename;
                    if (is_default) {
                        label += ' <span class="badge bg-primary ms-2">Default</span>';
                        li.classList.add('list-group-item-success');
                    }
                    if (has_timestamps) {
                        label += ' <span class="badge bg-info ms-2">Timestamps</span>';
                    } else {
                        label += ' <span class="badge bg-secondary ms-2">No Timestamps</span>';
                    }
                    li.innerHTML = label;
                    // Delete button
                    const delBtn = document.createElement('button');
                    delBtn.className = 'btn btn-sm btn-danger';
                    delBtn.textContent = 'Delete';
                    delBtn.onclick = function() { deleteAudioFile(filename); };
                    li.appendChild(delBtn);
                    audioFileList.appendChild(li);
                });
                // Populate default audio select
                selectDefaultAudio.innerHTML = '';
                data.files.forEach(fileInfo => {
                    const { filename, is_default } = fileInfo;
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    if (is_default) opt.selected = true;
                    selectDefaultAudio.appendChild(opt);
                });
                // Set current default audio
                if (currentDefaultAudio) {
                    currentDefaultAudio.textContent = data.default || 'None';
                }
            });
    }

    // Set default audio file
    btnSetDefaultAudio.addEventListener('click', function() {
        const filename = selectDefaultAudio.value;
        fetch('/api/audio/default', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        })
        .then(res => res.json())
        .then(data => {
            loadAudioFiles();
        });
    });

    // Upload audio file
    btnUploadAudio.addEventListener('click', function() {
        const file = audioUpload.files[0];
        if (!file) {
            uploadStatus.textContent = 'No file selected.';
            uploadStatus.classList.remove('text-success');
            uploadStatus.classList.add('text-danger');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        fetch('/api/audio/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                uploadStatus.textContent = 'Upload successful!';
                uploadStatus.classList.remove('text-danger');
                uploadStatus.classList.add('text-success');
                loadAudioFiles();
            } else {
                uploadStatus.textContent = data.error || 'Upload failed.';
                uploadStatus.classList.remove('text-success');
                uploadStatus.classList.add('text-danger');
            }
        });
    });

    // Delete audio file
    function deleteAudioFile(filename) {
        if (!confirm(`Delete ${filename}?`)) return;
        fetch(`/api/audio/delete/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        })
        .then(res => res.json())
        .then(data => {
            loadAudioFiles();
        });
    }

    // Fetch and display volume
    function loadVolume() {
        fetch('/api/audio/volume')
            .then(res => res.json())
            .then(data => {
                audioVolume.value = data.volume;
                audioVolumeValue.textContent = data.volume;
                if (currentVolume) {
                    currentVolume.textContent = data.volume;
                }
            });
    }
    audioVolume.addEventListener('input', function() {
        audioVolumeValue.textContent = audioVolume.value;
    });
    btnSetVolume.addEventListener('click', function() {
        const volume = audioVolume.value;
        fetch('/api/audio/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ volume })
        })
        .then(res => res.json())
        .then(data => {
            loadVolume();
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
    const btnSaveNetwork = document.getElementById('btn-save-network');
    const btnActivateAp = document.getElementById('btn-activate-ap');
    const btnDeactivateAp = document.getElementById('btn-deactivate-ap');
    const btnRefreshWifiLists = document.getElementById('btn-refresh-wifi-lists');
    const wifiStatusMessage = document.getElementById('wifi-status-message');

    function displayWifiMessage(message, isError = false) {
        wifiStatusMessage.textContent = message;
        wifiStatusMessage.className = `alert ${isError ? 'alert-danger' : 'alert-success'}`;
        wifiStatusMessage.style.display = 'block';
        // Automatically hide after 5 seconds
        setTimeout(() => {
            wifiStatusMessage.style.display = 'none';
        }, 5000);
    }

    async function loadWiFiNetworks() {
        try {
            const response = await fetch('/api/networks');
            const data = await response.json();

            // Populate Available Networks
            selectAvailableNetworks.innerHTML = '<option selected disabled>Select an available network...</option>';
            if (data.available_networks && data.available_networks.length > 0) {
                data.available_networks.forEach(net => {
                    const option = document.createElement('option');
                    option.value = net.ssid;
                    option.textContent = `${net.ssid} (${net.signal}%, ${net.security})`;
                    selectAvailableNetworks.appendChild(option);
                });
            } else {
                selectAvailableNetworks.innerHTML = '<option selected disabled>No networks found nearby</option>';
            }

            // Populate Saved Networks
            selectSavedNetworks.innerHTML = '<option selected disabled>Select a saved network...</option>';
            if (data.saved_networks && data.saved_networks.length > 0) {
                data.saved_networks.forEach(net => {
                    const option = document.createElement('option');
                    option.value = net.uuid; // Use UUID for connect/delete if available, else name
                    option.textContent = net.name;
                    selectSavedNetworks.appendChild(option);
                });
            } else {
                selectSavedNetworks.innerHTML = '<option selected disabled>No saved networks</option>';
            }
        } catch (error) {
            displayWifiMessage('Error loading WiFi networks: ' + error, true);
        }
    }

    btnRefreshWifiLists.addEventListener('click', loadWiFiNetworks);

    btnConnectAvailable.addEventListener('click', async () => {
        const ssid = selectAvailableNetworks.value;
        const password = inputAvailablePassword.value;
        if (!ssid || ssid === 'Select an available network...') {
            displayWifiMessage('Please select an available network.', true);
            return;
        }
        // Password might be optional for open networks, backend handles this
        const response = await fetch('/api/networks/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid_or_uuid: ssid, password: password })
        });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) {
            loadWiFiNetworks(); // Refresh lists
            loadStatus(); // Refresh status (current network)
        }
    });

    btnConnectSaved.addEventListener('click', async () => {
        const selectedOption = selectSavedNetworks.options[selectSavedNetworks.selectedIndex];
        const name_or_uuid = selectedOption.value;
        if (!name_or_uuid || name_or_uuid === 'Select a saved network...') {
            displayWifiMessage('Please select a saved network to connect.', true);
            return;
        }
        const response = await fetch('/api/networks/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid_or_uuid: name_or_uuid })
        });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) {
            loadStatus(); // Refresh status
        }
    });

    btnDisconnectNetwork.addEventListener('click', async () => {
        // Disconnects the currently active connection by default if no specific one is chosen
        const response = await fetch('/api/networks/disconnect', { method: 'POST' });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) {
            loadStatus(); // Refresh status
        }
    });

    btnDeleteSaved.addEventListener('click', async () => {
        const selectedOption = selectSavedNetworks.options[selectSavedNetworks.selectedIndex];
        const name_or_uuid = selectedOption.value;
        if (!name_or_uuid || name_or_uuid === 'Select a saved network...') {
            displayWifiMessage('Please select a saved network to delete.', true);
            return;
        }
        if (!confirm(`Are you sure you want to delete the network: ${selectedOption.textContent}?`)) return;

        const response = await fetch('/api/networks/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name_or_uuid: name_or_uuid })
        });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) {
            loadWiFiNetworks(); // Refresh lists
        }
    });

    btnSaveNetwork.addEventListener('click', async () => {
        const ssid = inputNewSsid.value.trim();
        const password = inputNewPassword.value;
        const autoconnect = checkboxNewAutoconnect.checked;

        if (!ssid) {
            displayWifiMessage('SSID cannot be empty.', true);
            return;
        }
        // Password can be empty for open networks, but usually required for save.
        // Backend should handle if password is truly required based on security type if we get that far.
        if (!password) {
             displayWifiMessage('Password is required to save a network.', true);
             return;
        }

        const response = await fetch('/api/networks/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password, autoconnect })
        });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) {
            inputNewSsid.value = '';
            inputNewPassword.value = '';
            loadWiFiNetworks(); // Refresh lists
            loadStatus();
        }
    });

    btnActivateAp.addEventListener('click', async () => {
        const response = await fetch('/api/networks/activate_ap', { method: 'POST' });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) loadStatus();
    });

    btnDeactivateAp.addEventListener('click', async () => {
        const response = await fetch('/api/networks/deactivate_ap', { method: 'POST' });
        const result = await response.json();
        displayWifiMessage(result.message, !result.success);
        if (result.success) loadStatus();
    });

    // Initial load
    loadAudioFiles();
    loadVolume();
    loadStatus();
    setInterval(loadStatus, 5000);

    // Initial load for WiFi section
    loadWiFiNetworks();
}); 