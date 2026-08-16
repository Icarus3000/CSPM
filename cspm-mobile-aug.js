/* Mobile UI augmentation for practice briefing (local mock dockets)
   - Adds bottom control bar with filters and Add Docket
   - Cards open detail pages on gh-pages (detail.html?id=)
   - Add Docket opens docket.html
   - Stores local dockets in localStorage under 'cspm_local_dockets'
   - Merges with window.hydrateBriefing sample data when available
*/
(function(){
  var CSS = `
  #cspm-bar{position:fixed;right:8px;left:8px;bottom:12px;display:flex;gap:6px;justify-content:space-between;z-index:2147483647}
  #cspm-bar .btn{flex:1;padding:8px 10px;border-radius:8px;background:#0b63ff;color:#fff;font-weight:600;text-align:center;font-size:14px}
  #cspm-test-container{padding:12px;background:#f7f9fc}
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
    var items=[];
    if(sample){
      (sample.todaysTasks||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'today',title:i.title,client:i.client},i)));
      (sample.upcomingDeadlines||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'upcoming',title:i.title,date:i.date,client:i.client},i)));
      (sample.overdueDeadlines||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'overdue',title:i.title,date:i.date,client:i.client},i)));
      (sample.overdueBills||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'bill',title:i.invoice,client:i.client,wipAmount:i.wipAmount},i)));
      (sample.readyToBillMatters||[]).forEach(i=>items.push(Object.assign({id: 's-'+uid(),_source:'sample',category:'readyToBill',title:i.matterName,client:i.clientName,entryCount:i.entryCount,wipAmount:i.wipAmount},i)));
    }
    local.forEach(i=>items.push(Object.assign({_source:'local'},i)));
    return items;
  }

  function renderCards(items){
    var root = document.getElementById('root') || document.body;
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
        c.onclick=function(){
          // open detail page on gh-pages with item id
          var id = encodeURIComponent(it.id);
          window.open('./detail.html?id='+id, '_blank');
        };
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

  // UI elements
  var bar=document.createElement('div'); bar.id='cspm-bar';
  ['Today','Upcoming','Overdue','Bills','Ready','Add Docket'].forEach(label=>{ var b=document.createElement('div'); b.className='btn'; b.textContent=label; bar.appendChild(b); });
  document.body.appendChild(bar);

  var buttons=bar.querySelectorAll('.btn');
  var filter=null;
  buttons[0].onclick=function(){ filter='today'; doFilter(); };
  buttons[1].onclick=function(){ filter='upcoming'; doFilter(); };
  buttons[2].onclick=function(){ filter='overdue'; doFilter(); };
  buttons[3].onclick=function(){ filter='bill'; doFilter(); };
  buttons[4].onclick=function(){ filter='readyToBill'; doFilter(); };
  buttons[5].onclick=function(){ window.open('./docket.html', '_blank'); };

  function doFilter(){ var items=window.__cspm_last_items||[]; if (!filter){ renderCards(items); return } var fitems=items.filter(i=>i.category===filter); renderCards(fitems); }

  function triggerRender(){ if (window.__cspm_last_sample) renderCards(mergeData(window.__cspm_last_sample)); else renderCards(mergeData(null)); }

  // Hook into sample hydration: capture sample passed to window.hydrateBriefing
  function onSample(sample){ window.__cspm_last_sample=sample; window.__cspm_last_items=mergeData(sample); triggerRender(); }

  // If hydrateBriefing already exists, wrap it
  if (typeof window.hydrateBriefing === 'function'){
    var orig = window.hydrateBriefing;
    window.hydrateBriefing = function(data){ try{ onSample(data); }catch(e){}; try{ orig(data);}catch(e){} };
  }

  // Poll for hydrate function and wrap it
  var tries=0; var poll=setInterval(function(){ tries++; if (typeof window.hydrateBriefing==='function'){ var orig=window.hydrateBriefing; window.hydrateBriefing=function(data){ try{ onSample(data); }catch(e){}; try{ orig(data);}catch(e){} }; clearInterval(poll); }
    if (tries>50){ clearInterval(poll); triggerRender(); }
  },200);

})();
