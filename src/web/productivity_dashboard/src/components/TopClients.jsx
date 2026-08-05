import React from 'react';

const formatCurrency = (val) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val || 0);

const TopClients = ({ data, delayClass = '' }) => {
  if (!data || data.length === 0) return null;
  
  // Find max value to determine bar width percentages
  const maxValue = Math.max(...data.map(d => d.value));
  
  return (
    <div className={`metric-card animated ${delayClass}`} style={{ gridColumn: 'span 1', display: 'flex', flexDirection: 'column', padding: '24px' }}>
      <h3 style={{ fontSize: '13px', fontWeight: '600', color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '24px' }}>
        TOP CLIENTS
      </h3>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {data.map((client, idx) => {
          const pct = maxValue > 0 ? (client.value / maxValue) * 100 : 0;
          return (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', fontSize: '12px' }}>
              <div style={{ flex: '1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-secondary)' }}>
                {client.name.toUpperCase()}
              </div>
              <div style={{ width: '80px', textAlign: 'right', fontWeight: '600', color: 'var(--text-primary)', marginRight: '8px' }}>
                {formatCurrency(client.value)}
              </div>
              <div style={{ width: '100px', height: '14px', background: 'var(--bg-app)', borderRadius: '2px', overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent-primary)', transition: 'width 1s ease-out' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TopClients;
