import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{label}</p>
        {payload.map((entry, index) => (
          <div key={`item-${index}`} className="tooltip-item">
            <div style={{ width: 12, height: 12, borderRadius: 2, backgroundColor: entry.color }} />
            <span>{entry.name}: </span>
            <span className="tooltip-value">
              {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(entry.value)}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export default function PipelineChart({ data, delayClass }) {
  const getVar = (name, fallback) => {
    if (typeof window !== 'undefined') {
      const val = getComputedStyle(document.documentElement).getPropertyValue(name);
      if (val) return val.trim();
    }
    return fallback;
  };

  const cWip = getVar('--accent-primary', '#3b82f6');
  const cBilled = getVar('--accent-secondary', '#8b5cf6');
  const cAR = getVar('--warning', '#f59e0b');
  const cIncome = getVar('--success', '#10b981');
  const text = getVar('--text-secondary', '#64748b');
  const grid = getVar('--chart-grid', '#e2e8f0');

  return (
    <div className={`chart-card animated ${delayClass}`}>
      <div className="chart-header">
        <h2 className="chart-title">Revenue Pipeline (WIP &rarr; Income)</h2>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <defs>
              <linearGradient id="colorWip" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={cWip} stopOpacity={0.8}/>
                <stop offset="95%" stopColor={cWip} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorBilled" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={cBilled} stopOpacity={0.8}/>
                <stop offset="95%" stopColor={cBilled} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorAR" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={cAR} stopOpacity={0.8}/>
                <stop offset="95%" stopColor={cAR} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={cIncome} stopOpacity={0.8}/>
                <stop offset="95%" stopColor={cIncome} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
            <XAxis dataKey="name" stroke={text} tick={{ fill: text }} tickLine={false} axisLine={false} />
            <YAxis 
              stroke={text} 
              tick={{ fill: text }} 
              tickLine={false} 
              axisLine={false}
              tickFormatter={(value) => `$${value / 1000}k`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />
            
            <Area type="monotone" dataKey="wip" name="WIP" stroke={cWip} fillOpacity={1} fill="url(#colorWip)" />
            <Area type="monotone" dataKey="billed" name="Billed" stroke={cBilled} fillOpacity={1} fill="url(#colorBilled)" />
            <Area type="monotone" dataKey="ar" name="A/R" stroke={cAR} fillOpacity={1} fill="url(#colorAR)" />
            <Area type="monotone" dataKey="income" name="Actual Income" stroke={cIncome} fillOpacity={1} fill="url(#colorIncome)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
