window.hydrateBriefing && window.hydrateBriefing({
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
