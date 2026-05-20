/** Hermes Voice — Push-to-Talk WebSocket Client with VAD auto-release */

const statusEl = document.getElementById('status');
const micBtn = document.getElementById('micBtn');
const transcriptEl = document.getElementById('transcript');
const permOverlay = document.getElementById('permOverlay');
const permBtn = document.getElementById('permBtn');

let ws = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let micStream = null;
let isRecording = false;
let reconnectTimer = null;
let activeTasks = 0;
let silenceTimer = null;
let vadActive = false;
let pingInterval = null;
let micPermissionGranted = false;

const VAD_THRESHOLD = 0.015;      // RMS amplitude threshold
const VAD_SILENCE_MS = 1500;      // ms of silence before auto-stop
const VAD_MIN_RECORD_MS = 800;    // minimum recording time before VAD can trigger

function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
}

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = 'status ' + (cls || '');
}

function updateTaskBadge() {
  if (activeTasks > 0) {
    setStatus(`Connected — ${activeTasks} background task${activeTasks > 1 ? 's' : ''} running`, 'thinking');
  }
}

function connect() {
  if (ws?.readyState === WebSocket.OPEN) return;

  setStatus('Connecting…');
  ws = new WebSocket(getWsUrl());

  ws.onopen = () => {
    setStatus('Connected — hold to talk', 'connected');
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    // Keep connection alive (mobile proxies love to kill idle sockets)
    if (pingInterval) clearInterval(pingInterval);
    pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({type: 'ping'}));
      }
    }, 15000);
  };

  ws.onmessage = async (event) => {
    console.log('WS message received, length:', event.data.length);
    const msg = JSON.parse(event.data);
    console.log('WS message type:', msg.type);

    if (msg.type === 'response_audio') {
      if (msg.has_background_task) {
        activeTasks++;
        updateTaskBadge();
      }
      setStatus('Hermes is speaking…', 'speaking');
      console.log('Playing response audio, format:', msg.format, 'data length:', msg.data?.length);
      await playAudio(msg.data);
      console.log('playAudio returned, resetting status');
      updateTaskBadge();
      setStatus('Connected — hold to talk', 'connected');
    } else if (msg.type === 'proactive') {
      if (!isRecording) {
        setStatus('Hermes has an update…', 'speaking');
        if (msg.audio_data) {
          await playAudio(msg.audio_data);
        }
        updateTaskBadge();
      } else {
        console.log('Proactive message queued (user recording):', msg.message);
      }
    } else if (msg.type === 'error') {
      setStatus('Error: ' + msg.message);
    }
  };

  ws.onclose = () => {
    setStatus('Disconnected — retrying…');
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    setStatus('Connection error');
  };
}

// --- Microphone permission (pre-warm so push-to-talk is instant) ---

async function requestMicPermission() {
  if (micPermissionGranted) return true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach(t => t.stop());
    micPermissionGranted = true;
    if (permOverlay) permOverlay.classList.add('hidden');
    setStatus('Connected — hold to talk', 'connected');

    // Prime AudioContext from this user gesture — iOS Safari needs this
    if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
      console.log('AudioContext primed during permission grant');
    }

    return true;
  } catch (err) {
    console.error('Mic permission denied:', err);
    setStatus('Microphone access denied');
    return false;
  }
}

// On load, try silently (works on desktop if already allowed)
// On mobile this will fail without a gesture → show overlay
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      stream.getTracks().forEach(t => t.stop());
      micPermissionGranted = true;
      if (permOverlay) permOverlay.classList.add('hidden');
    })
    .catch(() => {
      if (permOverlay) permOverlay.classList.remove('hidden');
    });
} else {
  setStatus('Browser does not support audio input');
}

if (permOverlay) {
  permOverlay.addEventListener('click', (e) => {
    e.stopPropagation();
    requestMicPermission();
  });
}
if (permBtn) {
  permBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    requestMicPermission();
  });
}

function getRms(buffer) {
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) {
    sum += buffer[i] * buffer[i];
  }
  return Math.sqrt(sum / buffer.length);
}

function startVadMonitoring() {
  if (!analyser || !isRecording) return;

  const buffer = new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(buffer);
  const rms = getRms(buffer);

  if (rms > VAD_THRESHOLD) {
    // Sound detected
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    if (!vadActive) {
      vadActive = true;
      micBtn.classList.remove('recording');
      micBtn.classList.add('hearing');
      setStatus('Hearing you…', 'thinking');
    }
  } else if (vadActive && !silenceTimer) {
    // Silence started — start timer
    micBtn.classList.remove('hearing');
    micBtn.classList.add('recording');
    setStatus('Silence detected — finishing…', 'thinking');
    silenceTimer = setTimeout(() => {
      if (isRecording) {
        stopRecording(true);
      }
    }, VAD_SILENCE_MS);
  }

  if (isRecording) {
    requestAnimationFrame(startVadMonitoring);
  }
}

async function startRecording() {
  if (isRecording) return;

  if (!window.MediaRecorder) {
    setStatus('Your browser does not support voice recording. Try Chrome or Safari.');
    return;
  }

  if (!micPermissionGranted) {
    // Permission not yet granted → show overlay instead of blocking on dialog
    if (permOverlay) permOverlay.classList.remove('hidden');
    setStatus('Tap "Enable Microphone" first');
    return;
  }

  isRecording = true;
  micBtn.classList.add('recording');
  setStatus('Listening…', 'thinking');
  audioChunks = [];
  vadActive = false;

  const recordStartTime = Date.now();

  try {
    // Ensure AudioContext is running (user gesture → safe to resume)
    if (audioContext && audioContext.state === 'suspended') {
      await audioContext.resume();
      console.log('AudioContext resumed on recording start');
    }

    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Set up VAD monitoring via Web Audio API
    audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(micStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    mediaRecorder = new MediaRecorder(micStream, { mimeType });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: mimeType });
      console.log('Recorded blob:', blob.size, 'bytes, type:', blob.type);

      if (blob.size < 100) {
        setStatus('Recording too short — try again');
        isRecording = false;
        micBtn.classList.remove('recording');
        micBtn.classList.remove('hearing');
        return;
      }

      const base64 = await blobToBase64(blob);
      const actualFormat = (blob.type || mimeType).includes('mp4') ? 'mp4' : 'webm';

      if (ws?.readyState === WebSocket.OPEN) {
        setStatus('Thinking…', 'thinking');
        ws.send(JSON.stringify({
          type: 'audio',
          data: base64,
          format: actualFormat,
        }));
      } else {
        setStatus('Not connected');
      }
    };

    mediaRecorder.start(100);

    // Start VAD loop after minimum record time
    setTimeout(() => {
      if (isRecording) startVadMonitoring();
    }, VAD_MIN_RECORD_MS);

  } catch (err) {
    console.error('Mic error:', err);
    setStatus('Microphone access denied');
    stopRecording(false);
  }
}

function stopRecording(send = true) {
  if (!isRecording) return;
  isRecording = false;
  micBtn.classList.remove('recording');
  micBtn.classList.remove('hearing');

  if (silenceTimer) {
    clearTimeout(silenceTimer);
    silenceTimer = null;
  }

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    if (!send) {
      mediaRecorder.onstop = null;
    }
    try {
      mediaRecorder.stop();
    } catch (e) {
      console.warn('MediaRecorder.stop() error:', e);
    }
  }

  // Always stop the mic tracks
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
}

function blobToBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.readAsDataURL(blob);
  });
}

async function playAudio(base64Data) {
  console.log('playAudio called, base64 length:', base64Data?.length || 0);

  // --- Strategy 1: HTML5 <audio> element (most reliable on mobile) ---
  try {
    const byteString = atob(base64Data);
    const array = new Uint8Array(byteString.length);
    for (let i = 0; i < byteString.length; i++) {
      array[i] = byteString.charCodeAt(i);
    }
    const blob = new Blob([array], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    console.log('Created audio blob URL, size:', blob.size);

    const audio = new Audio(url);

    return new Promise((resolve) => {
      let resolved = false;
      const cleanup = () => {
        if (resolved) return;
        resolved = true;
        URL.revokeObjectURL(url);
        console.log('Audio playback cleanup');
        resolve();
      };

      audio.onended = () => {
        console.log('Audio playback ended naturally');
        cleanup();
      };
      audio.onerror = (e) => {
        console.error('Audio playback error:', e);
        cleanup();
      };
      audio.onpause = () => {
        console.log('Audio paused');
        cleanup();
      };

      // Safety timeout
      setTimeout(() => {
        console.warn('Audio safety timeout');
        cleanup();
      }, 15000);

      const playPromise = audio.play();
      if (playPromise) {
        playPromise
          .then(() => console.log('Audio.play() resolved successfully'))
          .catch(err => {
            console.error('Audio.play() rejected:', err.name, err.message);
            cleanup();
          });
      } else {
        console.log('Audio.play() returned undefined (older browser)');
      }
    });
  } catch (e) {
    console.error('Audio element playback failed:', e);
    setStatus('Could not play audio');
  }
}

// --- Event handlers ---

// Prevent default touch behaviors that can interfere
function handleTouchStart(e) {
  e.preventDefault();
  startRecording();
}

function handleTouchEnd(e) {
  e.preventDefault();
  stopRecording(true);
}

micBtn.addEventListener('mousedown', startRecording);
micBtn.addEventListener('mouseup', () => stopRecording(true));
micBtn.addEventListener('mouseleave', () => stopRecording(false));

micBtn.addEventListener('touchstart', handleTouchStart, { passive: false });
micBtn.addEventListener('touchend', handleTouchEnd, { passive: false });

// Also handle touchcancel (e.g. phone call incoming, alert popup)
micBtn.addEventListener('touchcancel', () => stopRecording(false));

connect();
