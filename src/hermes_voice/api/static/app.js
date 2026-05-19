/** Hermes Voice — Push-to-Talk WebSocket Client with VAD auto-release */

const statusEl = document.getElementById('status');
const micBtn = document.getElementById('micBtn');
const transcriptEl = document.getElementById('transcript');

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
  };

  ws.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === 'response_audio') {
      if (msg.has_background_task) {
        activeTasks++;
        updateTaskBadge();
      }
      setStatus('Hermes is speaking…', 'speaking');
      await playAudio(msg.data);
      updateTaskBadge();
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
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    setStatus('Connection error');
  };
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
  isRecording = true;
  micBtn.classList.add('recording');
  setStatus('Listening…', 'thinking');
  audioChunks = [];
  vadActive = false;

  const recordStartTime = Date.now();

  try {
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
      const base64 = await blobToBase64(blob);
      if (ws?.readyState === WebSocket.OPEN) {
        setStatus('Thinking…', 'thinking');
        ws.send(JSON.stringify({
          type: 'audio',
          data: base64,
          format: 'webm',
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
    mediaRecorder.stop();
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
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();

  const byteString = atob(base64Data);
  const buffer = new ArrayBuffer(byteString.length);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < byteString.length; i++) {
    view[i] = byteString.charCodeAt(i);
  }

  try {
    const decoded = await audioContext.decodeAudioData(buffer);
    const source = audioContext.createBufferSource();
    source.buffer = decoded;
    source.connect(audioContext.destination);
    source.start(0);
    return new Promise((resolve) => { source.onended = resolve; });
  } catch (e) {
    console.error('Audio decode error:', e);
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
