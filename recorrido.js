(function(){
  'use strict';
  // Recorrido guiado: lleva pestaña por pestaña con una tarjeta que explica qué mirar.
  // Se abre con el botón de la portada o con el enlace …/#recorrido.
  const web=()=>document.body.classList.contains('gamma-web');
  const suave=()=>matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth';
  const n=x=>Number(x).toLocaleString('en-US');
  const anomalas=new Set(D.anomalias.map(a=>String(a.vaca))).size;
  const PASOS=[
    {tab:'hato',el:'.resumen',titulo:'Lo esencial',
     texto:()=>'Estas tres cifras resumen lo que encontró el análisis en '+n(D.resumen.vacas)+' vacas Holstein. Cada tarjeta lleva a su detalle.'},
    {tab:'hato',el:'#g-principal',titulo:'Cómo produce el hato',
     texto:()=>'Cada línea es la producción diaria típica según el número de lactancia. Desde la segunda, las vacas llegan a un pico más alto. Pasa el cursor o toca la gráfica para ver los valores.'},
    {tab:'hato',el:'.registro',titulo:'Dos listas distintas',
     texto:()=>'A la izquierda, las '+n(D.vigilancia.length)+' vacas que el modelo prevé con baja producción en su próxima lactancia: conviene revisarlas antes del parto. A la derecha, las '+n(anomalas)+' vacas que ya tuvieron una lactancia más baja de lo esperado. Las dos listas se descargan en Excel.'},
    {tab:'vacas',el:'#ficha',titulo:'La ficha de cada vaca',
     texto:()=>'La línea continua es lo que produjo la vaca; la discontinua, lo que esperaba el modelo; la franja, su margen. Con el buscador puedes abrir cualquier vaca por arete o nombre.'},
    {tab:'toros',el:'#sementales',titulo:'Con qué toros inseminar',
     texto:()=>'Cada punto compara la leche de las hijas de un toro con el promedio. El punto lleno indica que el toro se distingue del promedio; si la línea cruza el cero, con estos datos no se puede decir. No es una evaluación genética oficial.'},
    {tab:'dinero',el:'#economia',titulo:'Cuánta plata representa',
     texto:()=>'Los kilos que faltaron se pasan a litros y a dólares. Cambia el precio por litro y todo se recalcula, también la cifra de la portada. Es ingreso bruto, no ganancia.'},
    {tab:'gemma',el:'#asistente .gamma-split',vista:'#asistente',titulo:'Asistente Gemma',
     texto:()=>'En la finca, Gemma 3 corre en el equipo, sin internet, y responde preguntas como «¿cuánta plata se perdió?» o «¿con qué toros me conviene inseminar?». No inventa números: cada cifra se comprueba contra el registro. '+(web()?'Aquí ves un ejemplo; toca las otras preguntas sugeridas para ver más.':'Escribe una pregunta o toca una de las sugeridas.'),
     antes:()=>{if(web()&&!document.querySelector('#chat-respuestas article'))document.querySelector('[data-ejemplo="economia"]').click();}},
    {tab:'sensores',el:'#seguimiento',titulo:'Sensores en la finca',
     texto:()=>'Los sensores mandan la producción diaria, la temperatura y la humedad por MQTT al equipo de la finca. '+(web()?'Este escenario simulado muestra las dos alertas: calor por encima del umbral y una vaca con dos días de caída de más del 20 %.':'Toca «Cargar escenario simulado» para ver las alertas de calor y de caída de producción.'),
     antes:()=>{if(web()&&!document.querySelector('#sensor-resumen .gamma-alert'))document.getElementById('sensor-demo').click();}},
    {tab:'metodo',el:'#panel-metodo',titulo:'Cómo se calculó',
     texto:()=>'Aquí se explica de dónde sale cada número: los datos, el modelo y sus límites. Los datos son públicos y todavía no son de una finca de Panamá. Fin del recorrido.'}
  ];
  let i=0,foco=null,origen=null;
  const tarjeta=document.createElement('div');
  tarjeta.className='recorrido';tarjeta.hidden=true;
  tarjeta.setAttribute('role','dialog');tarjeta.setAttribute('aria-labelledby','recorrido-titulo');
  tarjeta.innerHTML='<div class="recorrido-cab"><span id="recorrido-paso"></span><button type="button" class="recorrido-cerrar" aria-label="Salir del recorrido">×</button></div>'+
    '<h2 id="recorrido-titulo"></h2><p id="recorrido-texto"></p>'+
    '<div class="recorrido-botones"><button type="button" class="boton" id="recorrido-atras">Anterior</button><button type="button" class="boton gamma-primary" id="recorrido-sigue">Siguiente</button></div>';
  document.body.appendChild(tarjeta);
  const $=id=>document.getElementById(id);
  function ir(j){
    i=j;const p=PASOS[i];
    if(foco)foco.classList.remove('en-foco');
    history.replaceState(null,'','#'+p.tab);abrir(p.tab);
    if(p.antes)p.antes();
    foco=document.querySelector(p.el);
    $('recorrido-paso').textContent='Paso '+(i+1)+' de '+PASOS.length;
    $('recorrido-titulo').textContent=p.titulo;$('recorrido-texto').textContent=p.texto();
    $('recorrido-atras').hidden=i===0;$('recorrido-sigue').textContent=i===PASOS.length-1?'Terminar':'Siguiente';
    // se desplaza bajo la barra de pestañas; 'vista' deja ver el título de la sección
    const destino=p.vista?document.querySelector(p.vista):foco;
    if(foco)foco.classList.add('en-foco');
    if(destino)requestAnimationFrame(()=>window.scrollTo({top:destino.getBoundingClientRect().top+scrollY-document.querySelector('.gamma-nav').offsetHeight-16,behavior:suave()}));
  }
  function abrirRecorrido(){origen=document.activeElement;document.body.classList.add('en-recorrido');tarjeta.hidden=false;ir(0);$('recorrido-sigue').focus();}
  function cerrar(){
    if(foco)foco.classList.remove('en-foco');foco=null;
    tarjeta.hidden=true;document.body.classList.remove('en-recorrido');
    if(origen&&document.contains(origen)&&origen!==document.body)origen.focus();
  }
  $('recorrido-sigue').onclick=()=>{if(i<PASOS.length-1)ir(i+1);else cerrar();};
  $('recorrido-atras').onclick=()=>{if(i>0)ir(i-1);};
  tarjeta.querySelector('.recorrido-cerrar').onclick=cerrar;
  document.addEventListener('keydown',e=>{
    if(tarjeta.hidden||/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName))return;
    if(e.key==='Escape')cerrar();
    else if(e.key==='ArrowRight'&&!e.target.closest('[role=tablist]'))$('recorrido-sigue').click();
    else if(e.key==='ArrowLeft'&&!e.target.closest('[role=tablist]')&&i>0)ir(i-1);
  });
  $('recorrido-abrir').onclick=abrirRecorrido;
  if(location.hash==='#recorrido')abrirRecorrido();
})();
