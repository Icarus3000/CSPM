import React from 'react';

const formatCurrency = (val) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val || 0);

const AnnualForecast = ({ target, basisDays, totalFeesYTD, delayClass = '' }) => {
  const startOfYear = new Date(new Date().getFullYear(), 0, 1);
  const now = new Date();
  
  // Calculate elapsed days excluding weekends for a simple approximation, or just calendar days
  // Let's use calendar days elapsed in the year so far:
  const elapsedCalendarDays = Math.floor((now - startOfYear) / (1000 * 60 * 60 * 24)) + 1;
  
  // Current Pace (per day)
  const pace = elapsedCalendarDays > 0 ? (totalFeesYTD / elapsedCalendarDays) : 0;
  
  // Projected
  const projected = pace * basisDays;
  
  // Percentage vs Target
  const pctVsTarget = target > 0 ? ((projected - target) / target) * 100 : 0;
  
  const isPositive = pctVsTarget >= 0;
  
  return (
    <div className={`metric-card animated ${delayClass}`} style={{ gridColumn: 'span 1', display: 'flex', flexDirection: 'column', padding: '24px' }}>
      <h3 style={{ fontSize: '13px', fontWeight: '600', color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '24px' }}>
        ANNUAL FORECAST
      </h3>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '14px' }}>
        <span style={{ color: 'var(--text-secondary)' }}>Current Pace</span>
        <span style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{formatCurrency(pace)} / day</span>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '14px' }}>
        <span style={{ color: 'var(--text-secondary)' }}>Basis</span>
        <span style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{basisDays} Days</span>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px', fontSize: '14px' }}>
        <span style={{ color: 'var(--text-secondary)' }}>Target</span>
        <span style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{formatCurrency(target)}</span>
      </div>
      
      <div style={{ marginTop: 'auto' }}>
        <div style={{ fontSize: '32px', fontWeight: '300', color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: '4px' }}>
          {formatCurrency(projected)}
        </div>
        <div style={{ fontSize: '14px', fontWeight: '600', color: isPositive ? 'var(--success)' : 'var(--danger)' }}>
          {isPositive ? '+' : ''}{pctVsTarget.toFixed(1)}% vs Target
        </div>
      </div>
    </div>
  );
};

export default AnnualForecast;
