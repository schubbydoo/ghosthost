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

    // Initial load
    loadAudioFiles();
    loadVolume();
    loadStatus();
    setInterval(loadStatus, 5000);
}); 