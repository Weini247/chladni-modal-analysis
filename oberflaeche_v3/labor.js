
import {field,scatter,modeViewer,colors} from "/grafik.js";
import {annotationView} from "/annotation.js";

const app=document.querySelector("#app"), home=app.innerHTML;
const $=(root,selector)=>root.querySelector(selector);
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const fmt=(x,d=2)=>x==null?"—":new Intl.NumberFormat("en",{maximumFractionDigits:d}).format(x);
const pct=(x,d=2)=>x==null?"—":fmt(x*100,d)+"%";
const opt=(x,y=x)=>'<option value="'+esc(x)+'">'+esc(y)+'</option>';
const photo=(q,type)=>"/foto/"+encodeURIComponent(q.id)+"/"+type;
const cache=new Map();
const aliases={"Bilder 2030":"2,090–2,096 Hz","Bilder 4120":"4,122–4,128 Hz","Bilder 3720":"3,720–3,726 Hz control",
  navier:"Simply supported · Navier",frei:"Free edges",zentralpunkt:"Free edges + point constraint",federflaeche:"Free edges + spring patch",
  anschluss:"Free edges + distributed contact",historisch:"Historical cosine model",alle:"Full catalogue",nur_einzel:"Single modes only",
  tolerantes_f1:"Tolerant F1 distance",anschluss_grad24:"Contact · degree 24","anschluss_steifigkeit_0.5":"Contact · half stiffness",
  anschluss_steifigkeit_2:"Contact · double stiffness",anschluss_radius_groesser:"Contact · radius × 1.5",
  ideal:"Ideal",breit_diffus:"Diffuse band",unterbrochen:"Interrupted lines",registrierung:"Registration shift",
  einzel:"Single mode",paar:"Mode pair",null:"Out-of-family control"};
const name=x=>aliases[x]??x;
const title=(tag,h,p)=>'<header><p class="eyebrow">'+tag+'</p><h1>'+h+'</h1><p>'+p+'</p></header>';
const alert=(s,bad=false)=>'<div class="notice'+(bad?' bad':'')+'" role="status">'+esc(s)+'</div>';
const metric=(label,x)=>"<span>"+esc(label)+" <b>"+esc(x)+"</b></span>";
const table=(head,rows)=>'<div class="scroll"><table><thead><tr>'+head.map(s=>"<th scope='col'>"+esc(s)+"</th>").join("")+
  "</tr></thead><tbody>"+rows.map(row=>"<tr>"+row.map(s=>"<td>"+esc(s)+"</td>").join("")+"</tr>").join("")+"</tbody></table></div>";
const jsonDetails=(caption,x)=>'<details class="summary"><summary>'+esc(caption)+'</summary><pre>'+esc(JSON.stringify(x,null,2))+"</pre></details>";
const exportsFor=f=>'<div class="exports">'+["png","svg","pdf"].map(x=>'<a href="/figur/'+f+"."+x+'" download>'+x.toUpperCase()+"</a>").join("")+"</div>";
const say=(el,s)=>{el.textContent=s;};
const bindZoom=img=>{img.addEventListener("click",()=>img.classList.toggle("zoomed"));};

async function request(url,{body,format="json"}={}){
  const options=body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-Chladni-Local":"1"},body:JSON.stringify(body)};
  const r=await fetch(url,options);
  if(!r.ok){
    const error=await r.json().catch(()=>null);
    throw new Error(error?.fehler??"The local request failed ("+r.status+").");
  }
  return format==="blob"?r.blob():r.json();
}
function get(key){
  if(!cache.has(key))cache.set(key,request("/api/"+key).catch(e=>{cache.delete(key);throw e;}));
  return cache.get(key);
}
function samples(a){
  return [...a].sort((x,y)=>(x.hz??Infinity)-(y.hz??Infinity)||x.id.localeCompare(y.id));
}
function label(q){return (q.hz==null?"Unknown frequency":fmt(q.hz)+" Hz")+" · "+q.id;}

async function start(root){
  const evidence=$(root,"#home-evidence");
  const [a,g]=await Promise.allSettled([get("atlas"),get("gap")]);
  if(!evidence.isConnected)return;
  if(a.status==="rejected"){evidence.innerHTML=alert(a.reason.message,true);return;}
  const counts=[[a.value.bilder.length,"experimental full frames"],[a.value.serien.length,"recorded series"]];
  if(g.status==="fulfilled"){
    const c=g.value.ablationsstudien.find(x=>x.name==="alle");counts.push([c.treffer+"/"+c.n,"accepted control reconstructions"]);
  }
  evidence.innerHTML=counts.map(([n,s])=>"<div><strong>"+esc(n)+"</strong><span>"+s+"</span></div>").join("");
}

async function atlas(root,params){
  root.innerHTML=title("EXPERIMENT","Experimental atlas","Browse individual exposures and compare sand geometry across recorded frequencies.");
  const a=await get("atlas"), st=get("studie").catch(()=>null);
  if(!root.isConnected)return;
  root.insertAdjacentHTML("beforeend",'<div class="frame"><aside class="panel controls"><h2>Recorded series</h2>'+
    '<label class="field">Series<select id="series">'+a.serien.map(x=>opt(x.serie,name(x.serie)+" · "+x.fotos+" frames")).join("")+'</select></label>'+
    '<label class="field">Exposure<select id="exposure"></select></label><label class="field">Recorded step <output id="stepno"></output><input id="step" type="range" min="0" value="0"></label>'+
    '<div class="list"><button id="prev">Previous</button><button id="next">Next</button></div>'+
    '<label class="field">Compare series<select id="compare">'+opt("","Choose series")+a.serien.map(x=>opt(x.serie,name(x.serie))).join("")+'</select></label>'+
    '<div id="seriesnote" class="status"></div></aside><div><div class="panel"><div class="kicker"><h2 id="frame-title"></h2><span id="frame-id" class="tag"></span></div>'+
    '<div id="variants" class="list"></div><div id="atlas-picture" class="mainFigure square"><img class="zoomable" alt="Selected experimental frame"></div>'+
    '<div id="quality"></div><div id="provenance"></div></div>'+
    '<div class="panel"><h2>Segmented sand coverage</h2><div id="legend" class="metric"></div><canvas class="plot" aria-label="Observed sand coverage by recorded frequency"></canvas><div id="comparetable"></div></div>'+
    '<div class="panel" id="robust"><h2>Image sensitivity</h2><p>Loading the registered perturbation study…</p></div></div></div>');
  const series=$(root,"#series"), compare=$(root,"#compare"), exposure=$(root,"#exposure"), step=$(root,"#step"), canvas=$(root,".plot");
  const image=$(root,".zoomable"), pic=$(root,"#atlas-picture"), layers=$(root,"#variants");
  const buttons=[["platte","Registered plate"],["original","Original preview"],["maske","Sand mask"],["linien","Line overlay"]];
  let group=[],current=0,layer="platte",study=null;
  bindZoom(image);
  const forSeries=v=>samples(a.bilder.filter(q=>q.serie===v));
  function chart(){
    const qq=group[current];
    const rows=[{ id:series.value,color:colors.cyan},...(compare.value?[{id:compare.value,color:colors.amber}]:[])];
    $(root,"#legend").innerHTML=rows.map(x=>metric(x.color===colors.cyan?"●":"○",name(x.id))).join("");
    scatter(canvas,rows.map(x=>({...x,points:forSeries(x.id).filter(r=>r.hz!=null&&r.abdeckung_rel!=null).map(r=>[r.hz,r.abdeckung_rel,r.id===qq?.id])})),"Recorded excitation frequency [Hz]");
    $(root,"#comparetable").innerHTML=table(["Series","Frames","Frequencies","Median coverage","Same-frequency pairs"],rows.map(x=>{
      const t=a.serien.find(z=>z.serie===x.id);return [name(x.id),t.fotos,t.frequenzen.length,pct(t.flaechenanteil_median),t.wiederholungsbeobachtungen.length];
    }));
  }
  function sensitivity(){
    const el=$(root,"#robust"), s=study?.sweeps?.[series.value];
    if(!s){el.innerHTML="<h2>Image sensitivity</h2><p>Controlled settings are available for the three target series.</p>";return;}
    const pair=Object.entries(s.sieger_haeufigkeiten).map(([q,n])=>[JSON.parse(q).map(x=>fmt(x)).join(" → "),n]);
    el.innerHTML="<h2>Image sensitivity</h2><p>Largest change in extracted lines across "+Object.keys(s.varianten).length+" algorithmic settings.</p>"+
      table(["Excitation step [Hz]","Settings with largest change"],pair)+
      table(["Distinct exposures at the same frequency","Frequency [Hz]","Mean line distance [% of side]"],s.wiederholungen.map(x=>[x.id_a+" / "+x.id_b,fmt(x.hz),pct(x.abstand_rel)]))+
      exportsFor("sweeps");
  }
  function render(){
    const q=group[current];if(!q)return;
    step.value=current;exposure.value=q.id;say($(root,"#stepno"),(current+1)+" / "+group.length);
    $(root,"#prev").disabled=current===0;$(root,"#next").disabled=current===group.length-1;
    say($(root,"#frame-title"),q.hz==null?"Frequency unresolved":fmt(q.hz)+" Hz");say($(root,"#frame-id"),q.id);
    pic.classList.toggle("original",layer==="original");
    image.classList.remove("zoomed");image.src=photo(q,layer);image.alt=buttons.find(x=>x[0]===layer)[1]+" for "+q.id;
    layers.innerHTML=buttons.map(([k,v])=>'<button data-layer="'+k+'" aria-pressed="'+(k===layer)+'">'+v+"</button>").join("");
    $(root,"#quality").innerHTML='<div class="metric">'+metric("Sand area",pct(q.abdeckung_rel))+
      metric("Local radius / side",pct(q.breite_edt_median_rel))+metric("Skeleton pixels",fmt(q.skelettpixel,0))+
      metric("Connected traces",fmt(q.skelett_komponenten_8,0))+metric("Endpoints",fmt(q.endpunkte_8,0))+'</div>'+
      '<p class="status">'+esc(q.flags?.length?q.flags.join(" · "):"No archive quality flags on this frame.")+"</p>";
    $(root,"#provenance").innerHTML=jsonDetails("Frequency evidence, registration and SHA-256",
      {source:q.pfad,sha256:q.sha256,frequency_status:q.frequenzstatus,evidence:q.frequenzbelege,
        registration:q.registrierung,corners:q.geometrie,recording:q.exif,coverage_grid:q.dichte_4x4,d4_sand_iou:q.d4_sand_iou})+
      (q.bildvarianten?'<a class="button subtle" href="#inverse?id='+encodeURIComponent(q.id)+'">Inspect reconstruction</a>':"");
    chart();
  }
  function selectSeries(){
    group=forSeries(series.value);current=0;step.max=Math.max(0,group.length-1);
    exposure.innerHTML=group.map(q=>opt(q.id,label(q))).join("");
    say($(root,"#seriesnote"),group.length+" archived exposures. Duplicate frequencies retain distinct frames.");
    render();sensitivity();
  }
  layers.addEventListener("click",event=>{ if(event.target.dataset.layer){layer=event.target.dataset.layer;render();} });
  series.addEventListener("change",selectSeries);compare.addEventListener("change",chart);
  exposure.addEventListener("change",()=>{current=group.findIndex(q=>q.id===exposure.value);render();});
  step.addEventListener("input",()=>{current=Number(step.value);render();});
  $(root,"#prev").onclick=()=>{current--;render();};$(root,"#next").onclick=()=>{current++;render();};
  const q=a.bilder.find(row=>row.id===params.get("id"));
  series.value=q?.serie??a.versuchsserien[0];selectSeries();
  if(q){current=group.findIndex(r=>r.id===q.id);render();}
  const ro=new ResizeObserver(chart);ro.observe(canvas);
  st.then(s=>{if(root.isConnected){study=s;sensitivity();}});
  return ()=>ro.disconnect();
}

const num=(key,label,value,min,max,step)=>'<label class="field">'+label+'<input required name="'+key+'" type="number" value="'+value+'" min="'+min+'" max="'+max+'" step="'+step+'"></label>';
async function modes(root){
  root.innerHTML=title("SIMULATION","Numerical mode lab","Solve the plate eigenproblem, vary the central contact and inspect normalized mode shapes.");
  root.insertAdjacentHTML("beforeend",'<div class="frame"><form class="panel controls"><h2>Plate and support</h2>'+
    '<label class="field">Model<select name="modell">'+["anschluss","federflaeche","zentralpunkt","frei","navier","historisch"].map(x=>opt(x,name(x))).join("")+'</select></label>'+
    '<div class="fields">'+num("seite_m","Side [m]",.18,.06,.5,.001)+num("dicke_mm","Thickness [mm]",3,.4,10,.1)+num("e_gpa","Young’s modulus [GPa]",69,15,300,1)+num("rho","Density [kg/m³]",2700,800,11000,1)+num("nu","Poisson ratio",.35,-.1,.48,.01)+num("grad","Ritz degree",20,8,24,1)+'</div>'+
    '<details class="summary" open><summary>Contact parameters</summary><div class="fields">'+num("radius_mm","Radius [mm]",6,1,24,.1)+num("k_n_m","Stiffness [N/m]",200000,2000,2000000,1)+num("rotation_nm","Rotation [N·m]",1.5,0,20,.1)+num("masse_g","Mass [g]",18,0,120,1)+'</div></details>'+
    '<div class="fields">'+num("mode","Mode",4,1,30,1)+num("mode2","Second mode",0,0,30,1)+num("mischung_deg","Mix angle [°]",0,-90,90,1)+'</div>'+
    '<label class="field"><input name="konvergenz" type="checkbox"> Compare another Ritz degree</label>'+
    '<button type="submit" class="primary">Compute modes</button><div class="status" role="status"></div></form>'+
    '<div><div class="panel"><div class="kicker"><h2 id="mode-title">Displacement field</h2><span class="tag violet">MODEL</span></div>'+
    '<div class="workspace-tools"><label class="field">View<select id="display"><option value="3d">3D surface</option><option value="field">2D signed displacement</option><option value="nodes">Nodal contours</option></select></label>'+
    '<button id="animate" disabled>Play phase</button></div><div class="mainFigure"><canvas class="mode3d" tabindex="0" aria-label="Computed displacement. Use arrow keys to rotate the 3D view."></canvas></div>'+
    '<div class="metric" id="mode-metrics"></div><div class="sign-scale" aria-label="Signed displacement scale from negative blue to positive rust"><span>−1</span><span>0</span><span>+1</span></div><p>Color shows signed normalized displacement. Animation uses slowed relative phase. The optional second mode uses its computed frequency ratio. Choose 0 to disable the second mode.</p>'+
    '</div><div class="panel" id="mode-diagnostics"><h2>Numerical diagnostics</h2><p>Small-deflection, homogeneous thin-plate model. The central contact and coherent superposition are illustrative assumptions.</p></div></div></div>');
  const view=modeViewer($(root,"canvas"),$(root,"#display"));
  const form=$(root,"form"), button=$(form,"button"), status=$(form,".status"), anim=$(root,"#animate");
  anim.onclick=()=>{anim.textContent=view.toggle()?"Pause phase":"Play phase";};
  async function solve(event){
    event?.preventDefault();
    button.disabled=true;say(status,"Computing eigenfields…");
    try{
      const d=Object.fromEntries(new FormData(form));
      d.konvergenz=form.elements.konvergenz.checked;
      const r=await request("/api/moden",{body:d});
      if(!root.isConnected)return;
      view.set(r);anim.disabled=false;say(status,"Field computed.");
      say($(root,"#mode-title"),name(r.modell));
      $(root,"#mode-metrics").innerHTML=r.frequenzen_hz.map((f,i)=>metric("Eigenfrequency "+(i+1),fmt(f)+" Hz")).join("")+
        metric(r.modell==="historisch"?"Reference":"Ritz degree",r.modell==="historisch"?"Cosine approximation":r.grad);
      const data=r.numerische_diagnose;
      const refinement=r.gradvergleich;
      $(root,"#mode-diagnostics").innerHTML='<h2>Numerical diagnostics</h2><p>Small-deflection, homogeneous thin-plate model. Computed modes do not establish the vibration of the GP2 apparatus.</p>'+
       (data?jsonDetails("Eigenproblem residuals and mass orthogonality",data):alert("The historical cosine model is an illustrative reference."))+
       (refinement?'<h3>Ritz degrees '+r.grad+' and '+refinement.grad_referenz+'</h3>'+table(
         ["Current modes","Comparison modes","Cluster frequency change","Projector overlap","Dimension change"],
         refinement.unterraeume.filter(u=>u.a.includes(r.mode)||u.a.includes(r.mode2)).map(u=>[
           u.a.join(", "),u.b.join(", "),pct(u.frequenz_delta_rel,4),fmt(u.projektor_overlap,6),u.dimensionswechsel?"Yes":"No"]))+
         jsonDetails("All matched subspaces",refinement.unterraeume):"")+
       '<p><a class="button subtle" href="#validation">Open degree convergence and benchmarks</a></p>';
    }catch(e){say(status,e.message);if(!anim.disabled)status.textContent+=" The previous field is still displayed.";}
    finally{button.disabled=false;}
  }
  form.addEventListener("submit",solve);solve();
  return ()=>view.destroy();
}

function rankText(r){
  return ({KEIN_BELASTBARER_TREFFER:"Abstained · fit check failed",
    NICHT_EINDEUTIG_IDENTIFIZIERBAR:"Abstained · competing families remain close",
    ZU_WENIG_LINIENEVIDENZ:"Abstained · insufficient visible lines",
    KANDIDAT_IM_BEOBACHTUNGSMODELL:"Candidate under the observation model"})[r]??r;
}

async function inverse(root,params){
  root.innerHTML=title("INFERENCE","Inverse reconstruction","Compare extracted sand traces with ranked model families. Selection uses fit stripes and the decision uses disjoint check stripes.");
  const a=await get("atlas");
  if(!root.isConnected)return;
  const list=samples(a.bilder.filter(q=>a.versuchsserien.includes(q.serie)));
  root.insertAdjacentHTML("beforeend",'<div class="frame"><form class="panel controls"><h2>Observed pattern</h2>'+
    '<label class="field">Exposure<select id="case">'+list.map(q=>opt(q.id,label(q))).join("")+'</select></label>'+
    num("schwelle","Sand cutoff",.10,.05,.18,.005)+
    '<button class="primary" type="submit">Extract and rank</button><div class="status" role="status"></div><p class="status">The check-distance and separation limits remain fixed when the extraction changes.</p></form>'+
    '<div><div id="decision"></div><div class="grid2" id="inverse-figures">'+
    '<figure class="panel"><h3>Original preview</h3><div class="framepic original"><img class="mark-image" id="inv-orig" alt="Original archive image"></div></figure>'+
    '<figure class="panel"><h3>Extracted sand traces</h3><div class="framepic square"><img class="mark-image" id="inv-obs" alt="Observed skeleton on the registered plate"></div></figure>'+
    '<figure class="panel"><h3>Mode field and zero contour</h3><div class="framepic square"><canvas id="inv-mode" aria-label="Signed modeled field with its theoretical node lines"></canvas></div></figure>'+
    '<figure class="panel"><h3>Model contour on observed traces</h3><div class="framepic square"><img class="mark-image" id="inv-under" alt="Amber experimental skeleton"><canvas class="picture-overlay" id="inv-overlay" aria-label="Cyan theoretical zero contour"></canvas></div><p class="status">Amber · extracted traces. Cyan · model zero contour.</p></figure>'+
    '</div><div class="panel inverse-ranks"><h2>Competing families</h2><div id="ranks"></div></div></div></div>');
  const select=$(root,"#case"), form=$(root,"form"), status=$(form,".status"), trigger=$(form,"button");
  select.value=list.some(q=>q.id===params.get("id"))?params.get("id"):"IMG_1583";
  if(!select.value)select.selectedIndex=0;
  let data=null, selected=0, serial=0;
  function draw(){
    const v=data?.felder[selected];if(!v)return;
    field($(root,"#inv-mode"),v.werte,v.n);
    field($(root,"#inv-overlay"),v.werte,v.n,"overlay");
  }
  function rank(){
    const r=data.ergebnis, rows=r.rang, top=rows[0], lim=data.schwellen;
    const gap=r.test_abstand_zum_naechsten_rel??r.luecke_rel;
    $(root,"#decision").innerHTML=alert(rankText(r.status)+" · "+(data.quelle==="neue_extraktion"?"new extraction":"archived V2 extraction"),r.status!=="KANDIDAT_IM_BEOBACHTUNGSMODELL")+
      '<div class="metric">'+metric("Best family check / side",pct(top?.test_rel))+
      metric("Check limit",pct(lim.max_test_rel))+metric("Gap to next family",pct(gap))+metric("Required gap",pct(lim.min_abstand_rel))+'</div>'+
      (top?'<p class="status">'+esc(top.test_rel>lim.max_test_rel?"The leading fit-ranked family exceeds the check-distance limit.":gap<lim.min_abstand_rel?"The leading family does not clear the check-distance gap.":"The rule identifies a model-conditional candidate.")+'</p>':"");
    $(root,"#ranks").innerHTML='<div class="scroll"><table><thead><tr><th>Rank</th><th>Model</th><th>Family / actual modes</th><th>Fit [% side]</th><th>Check [% side]</th><th>Frequency span [Hz]</th></tr></thead><tbody>'+
      rows.map((v,i)=>'<tr'+(selected===i?' class="selected"':'')+'><td><button data-rank="'+i+'" aria-pressed="'+(selected===i)+'">'+(i+1)+'</button></td><td>'+esc(name(v.modell))+'</td><td>'+esc(v.familie.join(" + ")+" / "+v.moden.join(" + "))+'</td><td>'+pct(v.fit_rel)+'</td><td>'+pct(v.test_rel)+'</td><td>'+v.frequenzspanne_hz.map(x=>fmt(x,0)).join("–")+'</td></tr>').join("")+
      '</tbody></table></div>'+jsonDetails("Selected candidate diagnostics",rows[selected]??{});
    draw();
  }
  async function show(recompute=false){
    const token=++serial, q=list.find(x=>x.id===select.value);
    if(!q)return;
    const path="/api/inverse/"+encodeURIComponent(q.id);
    trigger.disabled=true;
    if(!recompute){
      data=null;$(root,"#inverse-figures").hidden=true;$(root,"#decision").innerHTML="";$(root,"#ranks").innerHTML="";
    }
    say(status,recompute?"Extracting lines and evaluating the catalogue…":"Loading archived reconstruction…");
    try{
      const d=await request(path,recompute?{body:{schwelle:form.elements.schwelle.value}}:{});
      if(!root.isConnected||token!==serial)return;
      data=d;selected=0;
      $(root,"#inv-orig").src=photo(q,"original");
      const extracted=d.sandlinien_png??photo(q,"linien");
      $(root,"#inv-obs").src=extracted;$(root,"#inv-under").src=extracted;
      $(root,"#inverse-figures").hidden=false;
      rank();say(status,recompute?"Recomputed on the verified source image.":"Archive result loaded.");
    }catch(e){if(token===serial)say(status,e.message);}
    finally{if(token===serial)trigger.disabled=false;}
  }
  $(root,"#ranks").onclick=event=>{if(event.target.dataset.rank!=null){selected=Number(event.target.dataset.rank);rank();}};
  select.onchange=()=>show();form.onsubmit=event=>{event.preventDefault();show(true);};
  const ro=new ResizeObserver(draw);ro.observe($(root,"#inv-mode"));show();
  return ()=>ro.disconnect();
}
async function gap(root){
  root.innerHTML=title("ABLATION STUDY","The model–experiment gap","Compare family ranks on known synthetic fields, then examine what changes when the same rule is applied to experimental traces.");
  const [g,a]=await Promise.all([get("gap"),get("atlas")]);
  if(!root.isConnected)return;
  const control=g.ablationsstudien.find(s=>s.name==="alle");
  const publicNames={H1:"Boundary condition",H2:"Contact and material",H3:"Sand observation",H4:"Image processing",H5:"Mode mixing",H6:"Metric and catalogue"};
  root.insertAdjacentHTML("beforeend",'<section class="evidence"><div><strong>'+fmt(g.katalog.hypothesen,0)+'</strong><span>model hypotheses</span></div><div><strong>'+g.katalog.klassen+'</strong><span>distinct model-family labels</span></div><div><strong>'+control.treffer+' / '+control.n+'</strong><span>control photos clearing the frozen rule</span></div></section>'+
    '<div class="panel section-start"><div class="kicker"><h2>3,720–3,726 Hz control</h2><span class="tag ochre">EXPERIMENTAL CHECK</span></div><p>Every model ablation used the same check-distance and separation limits. F1 has its own scale and no calibrated acceptance rule.</p>'+
    '<div class="workspace-tools"><label class="field">Catalogue or metric<select id="abl">'+g.ablationsstudien.map(s=>opt(s.name,name(s.name))).join("")+'</select></label></div><div id="ablation-results"></div>'+exportsFor("gap")+'</div>'+
    '<div class="grid2 section-start"><section class="panel"><div class="kicker"><h2>Synthetic benchmarks</h2><span class="tag violet">KNOWN LABELS</span></div>'+
    '<label class="field">Observation stress<select id="stress">'+["ideal","breit_diffus","unterbrochen","registrierung"].map(v=>opt(v,name(v))).join("")+'</select></label>'+
    '<div id="synth-results"></div><p class="status">Chance expectation samples distinct families uniformly. The same underlying fields recur across stress settings.</p>'+exportsFor("synthetik")+'</section>'+
    '<section class="panel"><h2>Image-processing sensitivity</h2><label class="field">Exposure<select id="gap-case">'+samples(a.bilder.filter(q=>g.bildvarianten[q.id])).map(q=>opt(q.id,label(q))).join("")+'</select></label>'+
    '<div id="gap-stress"></div></section></div>'+
    '<div class="panel section-start"><h2>Geometric identifiability</h2><p>'+g.identifizierbarkeit.familienuebergreifende_masken+
    ' of '+g.identifizierbarkeit.verschiedene_masken+' distinct raster masks are shared by multiple model families. A static zero set is invariant to any nonzero global scale, including a sign flip. An exposure supplies no time phase.</p>'+
    jsonDetails("Examples of families with identical raster masks",g.identifizierbarkeit.beispiele)+'</div>'+
    '<div class="panel"><h2>Hypotheses under test</h2>'+
    table(["Hypothesis","What the comparison establishes"],Object.entries(publicNames).map(([k,v],i)=>[k+" · "+v,[
      "The tested support models do not clear the frozen criterion in this control set.",
      "Degree, stiffness and radius perturbations probe selected ranges. Uniform Young’s modulus scales free-plate frequencies without changing eigenspaces.",
      "Diffuse and broken synthetic traces alter decisions. Grain transport in the GP2 apparatus remains unmeasured.",
      "Stress cases quantify extraction dependence on each archived frame; they share the same original exposure.",
      "Pair hypotheses help recover synthetic pair labels but leave the real control abstention unchanged.",
      "Tolerant F1 is an alternative ranking. Exact raster collisions constrain all rules using that representation."][i]]))+'</div>');
  const abl=$(root,"#abl"), stress=$(root,"#stress"), specimen=$(root,"#gap-case");
  abl.value="alle";specimen.value="IMG_1583";
  function renderAbl(){
    const s=g.ablationsstudien.find(m=>m.name===abl.value), f1=s.name==="tolerantes_f1";
    $(root,"#ablation-results").innerHTML='<div class="metric">'+metric(f1?"Median 1−F1":"Median check / side",f1?fmt(s.median_prueffehler_rel,3):pct(s.median_prueffehler_rel))+
      metric("Rule passes",s.treffer==null?"No rule":s.treffer+" / "+s.n)+metric("Evaluable",s.bewertbar+" / "+s.n)+'</div>'+
      table(["Exposure","Leading family",f1?"Check 1−F1":"Check distance / side","Outcome"],s.faelle.map(x=>[x.id,x.familie?name(x.familie[0])+" · "+x.familie[1].join(" + "):"—",
        f1?fmt(x.prueffehler_rel,3):pct(x.prueffehler_rel),f1?"Descriptive only":rankText(x.status)]));
  }
  function renderSynthetic(){
    const rows=g.synthetisch.summen.filter(s=>s.verfahren==="v2_distanz"&&s.stoerung===stress.value);
    $(root,"#synth-results").innerHTML=table(["Known label","Top 1","Top 6","Chance Top 6","Accepted","False accepts"],
      rows.map(x=>[name(x.art),x.art==="null"?"—":x.top1+"/"+x.n,x.art==="null"?"—":x.top6+"/"+x.n,
        x.art==="null"?"—":fmt(x.zufall_top6_erwartet),x.akzeptiert+"/"+x.n,x.falschakzeptiert]));
  }
  function renderStress(){
    const cases=Object.entries(g.bildvarianten[specimen.value]), base=cases[0][1], n=cases.filter(([,x])=>JSON.stringify(x.familie)!==JSON.stringify(base.familie)).length;
    $(root,"#gap-stress").innerHTML='<p class="status">'+n+' of '+cases.length+' extraction settings changed the leading family relative to baseline.</p>'+
      '<div class="contained-scroll">'+table(["Setting","Check / side","Leading family"],cases.map(([k,x])=>[k.replaceAll("_"," "),pct(x.prueffehler_rel),
        x.familie?name(x.familie[0])+" · "+x.familie[1].join(" + "):"—"]))+'</div>'+
      '<a class="button subtle" href="#inverse?id='+encodeURIComponent(specimen.value)+'">Open this exposure in inversion</a>';
  }
  abl.onchange=renderAbl;stress.onchange=renderSynthetic;specimen.onchange=renderStress;
  renderAbl();renderSynthetic();renderStress();
}

async function validation(root){
  root.innerHTML=title("REPRODUCIBILITY","Research validation","Benchmarks, image sensitivities and exportable figures from the local research run.");
  const keys=["audit","studie","gap","mechanik","lauf"], results=await Promise.allSettled(keys.map(get));
  if(!root.isConnected)return;
  const [audit,study,g,m,l]=results.map(r=>r.value);
  const v=audit?.eingangspruefung, art=audit?.artefakte;
  const figureNames={sweeps:"Experimental sweeps",gap:"Control reconstructions",mechanik:"Plate-model convergence",synthetik:"Synthetic family benchmarks"};
  const statusRows=[
    ["V2 archive and rerun",art?art.filter(x=>x.bytegleich&&x.archiv_ok).length+" / "+art.length+" byte-identical":"Missing local audit"],
    ["Raw source checksums",l?l.rohdaten_nachher.dateien+" sources verified":v?v.quellen+" sources verified before V3":"Pending"],
    ["V3-G1 · image robustness",study?study.fotos.length+" photos with controlled image settings":"Pending"],
    ["Independent human reference",study?.annotation.status_unabhaengige_menschliche_referenz??"Pending"],
    ["V3-G2 · model gap",g?"Negative control result quantified":"Pending"]];
  root.insertAdjacentHTML("beforeend",'<div class="panel"><h2>Evidence and quality gates</h2>'+table(["Component","Recorded outcome"],statusRows)+'</div>'+
    '<div class="panel"><div class="kicker"><h2>Solver checks</h2><span class="tag violet">NUMERICAL</span></div>'+
    (m?'<div class="metric">'+metric("Free-plate literature benchmark",m.benchmark.bestanden?"Passed":"Failed")+
      metric("Navier max relative error",v?.navier_rel_eig_max?.toExponential(3)??"—")+'</div>'+
      '<label class="field">Model<select id="validation-model">'+Object.keys(m.modelle).map(k=>opt(k,name(k))).join("")+'</select></label><div id="validation-data"></div>':alert("Local mechanics data missing.",true))+
    '</div><div class="grid2 section-start">'+Object.entries(figureNames).map(([k,v])=>'<figure class="panel"><h2>'+v+'</h2>'+
      (l?.artefakte?.["figuren/"+k+".png"]?'<div class="mainFigure figure-space"><img loading="lazy" src="/figur/'+k+'.png" alt="'+v+'"></div>'+exportsFor(k):alert("Run the V3 figure export to enable downloads.",true))+'</figure>').join("")+'</div>'+
    '<div class="panel section-start"><h2>Reproduce this run</h2><pre>python -m chladni.checks --scope all\npython -m chladni.forschung_v3 alle\n.\\start-v3.ps1</pre>'+
    (l?jsonDetails("Run manifest and SHA-256 provenance",l):alert("The V3 run manifest is unavailable.",true))+'</div>');
  if(m){
    const select=$(root,"#validation-model");
    select.onchange=()=>{
      const z=m.modelle[select.value];
      $(root,"#validation-data").innerHTML=table(["Ritz degree","First eigenfrequency [Hz]","Max relative residual","Mass orthogonality error"],z.stufen.map(x=>[x.grad,fmt(x.hz[0]),x.rel_residuum_max.toExponential(2),x.m_orthogon_abs_max.toExponential(2)]))+
        jsonDetails("Near-degenerate subspace convergence",z.unterraeume);
    };
    select.value="anschluss";select.onchange();
  }
}

let dispose, epoch=0;
const routes={atlas,modes,inverse,gap,validation,annotation:(root)=>annotationView(root,{get,request,esc,opt,fmt,pct,title,alert,metric,photo,label,jsonDetails})};
async function navigate(){
  const [name,query]=location.hash.slice(1).split("?",2);
  if(name==="app") {app.focus();return;}
  const v=++epoch;dispose?.();dispose=null;
  document.querySelectorAll("nav a").forEach(a=>{if(a.hash==="#"+name)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
  if(!Object.hasOwn(routes,name)){
    app.innerHTML=home;start(app);window.scrollTo(0,0);return;
  }
  const root=document.createElement("section");root.className="view";
  app.replaceChildren(root);window.scrollTo(0,0);
  try{
    const cleanup=await routes[name](root,new URLSearchParams(query));
    if(v!==epoch)cleanup?.();else dispose=cleanup;
  }catch(e){if(v===epoch)root.insertAdjacentHTML("beforeend",alert(e.message,true));}
}
window.addEventListener("hashchange",navigate);
navigate();
