(function waitForHydrate(){
  function doHydrate(){
    if (typeof window.hydrateBriefing === 'function'){
      window.hydrateBriefing({
        ok: true,
        asOfDate: "2026-08-16",
        todaysTasks: [
          { title: "Call Client A", client: "Client A" },
          { title: "Review invoice INV-123", client: "Client B" }
        ],
        upcomingDeadlines: [
          { title: "File document", date: "2026-08-20", client: "Client B" }
        ],
        overdueDeadlines: [
          { title: "Respond to notice", date: "2026-08-01", client: "Client C" }
        ],
        overdueBills: [
          { invoice: "INV-123", client: "Client D", wipAmount: 1200.5, daysOld: 10 }
        ],
        readyToBillMatters: [
          { matterName: "Matter X", clientName: "Client E", entryCount: 3, wipAmount: 450.0 }
        ]
      });
      return true;
    }
    return false;
  }

  if (!doHydrate()){
    // Retry for up to ~10s
    var tries = 0;
    var maxTries = 50; // 50 * 200ms = 10s
    var id = setInterval(function(){
      tries++;
      if (doHydrate() || tries >= maxTries){
        clearInterval(id);
      }
    }, 200);
  }
})();

// Deployment retrigger + auto-hydrate wrapper: 2026-08-16T20:05:00Z
