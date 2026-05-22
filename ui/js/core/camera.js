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
})();
