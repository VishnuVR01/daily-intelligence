// Register Service Worker safely & handle PWA Installation Prompt
let deferredPrompt = null;

window.addEventListener('load', () => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/js/service-worker.js')
      .then((registration) => {
        console.log('Daily Intelligence Service Worker registered with scope:', registration.scope);
      })
      .catch((error) => {
        console.warn('Daily Intelligence Service Worker registration failed:', error);
      });
  }
});

// Capture installability event
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  
  const installBtn = document.getElementById('pwa-install-btn');
  if (installBtn) {
    installBtn.style.display = 'inline-flex';
    installBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      console.log(`User installation choice: ${outcome}`);
      deferredPrompt = null;
      installBtn.style.display = 'none';
    });
  }
});

window.addEventListener('appinstalled', () => {
  console.log('Daily Intelligence PWA successfully installed!');
  deferredPrompt = null;
  const installBtn = document.getElementById('pwa-install-btn');
  if (installBtn) {
    installBtn.style.display = 'none';
  }
});
