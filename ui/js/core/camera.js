(function () {
  let activeStream = null;

  window.startCamera = async function startCamera(videoId) {
    window.stopCamera();
    try {
      activeStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      document.getElementById(videoId).srcObject = activeStream;
    } catch {
      console.warn('Camera access denied or unavailable.');
      if (typeof showCameraError === 'function') showCameraError();
    }
  };

  window.stopCamera = function stopCamera() {
    if (activeStream) {
      activeStream.getTracks().forEach(t => t.stop());
      activeStream = null;
    }
  };

  window.captureFrame = function captureFrame(videoId) {
    const video  = document.getElementById(videoId);
    const canvas = document.getElementById('capture-canvas');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d').drawImage(video, 0, 0);
    return canvas.toDataURL('image/jpeg', 0.85);
  };

  // Re-trigger the CSS pulse on the kiosk face-box corners. The
  // class toggle + forced reflow is needed because re-adding the same
  // class otherwise won't restart the animation. On the registration
  // modal (no face-box element) this is a no-op, by design.
  function _flashCorners() {
    const fb = document.getElementById('face-box');
    if (!fb) return;
    fb.classList.remove('flash-corners');
    void fb.offsetWidth;
    fb.classList.add('flash-corners');
  }

  // Snap `count` frames spaced `gapMs` apart. Returns base64 JPEGs.
  // Used at registration (to capture pose variation per variant) and
  // at kiosk scan time (so a blink on one frame doesn't fail the scan).
  // On the kiosk, briefly pulses the face-box corner brackets on each
  // frame so the user sees something is happening during the ~1 s burst.
  window.captureBurst = async function captureBurst(videoId, count = 3, gapMs = 350) {
    const video  = document.getElementById(videoId);
    const canvas = document.getElementById('capture-canvas');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    const frames = [];
    for (let i = 0; i < count; i++) {
      ctx.drawImage(video, 0, 0);
      frames.push(canvas.toDataURL('image/jpeg', 0.85));
      _flashCorners();
      if (i < count - 1) await new Promise(r => setTimeout(r, gapMs));
    }
    return frames;
  };
})();
