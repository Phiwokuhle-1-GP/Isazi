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
      add('text',{x:38,y:y+4,'text-anchor':'end',fill:'#62736c','font-size':12},String(Math.round(max*i/4)));
    }
    const step=820/Math.max(1,data.length-1);
    const points=data.map((r,i)=>[50+i*step,260-(Number(r[1])||0)/max*220]);
    if(type.value==='line') add('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#b59253','stroke-width':3});
    data.forEach((r,i)=>{
      const [x,y]=points[i];
      if(type.value==='bar') add('rect',{x:x-Math.min(10,step*.35),y:y,width:Math.min(20,step*.7),height:260-y,fill:'#b59253'});
      else add('circle',{cx:x,cy:y,r:3,fill:'#b59253'});
      if(labels.checked) add('text',{x:x,y:Math.max(12,y-7),'text-anchor':'middle',fill:'#314b40','font-size':10},String(r[1]));
    });
  }
  type.addEventListener('change',draw);
  labels.addEventListener('change',draw);
  draw();
}());
