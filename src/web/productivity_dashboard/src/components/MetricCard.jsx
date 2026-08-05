import React from 'react';

export default function MetricCard({ title, value, icon: Icon, delayClass }) {
  const formattedValue = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

  return (
    <div className={`kpi-card animated ${delayClass}`}>
      <div className="kpi-header">
        <span className="kpi-title">{title}</span>
        {Icon && <Icon className="kpi-icon" size={20} />}
      </div>
      <div className="kpi-value">{formattedValue}</div>
    </div>
  );
}
