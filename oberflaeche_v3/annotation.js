
const tincture={sand:"#70e3cf",metall:"#bcc8ed",unklar:"#f6c680",linie:"#fff6e2"};
const labels={sand:"Sand region",metall:"Bare plate",unklar:"Ambiguous region",linie:"Line candidate"};

export async function annotationView(root,h){
  const {get,request,esc,opt,pct,title,alert,metric,photo,label,jsonDetails}=h;
  const $=s=>root.querySelector(s);
  root.innerHTML=title("REFERENCE ANNOTATION","Annotate an exposure","Register the plate, mark visible sand or bare metal, trace candidate lines and flag ambiguity.");
  const [a,study]=await Promise.all([get("atlas"),get("studie").catch(()=>null)]);
  if(!root.isConnected)return;
  const index=new Map(a.bilder.map(q=>[q.id,q])), shortlist=study?.annotation?.stichprobe??a.bilder.filter(q=>q.bildvarianten);
  const included=new Set(shortlist.map(q=>q.id));
  const other=a.bilder.filter(q=>!included.has(q.id));
  const choices='<optgroup label="Review sample">'+shortlist.map(q=>opt(q.id,label(q))).join("")+'</optgroup>'+
    '<optgroup label="Other archive exposures">'+other.map(q=>opt(q.id,label(q))).join("")+'</optgroup>';
  root.insertAdjacentHTML("beforeend",alert("BLOCKED · independently adjudicated human reference. Local revisions track self-reported provenance.",true)+
    '<div class="frame"><aside class="panel controls"><h2>Reference session</h2>'+
    '<label class="field">Exposure<select id="annotation-case">'+choices+'</select></label>'+
    '<label class="field">Reviewer ID<input id="annotator" autocomplete="off" maxlength="80" required></label>'+
    '<label class="field">Origin<select id="origin">'+opt("manuell_selbstangabe","Manual · self-reported")+opt("assistiert","Assisted / consulted labels")+'</select></label>'+
    '<label class="field">Notes<textarea id="annotation-note" maxlength="1000" placeholder="Visibility, lighting or region notes"></textarea></label>'+
    '<p class="status">The workspace starts from the registered photo and contains no algorithmic labels. Viewing any prior revision disables the blind-session flag for this exposure until reload.</p>'+
    '<div class="mark-actions"><button id="save-version" class="primary">Save revision</button></div><div class="status" id="anno-status" role="status"></div></aside>'+
    '<div><section class="panel"><div class="kicker"><h2>Registered plate</h2><span class="tag" id="anno-id"></span></div>'+
    '<div class="mark-actions"><button id="geometry">Edit corners and center</button><button id="register" hidden>Apply registration</button><button id="cancel-geo" hidden>Cancel geometry edit</button></div>'+
    '<p class="status" id="anno-guide"></p>'+
    '<div class="annotation-work framepic"><img class="mark-image" id="anno-img" alt="Photo workspace for manual annotation">'+
    '<canvas class="markCanvas" id="anno-canvas" tabindex="0" aria-label="Annotation drawing surface. Select tools and click points. Enter finishes, Backspace undoes."></canvas></div>'+
    '<div class="workspace-tools anno-toolbar"><label class="field">Mark<select id="mark-type">'+Object.entries(labels).map(([k,v])=>opt(k,v)).join("")+'</select></label>'+
    '<button id="finish-mark">Finish mark</button><button id="undo-mark">Undo</button><button id="clear-mark">Clear draft</button></div>'+
    '<div id="mark-list" class="metric"></div></section>'+
    '<section class="panel"><h2>Revision history</h2><p>Load a revision to branch from it. Comparing two independent reviewer sessions requires external review of their provenance.</p>'+
    '<label class="field">Revision to load<select id="version"></select></label><button id="load-version">Load selected revision</button>'+
    '<div class="fields"><label class="field">Reference A<select id="reference-a"></select></label><label class="field">Comparison B<select id="reference-b"></select></label></div>'+
    '<button id="compare-marks">Compare revisions</button><div id="mark-comparison" role="status"></div><div id="mark-provenance"></div></section></div></div>');
  const canvas=$("#anno-canvas"), img=$("#anno-img"), context=canvas.getContext("2d"), status=$("#anno-status"), caseSelect=$("#annotation-case");
  const origin=$("#origin"), note=$("#annotation-note"), mark=$("#mark-type"), guide=$("#anno-guide");
  let q, geom, versions=[], shapes=[], points=[], parent=null, serial=0, busy=false;
  let mode="mark", corners=[], screw, currentImage=null;
  const inspected=new Set();
  function message(s){status.textContent=s;}
  function asset(url){
    const last=currentImage;currentImage=url.startsWith("blob:")?url:null;img.src=url;
    if(last)URL.revokeObjectURL(last);
  }
  function draw(){
    if(!img.complete||!img.naturalWidth)return;
    const w=img.clientWidth,h=img.clientHeight, ratio=Math.min(2,window.devicePixelRatio||1);
    if(canvas.width!==Math.round(w*ratio))canvas.width=Math.round(w*ratio);
    if(canvas.height!==Math.round(h*ratio))canvas.height=Math.round(h*ratio);
    context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,w,h);
    function shape(typ,pp,draft=false){
      if(!pp.length)return;
      context.beginPath();pp.forEach(([x,y],i)=>i?context.lineTo(x*w,y*h):context.moveTo(x*w,y*h));
      context.strokeStyle=tincture[typ];context.lineWidth=2.1;
      if(!draft&&typ!=="linie"){context.closePath();context.fillStyle=tincture[typ]+"44";context.fill();}
      context.stroke();
      if(draft) for(const [x,y] of pp){
        context.beginPath();context.arc(x*w,y*h,3.2,0,2*Math.PI);context.fillStyle=tincture[typ];context.fill();
      }
    }
    if(mode==="geometry"){
      shape("sand",corners,corners.length!==4);
      for(const [i,[x,y]] of corners.entries()){
        context.font="bold 14px system-ui";context.fillStyle="#ffffff";context.fillText(String(i+1),x*w+7,y*h+4);
      }
      if(screw)shape("unklar",[screw],true);
    }else{
      shapes.forEach(s=>shape(s.typ,s.punkte));shape(mark.value,points,true);
    }
  }
  function renderTools(){
    const ge=mode==="geometry";
    $("#geometry").hidden=ge;$("#register").hidden=!ge;$("#cancel-geo").hidden=!ge;
    $(".anno-toolbar").hidden=ge;
    $("#save-version").disabled=ge||busy;
    guide.textContent=ge?(corners.length<4?"Click four corners in clockwise order, starting with the upper left.":"Click the screw center, then apply registration."):
      "Click points on the photo. Mark both sand and bare plate where visible. Finish with Enter or the button. Backspace undoes the last point.";
    $("#mark-list").innerHTML=Object.entries(labels).map(([k,v])=>metric(v,shapes.filter(s=>s.typ===k).length)).join("");
    draw();
  }
  async function registered(g,token=serial){
    const data=await request("/api/entzerren/"+encodeURIComponent(q.id),{body:g,format:"blob"});
    if(token!==serial||!root.isConnected)return false;
    asset(URL.createObjectURL(data));return true;
  }
  function stash(){
    if(points.length||shapes.length)message("Changing registration requires clearing draft marks or loading a revision.");
    return !points.length&&!shapes.length;
  }
  function finish(){
    const min=mark.value==="linie"?2:3;
    if(new Set(points.map(p=>p.join(","))).size<min){message("This mark needs at least "+min+" different points.");return;}
    shapes.push({typ:mark.value,punkte:points});points=[];message("Mark added to draft.");renderTools();
  }
  function undo(){
    if(mode==="geometry"){if(screw)screw=null;else corners.pop();}
    else if(points.length)points.pop();else shapes.pop();
    renderTools();
  }
  canvas.addEventListener("click",event=>{
    if(busy)return;
    const r=canvas.getBoundingClientRect(), clamp=v=>Math.max(0,Math.min(1,v));
    const p=[clamp((event.clientX-r.left)/r.width),clamp((event.clientY-r.top)/r.height)];
    if(mode==="geometry"){if(corners.length<4)corners.push(p);else screw=p;}
    else if(points.length<2000)points.push(p);
    renderTools();
  });
  canvas.addEventListener("keydown",event=>{
    if(event.key==="Backspace"){event.preventDefault();undo();}
    if(event.key==="Enter"&&mode==="mark"){event.preventDefault();finish();}
  });
  $("#finish-mark").onclick=finish;$("#undo-mark").onclick=undo;
  $("#clear-mark").onclick=()=>{points=[];shapes=[];message("Draft marks cleared.");renderTools();};
  mark.onchange=()=>{if(points.length)message("The unfinished points now use the selected mark type.");draw();};
  $("#geometry").onclick=()=>{
    if(!q||busy||!stash())return;
    mode="geometry";corners=[];screw=null;asset(photo(q,"original"));renderTools();
  };
  $("#cancel-geo").onclick=async()=>{
    busy=true;renderTools();
    try{if(await registered(geom)){mode="mark";message("Previous registration restored.");}}
    catch(e){message(e.message);}
    finally{busy=false;renderTools();}
  };
  $("#register").onclick=async()=>{
    if(busy)return;
    if(corners.length!==4||!screw){message("Set four ordered corners and the screw center.");return;}
    const g={ecken:corners,schraube:screw,verdeckt:[]}, token=serial;
    busy=true;renderTools();
    try{
      if(await registered(g,token)){geom=g;mode="mark";message("Registration applied to this draft.");}
    }catch(e){if(token===serial)message(e.message);}
    finally{if(token===serial){busy=false;renderTools();}}
  };
  function options(){
    const html=versions.length?versions.map(v=>opt(v.revision,"v"+v.version+" · "+v.autor+" · "+v.revision.slice(0,8))).join(""):opt("","No saved revisions");
    for(const id of ["#version","#reference-a","#reference-b"])$(id).innerHTML=html;
    if(versions.length>1)$("#reference-b").selectedIndex=1;
    $("#load-version").disabled=!versions.length;$("#compare-marks").disabled=versions.length<2;
  }
  async function select(){
    const token=++serial;q=index.get(caseSelect.value);if(!q)return;
    geom=q.geometrie;versions=[];mode="mark";shapes=[];points=[];parent=null;busy=false;note.value="";
    origin.value=inspected.has(q.id)?"assistiert":"manuell_selbstangabe";
    $("#anno-id").textContent=q.id;$("#mark-comparison").innerHTML="";$("#mark-provenance").innerHTML="";
    asset(photo(q,"platte"));options();renderTools();message("New draft.");
    try{
      const v=await request("/api/annotation/"+encodeURIComponent(q.id));
      if(token===serial&&root.isConnected){versions=v;options();}
    }catch(e){if(token===serial)message(e.message);}
  }
  $("#load-version").onclick=async()=>{
    if(busy)return;
    const v=versions.find(x=>x.revision===$("#version").value);if(!v)return;
    const token=serial;busy=true;renderTools();
    try{
      if(!await registered(v.geometrie,token))return;
      geom=v.geometrie;parent=v.revision;
      shapes=structuredClone(v.formen);points=[];mode="mark";note.value=v.notiz;inspected.add(q.id);origin.value="assistiert";
      $("#mark-provenance").innerHTML=jsonDetails("Loaded revision provenance",{...v,formen:v.formen.length});message("Loaded version "+v.version+" as the parent of the current draft.");
    }catch(e){if(token===serial)message(e.message);}
    finally{if(token===serial){busy=false;renderTools();}}
  };
  $("#save-version").onclick=async()=>{
    if(busy||!q||mode!=="mark")return;
    if(points.length){message("Finish or undo the current mark before saving.");return;}
    const reviewer=$("#annotator");
    if(!reviewer.value.trim()){message("Enter a reviewer ID.");reviewer.focus();return;}
    const token=serial;busy=true;renderTools();
    try{
      const v=await request("/api/annotation/"+encodeURIComponent(q.id),{body:{autor:reviewer.value,
        herkunft:origin.value,vorgaenger:parent,geometrie:geom,formen:shapes,notiz:note.value,
        blindmodus:!inspected.has(q.id)&&origin.value==="manuell_selbstangabe"}});
      if(token!==serial||!root.isConnected)return;
      versions.unshift(v);parent=v.revision;options();message("Saved immutable revision "+v.revision.slice(0,8)+".");
      $("#mark-provenance").innerHTML=jsonDetails("Saved revision provenance",{...v,formen:v.formen.length});
    }catch(e){if(token===serial)message(e.message);}
    finally{if(token===serial){busy=false;renderTools();}}
  };
  $("#compare-marks").onclick=async()=>{
    const target=$("#mark-comparison"), A=$("#reference-a").value,B=$("#reference-b").value, token=serial;
    if(A===B){target.innerHTML=alert("Choose two different revisions.",true);return;}
    inspected.add(q.id);
    try{
      const args=new URLSearchParams({a:A,b:B});
      const v=await request("/api/vergleich/"+encodeURIComponent(q.id)+"?"+args);
      if(token!==serial||!root.isConnected)return;
      target.innerHTML='<div class="metric">'+metric("Joint labeled area",pct(v.abgedeckter_annotierter_bereich_rel))+
        metric("Sand IoU",pct(v.iou))+metric("B precision vs A",pct(v.praezision_b_gegen_a))+
        metric("B recall vs A",pct(v.recall_b_gegen_a))+metric("Line distance / side",pct(v.linienabstand_rel))+
        metric("Registration shift / side",pct(v.gitter_mittel_rel))+'</div><p class="status">'+
        esc("Agreement is measured on shared clear labels. Dashes indicate insufficient evidence for the statistic.")+'</p>';
    }catch(e){if(token===serial)target.innerHTML=alert(e.message,true);}
  };
  const ro=new ResizeObserver(draw);ro.observe(img);img.addEventListener("load",draw);
  caseSelect.onchange=select;select();
  return ()=>{ro.disconnect();if(currentImage)URL.revokeObjectURL(currentImage);};
}
