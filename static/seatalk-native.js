/* Entrada nativa: SDK oficial; nenhuma identidade fornecida pelo navegador é confiada. */
(() => {
  const entry = document.querySelector('[data-seatalk-native]');
  const status = document.getElementById('seatalk-native-status');
  // Mesmo identificador usado por clientInfo no SDK, incluindo o cliente RC.
  if (!entry || !status || new URLSearchParams(location.search).get('browser') === '1'
      || !/(?:^|\s)SeaTalk(?:\.rc)?\//i.test(navigator.userAgent)) return;
  let busy = false;
  const welcome = document.querySelector('.sea-welcome');
  const heading = welcome?.querySelector('h1');
  const deadline = (promise, ms) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('O SeaTalk demorou para responder. Tente entrar novamente.')), ms);
    Promise.resolve(promise).then(value => { clearTimeout(timer); resolve(value); }, error => { clearTimeout(timer); reject(error); });
  });
  const sdk = () => window.ehaSeaSDK();
  async function jsonRequest(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(url, {credentials:'same-origin', cache:'no-store', ...options, signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível entrar agora. Tente novamente.');
      return data;
    } finally { clearTimeout(timer); }
  }
  async function login(event) {
    event?.preventDefault();
    if (busy) return;
    busy = true;
    if (welcome) { welcome.dataset.state = 'loading'; entry.hidden = true; }
    if (heading) heading.textContent = 'Preparando sua operação…';
    entry.setAttribute('aria-disabled', 'true');
    status.hidden = false;
    status.textContent = 'Entrando com sua conta do SeaTalk…';
    try {
      const bridge = await deadline(sdk(), 15000);
      const challenge = await jsonRequest('/auth/seatalk/native/challenge');
      const token = await deadline(bridge.getSSOToken(), 20000);
      const result = await jsonRequest('/auth/seatalk/native', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({state:challenge.state, token})
      });
      // A navegação ocorre na mesma WebView, sem abrir janela/navegador externo.
      window.location.assign(result.redirect);
    } catch (error) {
      if (welcome) { welcome.dataset.state = 'error'; entry.hidden = false; }
      if (heading) heading.textContent = 'Vamos tentar de novo?';
      status.textContent = error instanceof Error && error.name !== 'AbortError'
        ? error.message : 'A entrada demorou para responder. Tente novamente.';
    } finally {
      busy = false;
      entry.removeAttribute('aria-disabled');
    }
  }
  entry.addEventListener('click', login);
  if (!document.querySelector('[data-login-denied]')) login();
  else if (welcome) {
    welcome.dataset.state = 'error'; entry.hidden = false;
    if (heading) heading.textContent = 'Confira seu acesso';
    status.textContent = 'Sua conta precisa de liberação para acessar o EHA Live.';
  }
})();
