// Mock Data for Productivity Dashboard

export const productionData = [
  { name: 'Jan', fees: 45000, target: 50000, projected: 45000 },
  { name: 'Feb', fees: 52000, target: 50000, projected: 52000 },
  { name: 'Mar', fees: 48000, target: 50000, projected: 48000 },
  { name: 'Apr', fees: 61000, target: 50000, projected: 61000 },
  { name: 'May', fees: 59000, target: 50000, projected: 59000 },
  { name: 'Jun', fees: 42000, target: 50000, projected: 42000 }, // Current month partial
  { name: 'Jul', fees: 0, target: 50000, projected: 55000 }, // Future extrapolation
  { name: 'Aug', fees: 0, target: 50000, projected: 51000 },
  { name: 'Sep', fees: 0, target: 50000, projected: 58000 },
];

export const pipelineData = [
  { name: 'Week 1', wip: 12000, billed: 15000, ar: 25000, income: 10000 },
  { name: 'Week 2', wip: 18000, billed: 12000, ar: 30000, income: 15000 },
  { name: 'Week 3', wip: 15000, billed: 22000, ar: 28000, income: 18000 },
  { name: 'Week 4', wip: 21000, billed: 19000, ar: 22000, income: 25000 },
  { name: 'Week 5', wip: 24000, billed: 11000, ar: 26000, income: 14000 },
];

export const topClientsData = [
  { name: 'Wild Bunch Beverages', value: 35000 },
  { name: 'Leviathan Private Network', value: 28000 },
  { name: 'African Bronze', value: 15000 },
  { name: 'Spider Silk', value: 12000 },
  { name: 'Other', value: 9000 },
];

export const kpiSummary = {
  totalFeesYTD: 307000,
  feesTrend: 12.5,
  totalWIP: 24000,
  wipTrend: -5.2,
  totalAR: 75481.01,
  arTrend: 2.1,
  totalIncomeYTD: 285000,
  incomeTrend: 15.4
};
