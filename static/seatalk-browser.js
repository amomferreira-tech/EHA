/* SeaTalk-only presentation. External navigation never carries session/token data. */
(() => {
  const native = /(?:^|\s)SeaTalk(?:\.rc)?\//i.test(navigator.userAgent);
  let sdkPromise;
  window.ehaSeaSDK = () => {
    if (window.st?.getSSOToken) return Promise.resolve(window.st);
    return sdkPromise || (sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/static/vendor/seatalk-js-sdk-1.5.0.min.js';
      script.onload = () => window.st?.clientInfo?.app === 'SeaTalk'
        ? resolve(window.st) : reject(new Error('Abra o aplicativo dentro do SeaTalk.'));
      script.onerror = () => { sdkPromise = undefined; script.remove(); reject(new Error('Não foi possível carregar a entrada SeaTalk. Tente novamente.')); };
      document.head.appendChild(script);
    }));
  };
  const desktop = /Windows|Macintosh/.test(navigator.userAgent);
  document.querySelectorAll('[data-seatalk-browser]').forEach(button => {
    button.hidden = !native;
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      const label = button.textContent;
      const timer = setTimeout(() => { button.disabled = false; button.textContent = label; }, 15000);
      try {
        const sdk = await window.ehaSeaSDK();
        const url = new URL('/login?browser=1', location.origin).href;
        await sdk.openInExternalBrowser({url});
      } catch (_) {
        const status = document.getElementById('seatalk-browser-status');
        if (status) {
          status.hidden = false;
          status.textContent = 'O SeaTalk não abriu o navegador. Copie este endereço para o Chrome: ' + location.origin + '/login';
        }
      } finally {
        clearTimeout(timer);
        button.disabled = false;
        button.textContent = label;
      }
    });
  });
})();
