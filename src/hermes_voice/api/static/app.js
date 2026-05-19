/** Hermes Voice — Push-to-Talk WebSocket Client with proactive notifications */

const statusEl = document.getElementById('status');
const micBtn = document.getElementById('micBtn');
const transcriptEl = document.getElementById('transcript');

let ws = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let isRecording = false;
let reconnectTimer = null;
let activeTasks = 0;

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
      // Background task completed — auto-play if user isn't recording
      if (!isRecording) {
        setStatus('Hermes has an update…', 'speaking');
        if (msg.audio_data) {
          await playAudio(msg.audio_data);
        }
        updateTaskBadge();
      } else {
        // Queue visually? For now just log
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

async function startRecording() {
  if (isRecording) return;
  isRecording = true;
  micBtn.classList.add('recording');
  setStatus('Listening…', 'thinking');
  audioChunks = [];

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(100);
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

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());

    if (send) {
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
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
    }
    mediaRecorder = null;
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

// Touch / mouse events
micBtn.addEventListener('mousedown', startRecording);
micBtn.addEventListener('mouseup', () => stopRecording(true));
micBtn.addEventListener('mouseleave', () => stopRecording(false));

micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(true); });

connect();
