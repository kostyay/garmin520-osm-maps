'use strict';
const $ = id => document.getElementById(id);
const state = {metadata:null, features:[], disabled:new Set(), kinds:new Set(['polygons','lines','points']), night:false, ready:false, images:new Map(), unknown:[]};
const map = L.map('map',{zoomControl:false,minZoom:7,maxZoom:18,zoomAnimation:false,fadeAnimation:false}).setView([42.34,1.426],15);
window.previewMap = map;
L.control.zoom({position:'topright'}).addTo(map);
L.control.scale({imperial:false}).addTo(map);
map.attributionControl.setPrefix(false).addAttribution('Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · IMG/TYP browser approximation');
const canvas = L.DomUtil.create('canvas','easy-canvas',map.getPanes().overlayPane);
let controller, request = 0, gpx, hitFeatures = [];
function error(message) { $('error').textContent=message; $('error').hidden=!message; }
async function json(response) { const value=await response.json(); if(!response.ok) throw Error(value.error || 'The map could not be loaded.'); return value; }
function style(id) { return state.metadata.styles[id] || {kind:id.split(':')[0],code:Number(id.split(':')[1]),name:`Unstyled ${id}`,dayColor:'#df00d8',lineWidth:2}; }
function visible(id) { return !state.disabled.has(id) && state.kinds.has(style(id).kind); }
function appearance(item, suffix) { return item[(state.night?'night':'day')+suffix] || item['day'+suffix]; }
function paint(context,item) {
  const pattern=appearance(item,'Pattern');
  return pattern ? context.createPattern(state.images.get(pattern.url),'repeat') : appearance(item,'Color') || '#777';
}
function area(points) { return Math.abs(points.reduce((sum,p,i)=>{const q=points[(i+1)%points.length];return sum+p[0]*q[1]-q[0]*p[1];},0)); }
function draw() {
  if(!state.metadata) return;
  const size=map.getSize(), ratio=devicePixelRatio||1;
  canvas.width=size.x*ratio; canvas.height=size.y*ratio;
  canvas.style.width=`${size.x}px`; canvas.style.height=`${size.y}px`;
  L.DomUtil.setPosition(canvas,map.containerPointToLayerPoint([0,0]));
  const ctx=canvas.getContext('2d'); ctx.scale(ratio,ratio);
  const projected=state.features.filter(f=>visible(f[0])).map(f=>({id:f[0],p:f[1].map(([lon,lat])=>map.latLngToContainerPoint([lat,lon])),label:f[2],item:style(f[0])}));
  const polygons=projected.filter(f=>f.item.kind==='polygons');
  const lines=projected.filter(f=>f.item.kind==='lines'), points=projected.filter(f=>f.item.kind==='points');
  function path(p) { ctx.beginPath(); p.forEach((v,i)=>i?ctx.lineTo(v.x,v.y):ctx.moveTo(v.x,v.y)); }
  // Leaflet points expose x/y; area ordering uses coordinate arrays.
  polygons.sort((a,b)=>area(b.p.map(p=>[p.x,p.y]))-area(a.p.map(p=>[p.x,p.y])));
  for(const f of polygons) { path(f.p);ctx.closePath();ctx.fillStyle=paint(ctx,f.item);ctx.fill(); }
  ctx.lineJoin='round';
  for(const f of lines) {
    const icon=appearance(f.item,'Pattern'), width=icon?icon.height:Math.max(f.item.lineWidth||1,1);
    if(f.item.borderWidth) { path(f.p);ctx.strokeStyle=appearance(f.item,'BorderColor')||'#777';ctx.lineWidth=f.item.borderWidth;ctx.stroke(); }
    if(icon) {
      let phase=0;
      for(let i=1;i<f.p.length;i++) {
        const a=f.p[i-1],b=f.p[i],length=Math.hypot(b.x-a.x,b.y-a.y);
        ctx.save();ctx.translate(a.x,a.y);ctx.rotate(Math.atan2(b.y-a.y,b.x-a.x));ctx.translate(-phase,-width/2);
        ctx.fillStyle=paint(ctx,f.item);ctx.fillRect(phase,0,length,width);ctx.restore();phase=(phase+length)%icon.width;
      }
    } else { path(f.p);ctx.strokeStyle=paint(ctx,f.item);ctx.lineWidth=width;ctx.stroke(); }
  }
  for(const f of points) {
    const icon=appearance(f.item,'Icon'), p=f.p[0];
    if(icon) ctx.drawImage(state.images.get(icon.url),p.x-icon.width/2,p.y-icon.height/2);
    else { ctx.beginPath();ctx.arc(p.x,p.y,2,0,2*Math.PI);ctx.fillStyle=paint(ctx,f.item);ctx.fill(); }
  }
  if($('labels').checked) {
    const occupied=[];ctx.font='11px Arial';ctx.lineWidth=3;
    for(const f of [...points,...lines]) {
      if(!f.label || (f.item.kind==='lines' && [32,33,34].includes(f.item.code))) continue;
      const p=f.p[Math.floor(f.p.length/2)],text=f.label.slice(0,46), w=ctx.measureText(text).width;
      const rect=[p.x+5,p.y-18,p.x+w+12,p.y];
      if(rect[0]<0 || rect[2]>size.x || rect[1]<0 || rect[3]>size.y || occupied.some(b=>rect[0]<b[2]&&rect[2]>b[0]&&rect[1]<b[3]&&rect[3]>b[1]))continue;
      occupied.push(rect);ctx.strokeStyle=state.night?'#181818':'#fff';ctx.fillStyle=state.night?'#ddd':'#394435';ctx.strokeText(text,p.x+8,p.y-5);ctx.fillText(text,p.x+8,p.y-5);
    }
  }
  hitFeatures=[...points,...lines,...polygons];
}
function legend() {
  const counts=new Map();for(const [id] of state.features)counts.set(id,(counts.get(id)||0)+1);
  const search=$('type-search').value.toLowerCase();$('layer-list').replaceChildren();
  for(const [id,count] of [...counts].sort((a,b)=>style(a[0]).name.localeCompare(style(b[0]).name))) {
    const item=style(id), title=`${item.name} · ${item.kind} · 0x${item.code.toString(16)}`;
    if(!title.toLowerCase().includes(search))continue;
    const row=document.createElement('label');row.className='layer-row';row.title=title;
    const input=document.createElement('input');input.type='checkbox';input.checked=!state.disabled.has(id);input.setAttribute('aria-label',title);
    input.addEventListener('change',()=>{input.checked?state.disabled.delete(id):state.disabled.add(id);draw();});
    const sample=document.createElement('canvas');sample.width=64;sample.height=28;sample.setAttribute('aria-hidden','true');
    const ctx=sample.getContext('2d'), icon=appearance(item,'Icon');
    if(icon)ctx.drawImage(state.images.get(icon.url),(64-icon.width)/2,(28-icon.height)/2);
    else {ctx.fillStyle=paint(ctx,item);ctx.fillRect(0,10,64,8);}
    const label=document.createElement('span');label.textContent=`${item.name} · 0x${item.code.toString(16)}`;
    const number=document.createElement('span');number.className='layer-count';number.textContent=count.toLocaleString();
    row.append(input,sample,label,number);$('layer-list').append(row);
  }
  $('type-status').textContent=`${counts.size} types · ${state.features.length.toLocaleString()} features in this view`+(state.unknown.length?` · ${state.unknown.length} types lack TYP definitions (magenta fallback)`:' · all have TYP definitions');
}
async function refresh() {
  if(!state.metadata || !state.ready)return;
  if(controller)controller.abort();controller=new AbortController();const ticket=++request;
  const b=map.getBounds(),bbox=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(',');
  $('load-status').textContent='Reading map detail… The first view of a tile can take several seconds.';
  try {
    const value=await json(await fetch(`api/features?map=${state.metadata.id}&bbox=${bbox}&zoom=${map.getZoom()}`,{signal:controller.signal}));
    if(ticket!==request)return;
    state.features=value.features;state.unknown=value.unknownTypes;
    draw();legend();error('');$('load-status').textContent='Map loaded. Pan, zoom or click a feature to inspect it.';
    $('detail-status').textContent=`${value.resolution}-bit detail · zoom ${map.getZoom()} · browser approximation`;
    document.body.dataset.ready='true';
  } catch(e) { if(e.name!=='AbortError' && ticket===request){state.features=[];draw();legend();error(e.message);$('load-status').textContent='No map detail shown for this view.';} }
}
async function openMap(metadata) {
  if(controller)controller.abort();request++;
  state.ready=false;state.metadata=metadata.id?metadata:null;state.features=[];state.disabled.clear();state.images.clear();
  if(!metadata.id){$('map-size').textContent='No IMG loaded';return;}
  const jobs=[];
  for(const item of Object.values(metadata.styles)) for(const field of ['dayIcon','nightIcon','dayPattern','nightPattern']) {
    const icon=item[field];if(!icon || state.images.has(icon.url))continue;
    const image=new Image();state.images.set(icon.url,image);jobs.push(new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('A TYP symbol could not be loaded.'));image.src=icon.url;}));
  }
  await Promise.all(jobs);state.ready=true;
  $('map-size').textContent=`${(metadata.bytes/1e6).toFixed(2)} MB · embedded TYP`;$('tile-count').textContent=`${metadata.tiles} tiles`;
  const [w,s,e,n]=metadata.bounds;
  if(!(w<1.426&&e>1.426&&s<42.34&&n>42.34))map.fitBounds([[s,w],[n,e]],{animate:false});
  await refresh();
}
map.on('moveend',refresh);map.on('resize',draw);
map.on('mousemove',e=>{$('cursor-position').textContent=`${e.latlng.lat.toFixed(4)}° · ${e.latlng.lng.toFixed(4)}°`;});
map.on('click',e=>{
  const click=map.latLngToContainerPoint(e.latlng);let found=null,distance=9;
  for(const f of hitFeatures) {
    if(f.item.kind==='polygons')continue;
    for(let i=0;i<f.p.length;i++) {
      const d=i?L.LineUtil.pointToSegmentDistance(click,f.p[i-1],f.p[i]):click.distanceTo(f.p[i]);
      if(d<distance){distance=d;found=f;}
    }
  }
  if(!found) for(const f of hitFeatures.filter(f=>f.item.kind==='polygons')) {
    let inside=false;
    for(let i=0,j=f.p.length-1;i<f.p.length;j=i++) {const a=f.p[i],b=f.p[j];if((a.y>click.y)!==(b.y>click.y)&&click.x<(b.x-a.x)*(click.y-a.y)/(b.y-a.y)+a.x)inside=!inside;}
    if(inside){found=f;break;}
  }
  if(found){const content=document.createElement('div');content.textContent=`${found.item.name} · ${found.item.kind} · 0x${found.item.code.toString(16)}${found.label?' — '+found.label:''}`;L.popup().setLatLng(e.latlng).setContent(content).openOn(map);}
});
$('img-file').addEventListener('change',async e=>{
  const file=e.target.files[0];if(!file)return;
  if(file.size>256*1024**2){error('Choose an IMG smaller than 256 MiB.');return;}
  $('img-file').disabled=true;
  $('load-status').textContent='Opening IMG and reading its embedded style…';error('');
  try { await openMap(await json(await fetch('api/map',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Map-Name':encodeURIComponent(file.name)},body:file}))); }
  catch(errorValue){error(errorValue.message);$('load-status').textContent=state.metadata?'The previous map is still loaded.':'No map loaded. Choose another IMG.';}
  e.target.value='';e.target.disabled=false;
});
$('fit-map').addEventListener('click',()=>{if(state.metadata){const [w,s,e,n]=state.metadata.bounds;map.fitBounds([[s,w],[n,e]],{animate:false});}});
for(const b of document.querySelectorAll('[data-place]'))b.addEventListener('click',()=>{const places={andorra:[42.5063,1.5218],seu:[42.3576,1.456],arfa:[42.34,1.426]};map.setView(places[b.dataset.place],15,{animate:false});});
for(const input of document.querySelectorAll('[data-kind]'))input.addEventListener('change',()=>{input.checked?state.kinds.add(input.dataset.kind):state.kinds.delete(input.dataset.kind);draw();});
$('night').addEventListener('change',e=>{state.night=e.target.checked;document.body.classList.toggle('night',state.night);draw();legend();});
$('labels').addEventListener('change',draw);$('type-search').addEventListener('input',legend);
$('toggle-all').addEventListener('click',()=>{const ids=[...new Set(state.features.map(f=>f[0]))],enable=ids.every(id=>state.disabled.has(id));for(const id of ids)enable?state.disabled.delete(id):state.disabled.add(id);$('toggle-all').textContent=enable?'Hide all':'Show all';draw();legend();});
$('gpx-file').addEventListener('change',async e=>{
  try {
    const file=e.target.files[0];if(!file)return;
    const doc=new DOMParser().parseFromString(await file.text(),'application/xml');
    if(doc.querySelector('parsererror')||doc.documentElement.localName!=='gpx')throw Error('Choose a valid GPX file.');
    const segments=[...doc.getElementsByTagName('*')].filter(e=>['trkseg','rte'].includes(e.localName)).map(seg=>[...seg.getElementsByTagName('*')].filter(p=>['trkpt','rtept'].includes(p.localName)&&p.getAttribute('lat')?.trim()&&p.getAttribute('lon')?.trim()).map(p=>[Number(p.getAttribute('lat')),Number(p.getAttribute('lon'))]).filter(([lat,lon])=>Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=85&&Math.abs(lon)<=180)).filter(seg=>seg.length>1);
    if(!segments.length)throw Error('This GPX contains no track or route segments.');
    if(gpx)map.removeLayer(gpx);gpx=L.polyline(segments,{color:'#c22382',weight:4,interactive:false,pane:'markerPane'}).addTo(map);map.fitBounds(gpx.getBounds(),{padding:[35,35],maxZoom:16,animate:false});
    $('clear-course').hidden=false;$('course-status').textContent=`${file.name} · stays in this browser`;error('');
  }catch(e){error(e.message);}
});
$('clear-course').addEventListener('click',()=>{if(gpx)map.removeLayer(gpx);gpx=null;$('clear-course').hidden=true;$('gpx-file').value='';$('course-status').textContent='Your GPX stays in this browser.';});
fetch('api/map').then(json).then(openMap).catch(e=>error(e.message));
