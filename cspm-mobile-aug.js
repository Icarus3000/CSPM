/* Mobile UI augmentation for practice briefing (local mock dockets)
   - Adds bottom control bar with filters and Add Docket
   - Adds modal for viewing/editing cards
   - Stores local dockets in localStorage under 'cspm_local_dockets'
   - Merges with window.hydrated sample data when available
*/
(function(){
  var CSS = `
  #cspm-bar{position:fixed;right:8px;left:8px;bottom:12px;display:flex;gap:6px;justify-content:space-between;z-index:2147483647}
  #cspm-bar .btn{flex:1;padding:8px 10px;border-radius:8px;background:#0b63ff;color:#fff;font-weight:600;text-align:center;font-size:14px}
  #cspm-modal{position:fixed;left:8px;right:8px;top:12px;bottom:72px;background:#fff;border-radius:10px;padding:12px;box-shadow:0 6px 24px rgba(0,0,0,.2);overflow:auto;z-index:2147483648;display:none}
  #cspm-overlay{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:2147483647;display:none}
  #cspm-form input,#cspm-form textarea{width:100%;padding:8px;margin:6px 0;border:1px solid #ddd;border-radius:6px}
  #cspm-form .row{display:flex;gap:6px}
  .cspm-card{cursor:pointer}
  `;
  var style = document.createElement('style'); style.appendChild(document.createTextNode(CSS));
  document.head.appendChild(style);

  function uid(){return 'id'+Math.random().toString(36).slice(2,9)}
  function nowISO(){return new Date().toISOString().slice(0,10)}

  function getLocal(){try{return JSON.parse(localStorage.getItem('cspm_local_dockets')||'[]')}catch(e){return []}}
  function setLocal(v){localStorage.setItem('cspm_local_dockets',JSON.stringify(v))}

  function mergeData(sample){
    var local=getLocal();
    // Flatten sample into items with category mapping
    var items=[];
    (sample.todaysTasks||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'today',title:i.title,client:i.client},i)));
    (sample.upcomingDeadlines||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'upcoming',title:i.title,date:i.date,client:i.client},i)));
    (sample.overdueDeadlines||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'overdue',title:i.title,date:i.date,client:i.client},i)));
    (sample.overdueBills||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'bill',title:i.invoice,client:i.client,wipAmount:i.wipAmount},i)));
    (sample.readyToBillMatters||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'readyToBill',title:i.matterName,client:i.clientName,entryCount:i.entryCount,wipAmount:i.wipAmount},i)));
    // local items already have category
    local.forEach(i=>items.push(Object.assign({_source:'local'},i)));
    return items;
  }

  function renderCards(items){
    // find container where app renders lists. Try common selectors
    var root = document.getElementById('root') || document.body;
    // Simple approach: append a test container at top of root
    var test = document.getElementById('cspm-test-container');
    if (!test){ test = document.createElement('div'); test.id='cspm-test-container'; test.style.padding='12px'; root.insertBefore(test,root.firstChild); }
    test.innerHTML='';

    var groups = {today:[],upcoming:[],overdue:[],bill:[],readyToBill:[]};
    items.forEach(it=>{ var k=it.category||it.status||'today'; if (!groups[k]) groups[k]=[]; groups[k].push(it); });

    function makeList(title,key){
      var h=document.createElement('h3'); h.textContent=title; test.appendChild(h);
      var wrap=document.createElement('div'); wrap.style.display='grid'; wrap.style.gridTemplateColumns='1fr 1fr'; wrap.style.gap='8px';
      groups[key].forEach(it=>{
        var c=document.createElement('div'); c.className='cspm-card'; c.style.padding='10px'; c.style.border='1px solid #eee'; c.style.borderRadius='8px'; c.style.background='#fff';
        var t=document.createElement('div'); t.textContent=it.title||it.invoice||'Item'; t.style.fontWeight=700; c.appendChild(t);
        var s=document.createElement('div'); s.textContent=it.client?('Client: '+it.client): (it.date?('Date: '+it.date):''); s.style.color='#555'; s.style.fontSize='13px'; c.appendChild(s);
        c.onclick=function(){ openModal(it); };
        wrap.appendChild(c);
      });
      test.appendChild(wrap);
    }

    makeList('Today','today');
    makeList('Upcoming','upcoming');
    makeList('Overdue','overdue');
    makeList('Bills','bill');
    makeList('Ready to Bill','readyToBill');
  }

  function openModal(item){
    overlay.style.display='block'; modal.style.display='block';
    modal.innerHTML='';
    var h=document.createElement('h2'); h.textContent=item.title||'Details'; modal.appendChild(h);
    var p=document.createElement('p'); p.textContent='Client: '+(item.client||'N/A'); modal.appendChild(p);
    if (item.date){ var pd=document.createElement('p'); pd.textContent='Date: '+item.date; modal.appendChild(pd);}    
    if (item.wipAmount){ var w=document.createElement('p'); w.textContent='WIP: $'+item.wipAmount; modal.appendChild(w);}    
    var note=document.createElement('div'); note.textContent=item.notes||''; modal.appendChild(note);
    var btnRow=document.createElement('div'); btnRow.style.display='flex'; btnRow.style.gap='8px'; btnRow.style.marginTop='12px';
    var openBtn=document.createElement('button'); openBtn.textContent='Open link'; openBtn.className='btn'; openBtn.onclick=function(){ if (item.link) window.open(item.link,'_blank'); else alert('No link for this item'); };
    var del=document.createElement('button'); del.textContent='Delete'; del.className='btn'; del.style.background='#c0392b'; del.onclick=function(){ if (confirm('Delete?')){ deleteLocal(item.id); overlay.style.display='none'; modal.style.display='none'; } };
    btnRow.appendChild(openBtn); btnRow.appendChild(del);
    modal.appendChild(btnRow);
  }

  function deleteLocal(id){ var a=getLocal().filter(x=>x.id!==id); setLocal(a); triggerRender(); }

  function createForm(){
    var f=document.createElement('form'); f.id='cspm-form';
    f.innerHTML = `\n      <label>Title<input name='title' required></label>\n      <label>Client<input name='client'></label>\n      <label>Date<input type='date' name='date' value='${nowISO()}'></label>\n      <label>Notes<textarea name='notes'></textarea></label>\n      <label>Billable hours<input type='number' step='0.1' name='billableHours'></label>\n      <label>Link<input name='link' placeholder='https://...'></label>\n      <label>Category<select name='category'><option value='today'>Today</option><option value='upcoming'>Upcoming</option><option value='overdue'>Overdue</option><option value='bill'>Bill</option><option value='readyToBill'>Ready to Bill</option></select></label>\n      <div style='display:flex;gap:8px'><button class='btn' type='submit'>Save</button><button id='cspm-cancel' class='btn' type='button' style='background:#666'>Cancel</button></div>\n    `;
    f.onsubmit=function(ev){ ev.preventDefault(); var fd=new FormData(f); var obj={id:uid(),title:fd.get('title'),client:fd.get('client'),date:fd.get('date'),notes:fd.get('notes'),billableHours:parseFloat(fd.get('billableHours')||0),link:fd.get('link'),category:fd.get('category')}; var a=getLocal(); a.unshift(obj); setLocal(a); overlay.style.display='none'; modal.style.display='none'; triggerRender(); };
    return f;
  }

  function triggerRender(){ if (window.__cspm_last_sample) renderCards(mergeData(window.__cspm_last_sample)); else renderCards(getLocal()); }

  // UI elements
  var bar=document.createElement('div'); bar.id='cspm-bar';
  ['Today','Upcoming','Overdue','Bills','Ready','Add Docket'].forEach(label=>{ var b=document.createElement('div'); b.className='btn'; b.textContent=label; bar.appendChild(b); });
  document.body.appendChild(bar);
  var overlay=document.createElement('div'); overlay.id='cspm-overlay'; document.body.appendChild(overlay);
  var modal=document.createElement('div'); modal.id='cspm-modal'; document.body.appendChild(modal);

  // wire buttons
  var buttons=bar.querySelectorAll('.btn');
  var filter=null;
  buttons[0].onclick=function(){ filter='today'; doFilter(); };
  buttons[1].onclick=function(){ filter='upcoming'; doFilter(); };
  buttons[2].onclick=function(){ filter='overdue'; doFilter(); };
  buttons[3].onclick=function(){ filter='bill'; doFilter(); };
  buttons[4].onclick=function(){ filter='readyToBill'; doFilter(); };
  buttons[5].onclick=function(){ overlay.style.display='block'; modal.style.display='block'; modal.innerHTML=''; modal.appendChild(createForm()); document.getElementById('cspm-cancel').onclick=function(){ overlay.style.display='none'; modal.style.display='none'; }; };
  overlay.onclick=function(){ overlay.style.display='none'; modal.style.display='none'; };

  function doFilter(){ var items=window.__cspm_last_items||[]; if (!filter){ triggerRender(); return } var fitems=items.filter(i=>i.category===filter); renderCards(fitems); }

  // Hook into sample hydration: wait for window.hydrateBriefing calls as earlier script
  function onSample(sample){ window.__cspm_last_sample=sample; window.__cspm_last_items=mergeData(sample); triggerRender(); }

  // If the sample script already called earlier, try to pick it up
  if (typeof window.hydrateBriefing === 'function' && window.__cspm_last_sample===undefined){
    // hijack: call a small wrapper to capture data
    var orig = window.hydrateBriefing;
    window.hydrateBriefing = function(data){ try{ onSample(data); }catch(e){}; try{ orig(data);}catch(e){} };
  }

  // Poll for hydrate function and wrap it
  var tries=0; var poll=setInterval(function(){ tries++; if (typeof window.hydrateBriefing==='function'){ // wrap once
      var orig=window.hydrateBriefing; window.hydrateBriefing=function(data){ try{ onSample(data); }catch(e){}; try{ orig(data);}catch(e){} };
      clearInterval(poll); }
    if (tries>50){ clearInterval(poll); // fallback: render local only
      triggerRender(); }
  },200);

})();

// Deployment: add mobile mock UI: 2026-08-16T20:12:00Z
