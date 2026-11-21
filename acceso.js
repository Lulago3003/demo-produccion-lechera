/* Puerta de acceso del dashboard publicado en el sitio de AIOROS.
 *
 * Solo se activa en los dominios de `acceso.dominios` (configuracion.json). En el equipo, en la Jetson
 * o abriendo el archivo directo no hay puerta: el dashboard sigue funcionando sin internet.
 *
 * En esos dominios, la página queda oculta hasta comprobar la sesión de aioros.tech:
 *   1. El portal (aioros.tech/mis-servicios) manda aquí con `#sso=<token>`; se canjea con Firebase Auth.
 *      Si ya había sesión en este dominio (por ejemplo, del panel de Gamma), se usa esa.
 *   2. Entra un admin u operador, o una cuenta que tenga alguno de `acceso.servicios` en
 *      `usuarios/{uid}.servicios`, el mismo campo que se edita en el panel de administración.
 *   3. Sin sesión, vuelve al portal. Con sesión pero sin el servicio, lo dice y ofrece cerrar sesión.
 *
 * Es la misma puerta que usan los tableros de Alpha y Beta: oculta la página a quien no entra por el
 * portal, pero los datos de demostración viajan dentro del HTML. Datos reales irían detrás del backend. */
(function () {
  var A = window.GAMMA_ACCESO || {};
  if (!A.firebase || (A.dominios || []).indexOf(location.hostname) < 0) return;

  var raiz = document.documentElement;
  raiz.classList.add('gamma-puerta');
  var estilo = document.createElement('style');
  estilo.textContent =
    'html.gamma-puerta body>:not(#gamma-puerta){display:none!important}' +
    '#gamma-puerta{min-height:100vh;display:grid;place-items:center;padding:24px;background:#EEF2EA;color:#1F3326;' +
    'font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center}' +
    '#gamma-puerta .caja{max-width:420px}#gamma-puerta p{margin:0 0 18px}' +
    '#gamma-puerta a,#gamma-puerta button{display:inline-block;margin:4px;padding:10px 18px;border-radius:8px;' +
    'border:1px solid #1F3326;background:#1F3326;color:#fff;font:inherit;text-decoration:none;cursor:pointer}' +
    '#gamma-puerta button{background:transparent;color:#1F3326}';
  document.head.appendChild(estilo);

  // El token llega en el fragmento: se toma y se borra de la barra antes de que la página lea el fragmento
  var token = null;
  var m = /(?:^#|&)sso=([^&]+)/.exec(location.hash);
  if (m) {
    token = decodeURIComponent(m[1]);
    history.replaceState(null, '', location.pathname + location.search);
  }
  var portal = A.portal || 'https://aioros.tech/';

  function cuandoHayBody(fn) {
    if (document.body) fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function aviso(texto, salir, esperando) {
    cuandoHayBody(function () {
      var p = document.getElementById('gamma-puerta');
      if (!p) {
        p = document.createElement('div');
        p.id = 'gamma-puerta';
        document.body.appendChild(p);
      }
      p.textContent = '';
      var caja = document.createElement('div');
      caja.className = 'caja';
      var t = document.createElement('p');
      t.textContent = texto;
      caja.appendChild(t);
      if (!esperando) {
        var ir = document.createElement('a');
        ir.href = portal;
        ir.textContent = 'Ir a AIOROS';
        caja.appendChild(ir);
        if (salir) caja.appendChild(salir);
      }
      p.appendChild(caja);
    });
  }

  function abrir() {
    raiz.classList.remove('gamma-puerta');
    var p = document.getElementById('gamma-puerta');
    if (p) p.remove();
  }

  aviso('Comprobando tu acceso…', null, true);

  var base = 'https://www.gstatic.com/firebasejs/' + (A.sdk || '10.12.2') + '/';
  Promise.all([import(base + 'firebase-app.js'), import(base + 'firebase-auth.js'), import(base + 'firebase-firestore.js')])
    .then(async function (sdk) {
      var appSdk = sdk[0], authSdk = sdk[1], fs = sdk[2];
      var app = appSdk.initializeApp(A.firebase);
      var auth = authSdk.getAuth(app);
      if (token) {
        try {
          await authSdk.signInWithCustomToken(auth, token);
        } catch (e) {
          console.error('[acceso] token', e);
          aviso('El enlace de acceso venció o no es válido. Vuelve a entrar desde AIOROS.');
          return;
        }
      }
      await auth.authStateReady();
      var usuario = auth.currentUser;
      if (!usuario) {
        location.replace(portal);
        return;
      }
      var claims = (await usuario.getIdTokenResult()).claims || {};
      if (claims.admin === true || claims.role === 'admin' || claims.role === 'operador') {
        abrir();
        return;
      }
      var doc = await fs.getDoc(fs.doc(fs.getFirestore(app), 'usuarios', usuario.uid));
      var servicios = doc.exists() && Array.isArray(doc.data().servicios) ? doc.data().servicios : [];
      if ((A.servicios || []).some(function (s) { return servicios.indexOf(s) >= 0; })) {
        abrir();
        return;
      }
      var salir = document.createElement('button');
      salir.type = 'button';
      salir.textContent = 'Cerrar sesión';
      salir.onclick = function () { authSdk.signOut(auth).then(function () { location.replace(portal); }); };
      aviso('La cuenta ' + (usuario.email || '') + ' no tiene acceso a esta demostración.', salir);
    })
    .catch(function (e) {
      console.error('[acceso]', e);
      aviso('No se pudo comprobar tu acceso. Revisa la conexión y vuelve a cargar la página.');
    });
})();
