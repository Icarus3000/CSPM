import React from 'react';
import {
  ComposedChart,
  Line,
  Bar,
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

export default function ProductionChart({ data, delayClass }) {
  // Use CSS variables for chart colors, fallback to defaults if not computed yet
  const getVar = (name, fallback) => {
    if (typeof window !== 'undefined') {
      const val = getComputedStyle(document.documentElement).getPropertyValue(name);
      if (val) return val.trim();
    }
    return fallback;
  };

  const primary = getVar('--accent-primary', '#3b82f6');
  const secondary = getVar('--accent-secondary', '#8b5cf6');
  const text = getVar('--text-secondary', '#64748b');
  const grid = getVar('--chart-grid', '#e2e8f0');

  return (
    <div className={`chart-card animated ${delayClass}`}>
      <div className="chart-header">
        <h2 className="chart-title">Production & Extrapolation</h2>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
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
            
            <Bar dataKey="fees" name="Actual Fees" fill={primary} radius={[4, 4, 0, 0]} maxBarSize={50} />
            <Line type="monotone" dataKey="target" name="Target" stroke="#ef4444" strokeWidth={2} dot={false} strokeDasharray="5 5" />
            <Line type="monotone" dataKey="projected" name="Projected/Extrapolated" stroke={secondary} strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
