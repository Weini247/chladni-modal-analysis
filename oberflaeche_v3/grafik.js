
const navy = [36, 85, 146], paper = [226, 236, 241], rust = [171, 88, 48];
const cyan = "#70e3cf", amber = "#f6c680", pale = "#a4b3c1";
const ctxOf = c => c.getContext("2d");

function rgb(v) {
  const q = Math.min(1, Math.abs(v));
  return paper.map((x, i) => Math.round(x + q * ((v < 0 ? navy : rust)[i] - x)));
}

export function nodal(ctx, values, n, side, offset = 0) {
  ctx.beginPath();
  for (let y = 0; y < n - 1; y++) for (let x = 0; x < n - 1; x++) {
    const grid = [[x,y],[x+1,y],[x+1,y+1],[x,y+1]];
    const points = [];
    for (let i = 0; i < 4; i++) {
      const [a,b] = grid[i], [c,d] = grid[(i+1)%4];
      const va = values[b*n+a], vb = values[d*n+c];
      if ((va >= 0) === (vb >= 0)) continue;
      const f = va/(va-vb);
      points.push([offset+(a+.5+f*(c-a))*side/n,offset+(b+.5+f*(d-b))*side/n]);
    }
    if (points.length === 4) {
      const center = grid.reduce((s,[i,j]) => s+values[j*n+i],0);
      if ((center >= 0) !== (values[y*n+x] >= 0)) points.push(points.shift());
    }
    for (let i = 0; i < points.length; i += 2) {
      ctx.moveTo(...points[i]); ctx.lineTo(...points[i+1]);
    }
  }
  ctx.stroke();
}

function canvasSize(canvas, fallback = 512) {
  const width = canvas.clientWidth || fallback, height = canvas.clientHeight || fallback;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.round(width*dpr), h = Math.round(height*dpr);
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w; canvas.height = h;
  }
  const ctx = ctxOf(canvas);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,width,height);
  return {ctx,width,height};
}

export function field(canvas, values, n, kind = "field") {
  const {ctx,width,height} = canvasSize(canvas);
  if (kind === "field") {
    const scratch = document.createElement("canvas");
    scratch.width = scratch.height = n;
    const small = ctxOf(scratch), im = small.createImageData(n,n);
    for (let i = 0; i < values.length; i++) im.data.set([...rgb(values[i]),255],4*i);
    small.putImageData(im,0,0);
    ctx.drawImage(scratch,0,0,width,height);
  }
  if (kind === "nodes") {
    ctx.fillStyle = "#121d27"; ctx.fillRect(0,0,width,height);
  }
  ctx.strokeStyle = kind === "field" ? "#172630" : cyan;
  ctx.lineWidth = kind === "field" ? 1.35 : 2;
  nodal(ctx,values,n,width);
}

export function scatter(canvas, series, labels) {
  const {ctx,width,height} = canvasSize(canvas);
  const x0 = 47, y0 = height-43, xmax = width-18, ymin = 18;
  const data = series.flatMap(s => s.points);
  if (!data.length) { ctx.fillStyle = pale; ctx.font = "14px system-ui"; ctx.fillText("No recorded frequencies with coverage.",x0,ymin+15); return; }
  const xs = data.map(p=>p[0]), ys = data.map(p=>p[1]);
  const lo = Math.min(...xs), hi = Math.max(...xs);
  const top = Math.max(.05, Math.ceil(Math.max(...ys)*20)/20);
  const x = f => x0+(lo===hi?.5:(f-lo)/(hi-lo))*(xmax-x0);
  const y = f => y0-(f/top)*(y0-ymin);
  ctx.font = "12px system-ui"; ctx.textAlign = "right";
  for (let j=0;j<=4;j++) {
    const p=top*j/4, py=y(p);
    ctx.beginPath(); ctx.moveTo(x0,py); ctx.lineTo(xmax,py); ctx.strokeStyle="#263844"; ctx.stroke();
    ctx.fillStyle=pale; ctx.fillText(Math.round(100*p)+"%",x0-7,py+4);
  }
  ctx.textAlign="center";
  for (let j=0;j<=(lo===hi?0:4);j++){
    const f=lo+j*(hi-lo)/4; ctx.fillStyle=pale;
    ctx.fillText(new Intl.NumberFormat("en",{maximumFractionDigits:1}).format(f),x(f),y0+19);
  }
  ctx.fillText(labels,(xmax+x0)/2,height-3);
  for (const s of series) {
    ctx.fillStyle=s.color;
    for (const [i,j,active] of s.points) {
      ctx.beginPath();ctx.arc(x(i),y(j),active?5.8:3.5,0,2*Math.PI);ctx.fill();
      if (active) {ctx.strokeStyle="#ffffff";ctx.lineWidth=1.4;ctx.stroke();}
    }
  }
}

function surface(canvas, field, n, camera) {
  const {ctx,width,height} = canvasSize(canvas);
  const {yaw, tilt, zoom} = camera, cos=Math.cos(yaw), sin=Math.sin(yaw);
  const sy=Math.sin(tilt), cy=Math.cos(tilt), size=zoom*Math.min(width,height*1.18)*.64;
  function project(x,y,z){
    const dx=x-.5,dy=y-.5, ry=dx*sin+dy*cos;
    return [width*.5+size*(dx*cos-dy*sin),height*.54+size*(ry*sy-z*cy),ry*cy+z*sy];
  }
  const sample = [];
  for(let i=0;i<n;i+=2)sample.push(i);
  if(sample.at(-1)!==n-1) sample.push(n-1);
  const tiles = [];
  for(let i=0;i<sample.length-1;i++) for(let j=0;j<sample.length-1;j++){
    const a=sample[i],b=sample[j],c=sample[i+1],d=sample[j+1];
    const vs=[[a,b],[c,b],[c,d],[a,d]].map(([x,y])=>[project(x/(n-1),y/(n-1),.32*field[y*n+x]),field[y*n+x]]);
    tiles.push({p:vs.map(v=>v[0]),tone:vs.reduce((s,v)=>s+v[1],0)/4,depth:vs.reduce((s,v)=>s+v[0][2],0)/4});
  }
  const border = [[0,0],[1,0],[1,1],[0,1],[0,0]].map(([x,y])=>project(x,y,-.35));
  ctx.fillStyle="#0d151f";ctx.fillRect(0,0,width,height);
  ctx.beginPath(); border.forEach(p=>ctx.lineTo(p[0],p[1]));ctx.strokeStyle="#586c80";ctx.lineWidth=1;ctx.stroke();
  tiles.sort((a,b)=>a.depth-b.depth);
  for(const t of tiles){
    ctx.beginPath();t.p.forEach(p=>ctx.lineTo(p[0],p[1]));ctx.closePath();
    ctx.fillStyle="rgb("+rgb(t.tone).join(",")+")";ctx.fill();
    ctx.strokeStyle="rgba(20,37,54,.38)";ctx.lineWidth=.62;ctx.stroke();
  }
  ctx.font="12px system-ui";ctx.fillStyle=pale;
  ctx.fillText("Normalized displacement",14,22);
  ctx.fillText("Drag to rotate · Scroll to zoom",14,height-14);
}

export function modeViewer(canvas, display) {
  let result, animation, start=0, time=0;
  const camera={yaw:-.56,tilt:.46,zoom:1};
  let down;
  function render(){
    if(!result || !canvas.isConnected) return;
    const [a,b]=result.felder, [f1,f2]=result.frequenzen_hz;
    const values=a.map((v,i)=>Math.cos(time)*v+(f2?Math.cos(time*f2/f1)*b[i]:0));
    if(display.value==="3d") surface(canvas,values,result.n,camera);
    else field(canvas,values,result.n,display.value);
  }
  const observer=new ResizeObserver(render);
  observer.observe(canvas);
  function loop(now){
    if(!canvas.isConnected) { observer.disconnect(); return; }
    time += start ? Math.min(now-start,80)*.003 : 0;
    start=now;render();animation=requestAnimationFrame(loop);
  }
  canvas.addEventListener("pointerdown",event=>{
    if(display.value!=="3d") return;
    down=[event.clientX,event.clientY];canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove",event=>{
    if(!down)return;
    camera.yaw+=(event.clientX-down[0])*.011;
    camera.tilt=Math.max(.04,Math.min(1.53,camera.tilt+(event.clientY-down[1])*.009));
    down=[event.clientX,event.clientY];render();
  });
  for(const e of ["pointerup","pointercancel","lostpointercapture"]) canvas.addEventListener(e,()=>{down=null;});
  canvas.addEventListener("wheel",event=>{
    if(display.value!=="3d")return;
    event.preventDefault();
    camera.zoom=Math.max(.48,Math.min(1.65,camera.zoom*Math.exp(-event.deltaY*.001)));
    render();
  },{passive:false});
  canvas.addEventListener("keydown",event=>{
    const delta={ArrowUp:[0,-.1],ArrowDown:[0,.1],ArrowLeft:[-.12,0],ArrowRight:[.12,0]}[event.key];
    if(!delta||display.value!=="3d")return;
    event.preventDefault();camera.yaw+=delta[0];camera.tilt=Math.max(.04,Math.min(1.53,camera.tilt+delta[1]));render();
  });
  display.addEventListener("change",()=>{
    canvas.parentElement.classList.toggle("mode-2d",display.value!=="3d");
    render();
  });
  return {
    set(data){result=data;time=0;render();},
    toggle(){
      if(animation){cancelAnimationFrame(animation);animation=undefined;start=0;return false;}
      animation=requestAnimationFrame(loop);return true;
    },
    destroy(){observer.disconnect();if(animation)cancelAnimationFrame(animation);}
  };
}

export const colors = {cyan,amber,pale};
