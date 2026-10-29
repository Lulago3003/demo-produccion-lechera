(function(){
  'use strict';
  const $=id=>document.getElementById(id), cfg=GAMMA_CONFIG;
  const usd=n=>new Intl.NumberFormat('es-PA',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n);
  const usd0=n=>new Intl.NumberFormat('es-PA',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
  const num=(n,d=1)=>Number(n).toLocaleString('es-PA',{maximumFractionDigits:d});
  let precio=cfg.precio_litro, densidad=cfg.densidad_kg_litro, token='', conectado=false, ocupado=false;
  let historial=[], finca='demo', simulado=false, firma='', primerSensor=true, lecturas=null, pendienteAuto=false;
  let seleccion=String($('v-arete').textContent), eco=[];
  try{
    const guardado=JSON.parse(localStorage.getItem('gamma-precio-v2'));
    if(guardado&&Number.isFinite(guardado.precio)&&guardado.precio>=0&&guardado.precio<=10&&Number.isFinite(guardado.densidad)&&guardado.densidad>=1&&guardado.densidad<=1.1){precio=guardado.precio;densidad=guardado.densidad;}
  }catch(e){}
  $('precio-leche').value=precio;$('densidad-leche').value=densidad;
  const celda=v=>esc(v===null||v===undefined?'—':typeof v==='object'?JSON.stringify(v):typeof v==='number'?num(v,2):String(v));
  function tabla(filas){
    if(!filas.length)return '<p class="gamma-muted">No hay registros comparables para esta consulta.</p>';
    const ks=Object.keys(filas[0]);
    return '<table><thead><tr>'+ks.map(k=>'<th>'+esc(k.replaceAll('_',' '))+'</th>').join('')+'</tr></thead><tbody>'+filas.map(r=>'<tr>'+ks.map(k=>'<td>'+celda(r[k])+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
  }
  function calculoEconomico(){
    const filas=[];let sin=0;
    Object.entries(D.vacas).forEach(([id,v])=>v.lacts.filter(l=>l.anom).forEach(l=>{
      if(!l.w||l.e305==null){sin++;return;}
      const dias=Math.min(305,l.dur),kg=wood(l.w,dias).reduce((a,b)=>a+b,0),litros=Math.max(0,l.e305-kg)/densidad;
      filas.push({vaca:id,nombre:v.nombre,lactancia:l.n,dias,kg_reconstruidos:+kg.toFixed(2),kg_esperados:l.e305,litros_brecha:+litros.toFixed(2),valor_brecha:+(litros*precio).toFixed(2)});
    }));
    filas.sort((a,b)=>b.valor_brecha-a.valor_brecha);eco=filas;
    $('economia-cifras').innerHTML=[['Brecha histórica estimada',usd(filas.reduce((a,b)=>a+b.valor_brecha,0)),'Ingreso bruto del escenario'],['Leche equivalente',num(filas.reduce((a,b)=>a+b.litros_brecha,0),0)+' L','En lactancias anómalas comparables'],['Lactancias comparables',filas.length,sin+' sin base suficiente para monetizar']].map(r=>'<div class="gamma-stat"><dt>'+r[0]+'</dt><dd>'+r[1]+'</dd><small>'+r[2]+'</small></div>').join('');
    $('economia-tabla').innerHTML=tabla(filas.slice(0,12));
    // la cifra de la portada sigue al precio elegido
    $('kpi-dinero').textContent=usd0(filas.reduce((a,b)=>a+b.valor_brecha,0));$('kpi-dinero-nota').textContent='en leche que faltó en lactancias pasadas, a '+usd(precio)+' por litro';
    $('precio-fuente').innerHTML=(precio===cfg.precio_litro?'Precio de referencia, '+usd(cfg.precio_litro)+' por litro. ':'Precio personalizado. La referencia es '+usd(cfg.precio_litro)+' por litro. ')+esc(cfg.precio_descripcion)+' <a href="'+esc(cfg.precio_fuente)+'" target="_blank" rel="noopener">Ver la noticia</a>. <a href="'+esc(cfg.densidad_fuente)+'" target="_blank" rel="noopener">Densidad orientativa (FAO)</a>.';
    economiaVaca();
  }
  function economiaVaca(){
    const v=D.vacas[seleccion];if(!v)return;
    let h='<b>Valor económico de la vaca '+esc(seleccion)+'</b><br>';
    const filas=eco.filter(r=>r.vaca===seleccion);
    h+=filas.length?'Brecha histórica comparable: <b>'+usd(filas.reduce((a,b)=>a+b.valor_brecha,0))+'</b>.<br>':'Sin brecha histórica monetizable en las lactancias anómalas comparables.<br>';
    if(v.prox){const valor=v.prox.p305/densidad*precio,m=D.modelo.margen;
      h+='Próxima lactancia, hasta 305 días: <b>'+num(v.prox.p305/densidad,0)+' litros</b>, unos <b>'+usd(valor)+'</b> de ingreso bruto. Rango del escenario: '+usd(valor*(1-m))+' a '+usd(valor*(1+m))+'.<br>';
    }
    h+='<span class="gamma-muted">Precio '+usd(precio)+'/L; densidad '+num(densidad,3)+' kg/L. Sin descontar costos.</span>';
    $('v-economia').innerHTML=h;
    $('chat-vaca').textContent='Ficha seleccionada: '+seleccion+(v.nombre?', '+v.nombre:'');
  }
  function cambiarPrecio(){
    const p=$('precio-leche').valueAsNumber,d=$('densidad-leche').valueAsNumber;
    if(!Number.isFinite(p)||p<0||p>10||!Number.isFinite(d)||d<1||d>1.1){$('economia-error').textContent='Introduce un precio entre 0 y 10 y una densidad entre 1 y 1,1.';return;}
    $('economia-error').textContent='';precio=p;densidad=d;
    try{localStorage.setItem('gamma-precio-v2',JSON.stringify({precio,densidad}));}catch(e){}
    calculoEconomico();
    if(lecturas)mostrarSensores(lecturas);
  }
  $('precio-leche').addEventListener('input',cambiarPrecio);$('densidad-leche').addEventListener('input',cambiarPrecio);
  $('restaurar-precio').onclick=()=>{$('precio-leche').value=cfg.precio_litro;$('densidad-leche').value=cfg.densidad_kg_litro;cambiarPrecio();};
  $('exportar-economia').onclick=()=>{
    const campos=['vaca','nombre','lactancia','dias','kg_reconstruidos','kg_esperados','litros_brecha','valor_brecha'];
    descargar([['Escenario histórico; no pérdida demostrada ni total anual'],['Precio USD/L',precio],['Densidad kg/L',densidad],campos].concat(eco.map(r=>campos.map(k=>typeof r[k]==='number'?String(r[k]).replace('.',','):r[k]))),'gamma_valor_economico.csv');
  };
  window.addEventListener('gamma-vaca',e=>{seleccion=String(e.detail.id);economiaVaca();});
  calculoEconomico();

  function dibujarGrafica(g){
    if(!g||!g.series||!g.series.length)return '';
    const colores=['#2c7340','#b18400','#4e944f','#1a5130'];
    let html='<div class="gamma-chart"><p>'+esc(g.titulo)+' ('+esc(g.unidad)+')</p>';
    if(g.tipo==='barras'){
      const vals=g.series[0].valores,neg=vals.some(v=>v<0),max=Math.max(1,...vals.map(Math.abs));
      html+='<div class="gamma-bars" role="img" aria-label="'+esc(g.titulo)+'">'+vals.map((v,i)=>{
        const ancho=Math.abs(v)/max*(neg?50:100),izq=neg?(v<0?50-ancho:50):0;
        return '<div class="gamma-bar"><span>'+esc(g.etiquetas[i])+'</span><span class="gamma-bar-track"><i style="left:'+izq+'%;width:'+ancho+'%;'+(v<0?'background:#a26d21':'')+'"></i></span><b>'+num(v,0)+'</b></div>';
      }).join('')+'</div>';
    }else{
      const W=800,H=290,L=54,R=18,T=22,B=42,N=g.etiquetas.length;
      if(N===0)return html+'<p>Sin puntos disponibles.</p></div>';
      const vals=g.series.flatMap(s=>s.valores).filter(v=>v!==null&&Number.isFinite(v)),ymax=Math.max(1,...vals)*1.1;
      const X=i=>L+i/Math.max(1,N-1)*(W-L-R),Y=v=>H-B-v/ymax*(H-T-B);
      html+='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(g.titulo)+'">';
      for(let j=0;j<=4;j++){const v=ymax*j/4,y=Y(v);html+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" stroke="#dce3d6"/><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" font-size="12" fill="#6b796e">'+num(v,0)+'</text>';}
      g.series.forEach((s,j)=>{let path='',pen=false;s.valores.forEach((v,i)=>{if(v===null||!Number.isFinite(v)){pen=false;return;}path+=(pen?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1);pen=true;});html+='<path d="'+path+'" stroke="'+colores[j%4]+'" stroke-width="2.5" fill="none"/>';});
      [0,Math.floor((N-1)/2),N-1].filter((v,i,a)=>a.indexOf(v)===i).forEach(i=>{html+='<text x="'+X(i)+'" y="'+(H-17)+'" text-anchor="middle" font-size="12" fill="#6b796e">'+esc(g.etiquetas[i])+'</text>';});
      html+='</svg><div class="gamma-chart-legend">'+g.series.map((s,i)=>'<span><i style="background:'+colores[i%4]+'"></i>'+esc(s.nombre)+'</span>').join('')+'</div>';
    }
    return html+'</div>';
  }
  async function api(ruta,body,timeout=150000){
    const headers={};if(body){headers['Content-Type']='application/json';headers['X-Gamma-Token']=token;}
    const r=await fetch(ruta,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(timeout)});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo completar la solicitud');return d;
  }
  function mostrarRespuesta(p,r){
    const cont=$('chat-respuestas');if(!historial.length)cont.innerHTML='';
    const article=document.createElement('article');article.className='gamma-respuesta';
    article.innerHTML='<p class="gamma-pregunta">'+esc(p)+'</p><div class="gamma-muted">'+esc(r.ambito)+'. '+(r.motor==='ejemplo'?'Ejemplo de la versión web: cifras, gráfica y hallazgos verificados calculados del registro. En el equipo de la finca, Gemma elige los hallazgos y responde con sus palabras.':r.motor==='gemma'?(r.modo==='redaccion_verificada'?'Redactó Gemma en '+num(r.segundos,1)+' s; cada cifra se comprobó contra el registro.':'Respondió Gemma en '+num(r.segundos,1)+' s con hallazgos verificados.'):r.motor==='regla'?'Respuesta fija: el registro no tiene datos de salud.':r.motor==='ocupado'?'Gemma estaba ocupado.':r.motor==='verificacion'?'Redacción no verificada.':'Cifras calculadas; Gemma no respondió.')+'</div><div class="gamma-prosa">'+esc(r.respuesta)+'</div>'+ '<dl class="gamma-facts">'+r.hechos.map(h=>'<div><dt>'+esc(h.etiqueta)+'</dt><dd>'+celda(h.valor)+' '+esc(h.unidad)+'</dd></div>').join('')+'</dl>'+dibujarGrafica(r.grafica)+'<details><summary>Datos utilizados y alcance</summary><div class="desliza">'+tabla(r.tabla)+'</div>'+r.notas.map(n=>'<p>'+esc(n)+'</p>').join('')+'</details>';
    cont.prepend(article);while(cont.children.length>10)cont.lastElementChild.remove();cont.scrollTop=0;
    // en el celular la respuesta queda debajo del formulario: se lleva a la vista
    if(matchMedia('(max-width:800px)').matches)article.scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function preguntar(p,automatico=false){
    if(ocupado)return;
    if(!conectado){$('chat-error').textContent='Abre iniciar.command en la carpeta del proyecto y usa el dashboard en http://127.0.0.1:8765.';return;}
    ocupado=true;$('chat-enviar').disabled=true;$('chat-respuestas').setAttribute('aria-busy','true');$('chat-error').textContent='';
    $('gemma-estado').className='gamma-status procesando';$('gemma-estado').textContent='Gemma está leyendo los datos…';
    try{
      const conVaca=$('chat-alcance').value==='vaca'||/esta vaca|seleccionada/.test(p.toLowerCase());
      const r=await api('/api/chat',{pregunta:p,vaca:conVaca?seleccion:null,precio_litro:precio,densidad_kg_litro:densidad,finca,simulado,historial:historial.slice(-3),tema:automatico?'sensores':'auto'});
      if(r.vaca_consultada){mostrar(r.vaca_consultada);$('chat-alcance').value='vaca';}
      mostrarRespuesta(p,r);historial.push(p);if(historial.length>10)historial.shift();
      $('gemma-estado').className='gamma-status '+(r.motor==='gemma'?'listo':'');$('gemma-estado').textContent=r.motor==='gemma'?'Gemma 3 de 4B, en este equipo':'Consulta terminada; revisa el estado del modelo';
      if(!automatico)$('chat-pregunta').value='';
    }catch(e){$('chat-error').textContent=e.name==='TimeoutError'?'La consulta tardó demasiado; vuelve a intentarlo.':e.message;$('gemma-estado').className='gamma-status';$('gemma-estado').textContent='Consulta interrumpida';}
    finally{ocupado=false;$('chat-enviar').disabled=false;$('chat-respuestas').setAttribute('aria-busy','false');}
  }
  $('chat-form').onsubmit=e=>{e.preventDefault();const p=$('chat-pregunta').value.trim();if(p)preguntar(p);};
  $('chat-pregunta').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}};
  document.querySelectorAll('[data-pregunta]').forEach(b=>b.onclick=()=>{$('chat-pregunta').value=b.dataset.pregunta;$('chat-pregunta').focus();});
  $('chat-limpiar').onclick=()=>{if(ocupado)return;historial=[];$('chat-respuestas').innerHTML='<div class="gamma-empty">Conversación vacía. Escribe una nueva pregunta.</div>';};

  function mostrarSensores(s){
    lecturas=s;
    $('sensor-estado').textContent=(s.simulado?'Datos simulados de la finca ':'Registros reales de la finca ')+s.finca+': '+s.eventos+' eventos, revisado a las '+new Date(s.actualizado).toLocaleTimeString('es-PA',{timeZone:'America/Panama'});
    if(!s.eventos){$('sensor-resumen').innerHTML='<div class="gamma-empty">No hay registros para esta finca y este origen. Puedes cargar el escenario simulado para probar los avisos y la proyección.</div>';return;}
    let h=s.simulado?'<div class="gamma-notice simulado"><b>Datos simulados.</b> Este escenario contiene una caída de producción y una lectura de calor para comprobar la integración.</div>':'';
    h+=s.alertas.length?s.alertas.map(a=>'<div class="gamma-alert"><b>'+esc(a.referencia)+':</b> '+esc(a.mensaje)+'<br>'+esc(a.tipo==='calor'?'THI: ':'Última producción: ')+num(a.valor,2)+' '+esc(a.unidad||'')+'</div>').join(''):'<p class="estado e-ok">Sin alertas activas en las lecturas recientes</p>';
    if(s.predicciones&&s.predicciones.length)h+='<div class="gamma-box"><h3>Inferencias de lactancias recibidas</h3><p class="gamma-muted">Modelo entrenado ejecutado al recibir la lactancia completa. El precio corresponde al escenario enviado con el evento.</p><div class="desliza">'+tabla(s.predicciones)+'</div></div>';
    h+='<div class="gamma-sensor-grid">';
    s.ambiente.forEach(a=>{h+='<div class="gamma-box"><h3>'+esc(a.zona)+'</h3><div class="gamma-facts"><div><dt>Temperatura</dt><dd>'+num(a.temperatura_c)+' °C</dd></div><div><dt>Humedad</dt><dd>'+num(a.humedad_pct)+' %</dd></div><div><dt>Índice de calor (THI), umbral '+cfg.thi_umbral+'</dt><dd>'+num(a.thi)+'</dd></div></div><p class="gamma-muted">'+esc(new Date(a.timestamp).toLocaleString('es-PA',{timeZone:'America/Panama',day:'numeric',month:'short',hour:'numeric',minute:'2-digit'}))+(a.desactualizado?', sin datos recientes (más de 15 minutos)':', lectura reciente')+'</p></div>';});
    s.vacas.forEach(v=>{h+='<div class="gamma-box"><h3>Vaca '+esc(v.vaca)+', lactancia '+v.lactancia+'</h3><p>'+v.registros+' registros diarios hasta el '+esc(v.fecha)+(v.desactualizado?'. Sin datos recientes':'')+'.</p>';
      const pro=v.proyeccion;
      if(pro.disponible){h+='<p>Proyección experimental a 305 días: <b>'+num(pro.kg_305,0)+' kg</b>, que son '+num(pro.kg_305/densidad,0)+' litros y '+usd(pro.kg_305/densidad*precio)+' brutos.</p><p class="gamma-muted">'+esc(pro.metodo)+'</p>';}
      else h+='<p class="gamma-muted">'+esc(pro.motivo)+'</p>';
      const serie=[{nombre:s.simulado?'Simulada':'Registrada',valores:v.serie.map(x=>x.kg)}];
      if(pro.disponible)serie.push({nombre:'Referencia escalada',valores:v.serie.map(x=>pro.curva[x.dia-1]??null)});
      h+=dibujarGrafica({tipo:'lineas',titulo:'Producción diaria',unidad:'kg/día',etiquetas:v.serie.map(x=>x.dia),series:serie})+'<details><summary>Ver registros</summary><div class="desliza">'+tabla(v.serie)+'</div></details></div>';
    });
    $('sensor-resumen').innerHTML=h+'</div>';
  }
  async function refrescar(){
    if(!conectado)return;
    const f=finca,sim=simulado;
    try{
      const s=await api('/api/sensores?finca='+encodeURIComponent(f)+'&simulado='+sim,undefined,10000);
      if(f!==finca||sim!==simulado)return;
      const nueva=JSON.stringify([s.finca,s.simulado,s.eventos,s.ambiente.map(a=>[a.id,a.desactualizado]),s.vacas.map(v=>[v.vaca,v.fecha,v.desactualizado]),s.alertas]);
      const cambio=nueva!==firma;
      if(cambio){mostrarSensores(s);firma=nueva;}else $('sensor-estado').textContent=(s.simulado?'Datos simulados de la finca ':'Registros reales de la finca ')+s.finca+': '+s.eventos+' eventos, revisado a las '+new Date(s.actualizado).toLocaleTimeString('es-PA',{timeZone:'America/Panama'});
      if(cambio&&!primerSensor&&$('sensor-auto').checked)pendienteAuto=true;
      if(pendienteAuto&&$('sensor-auto').checked&&!ocupado){pendienteAuto=false;preguntar('Explica los cambios actuales en sensores y producción diaria de '+finca+'.',true);}
      if(!$('sensor-auto').checked)pendienteAuto=false;
      primerSensor=false;$('sensor-error').textContent='';
    }catch(e){$('sensor-error').textContent='No se pudo actualizar el seguimiento: '+e.message;}
  }
  $('sensor-aplicar').onclick=()=>{
    const f=$('sensor-finca').value.trim();if(!/^[A-Za-z0-9_.-]{1,80}$/.test(f)){$('sensor-error').textContent='Usa letras, números, puntos, guiones o guiones bajos para identificar la finca.';return;}
    finca=f;simulado=$('sensor-modo').value==='true';primerSensor=true;pendienteAuto=false;firma='';refrescar();
  };
  $('sensor-demo').onclick=async()=>{
    if(!conectado){$('sensor-error').textContent='El escenario requiere el servidor local. Abre iniciar.command.';return;}
    $('sensor-demo').disabled=true;
    try{const s=await api('/api/simular',{});finca='demo';simulado=true;$('sensor-finca').value=finca;$('sensor-modo').value='true';mostrarSensores(s);firma='';primerSensor=false;$('sensor-error').textContent='';}
    catch(e){$('sensor-error').textContent=e.message;}finally{$('sensor-demo').disabled=false;}
  };
  // versión web (GitHub Pages o la web de AIOROS): Gemma y los sensores viven en el equipo de la finca
  function modoWeb(){
    document.body.classList.add('gamma-web');
    $('gemma-estado').textContent='Gemma está apagado en la versión web';
    $('sensor-estado').textContent='Sin conexión con el equipo de la finca.';
    $('chat-respuestas').innerHTML='<div class="gamma-notice">Esta es la versión web: Gemma corre en el equipo de la finca, una PC o la Jetson, sin internet. Toca una de las preguntas sugeridas para ver un ejemplo con las cifras, la gráfica y los hallazgos verificados que salen del registro. Para escribir preguntas propias hace falta el equipo de la finca.</div>';
    $('sensor-resumen').innerHTML='<div class="gamma-notice">Esta es la versión web: los sensores llegan por MQTT al equipo de la finca. Toca <b>Cargar escenario simulado</b> para ver un ejemplo con una caída de producción y una alerta de calor.</div>';
    ['chat-enviar','chat-pregunta','sensor-aplicar','sensor-finca','sensor-modo','sensor-auto'].forEach(id=>{$(id).disabled=true;});
    $('chat-alcance').value='hato';$('chat-alcance').disabled=true;
    document.querySelectorAll('.gamma-chips button').forEach(b=>b.onclick=()=>{
      const r=GAMMA_EJEMPLOS.chat[b.dataset.ejemplo];if(!r)return;
      if(r.vaca_consultada)mostrar(r.vaca_consultada);
      mostrarRespuesta(b.dataset.pregunta,r);historial.push(b.dataset.pregunta);if(historial.length>10)historial.shift();
    });
    $('sensor-demo').onclick=()=>{
      mostrarSensores(GAMMA_EJEMPLOS.sensores);
      $('sensor-estado').textContent='Escenario simulado de la finca demo, calculado al generar esta página: '+GAMMA_EJEMPLOS.sensores.eventos+' eventos.';
    };
  }
  async function conectar(){
    if(!/^https?:$/.test(location.protocol)){modoWeb();return;}
    try{const s=await api('/api/sesion',undefined,5000);token=s.token;conectado=true;const e=await api('/api/estado',undefined,10000);
      $('gemma-estado').textContent=e.gemma.mensaje;$('gemma-estado').className='gamma-status '+(e.gemma.disponible?'listo':'');await refrescar();
    }catch(e){conectado=false;modoWeb();}
  }
  conectar();setInterval(()=>{if(!document.hidden)refrescar();},3000);
  window.GammaUI={calculoEconomico,dibujarGrafica};
})();
