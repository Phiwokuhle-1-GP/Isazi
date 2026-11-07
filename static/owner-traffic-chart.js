(function () {
  'use strict';
  const svg = document.getElementById('traffic-chart');
  const type = document.getElementById('traffic-chart-type');
  const labels = document.getElementById('traffic-labels');
  if (!svg || !type || !labels) return;
  let data;
  try { data = JSON.parse(svg.dataset.traffic); } catch (_) { return; }
  if (!Array.isArray(data) || !data.length) return;
  const ns = 'http://www.w3.org/2000/svg';
  function add(tag, attrs, content) {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (content !== undefined) node.textContent = content;
    svg.appendChild(node);
  }
  function draw() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const max = Math.max(1, ...data.map(row => Number(row[1]) || 0));
    for (let i=0;i<=4;i++) {
      const y=260-i*55;
      add('line',{x1:45,x2:885,y1:y,y2:y,stroke:'#e1e7e5'});
      add('text',{x:38,y:y+4,'text-anchor':'end',fill:'#40594e','font-size':14,'font-weight':'700'},String(Math.round(max*i/4)));
    }
    const step=820/Math.max(1,data.length-1);
    const points=data.map((r,i)=>[50+i*step,260-(Number(r[1])||0)/max*220]);

    // traffic-date-labels: spread up to seven UTC dates across the axis.
    const tickCount = Math.min(7, data.length);
    for (let tick = 0; tick < tickCount; tick++) {
      const i = tickCount === 1 ? 0 : Math.round(tick * (data.length-1) / (tickCount-1));
      const x = 50 + i*step;
      add('line', {x1:x,x2:x,y1:260,y2:265,stroke:'#a4b2aa'});
      add('text', {x:x,y:282,'text-anchor':i===0?'start':i===data.length-1?'end':'middle',fill:'#40594e','font-size':12,'font-weight':'700'}, String(data[i][0]));
    }

    if(type.value==='line') add('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#b59253','stroke-width':3});
    data.forEach((r,i)=>{
      const [x,y]=points[i];
      const hit = document.createElementNS(ns, type.value==='bar' ? 'rect' : 'circle');
      const attributes = type.value==='bar' ? {x:x-Math.min(10,step*.35),y:y,width:Math.min(20,step*.7),height:Math.max(1,260-y),fill:'#b59253'} : {cx:x,cy:y,r:5,fill:'#b59253'};
      Object.entries(attributes).forEach(([key,value]) => hit.setAttribute(key,value));
      const title = document.createElementNS(ns, 'title');
      title.textContent = String(r[0]) + ' — Page views: ' + String(r[1]);
      hit.appendChild(title);
      svg.appendChild(hit);
      if(labels.checked) add('text',{x:x,y:Math.max(12,y-7),'text-anchor':'middle',fill:'#233d32','font-size':12,'font-weight':'700'},String(r[1]));
    });
  }
  type.addEventListener('change',draw);
  labels.addEventListener('change',draw);
  draw();
}());
