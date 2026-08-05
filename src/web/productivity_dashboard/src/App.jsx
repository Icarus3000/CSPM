import React, { useState, useEffect, useMemo } from 'react';
import { Sun, Moon, DollarSign, Clock, FileText, CheckCircle, AlertTriangle, Settings } from 'lucide-react';
import MetricCard from './components/MetricCard';
import ProductionChart from './components/ProductionChart';
import PipelineChart from './components/PipelineChart';
import AnnualForecast from './components/AnnualForecast';
import TopClients from './components/TopClients';

function getDateRange(periodKey) {
  const now = new Date();
  const year = now.getFullYear();

  // Helper: find last Sunday
  const lastSunday = (d) => {
    const result = new Date(d);
    result.setDate(result.getDate() - result.getDay());
    result.setHours(0, 0, 0, 0);
    return result;
  };

  switch (periodKey) {
    case 'YTD':
      return [new Date(year, 0, 1), now];
    case 'Q1':
      return [new Date(year, 0, 1), new Date(year, 2, 31)];
    case 'Q2':
      return [new Date(year, 3, 1), new Date(year, 5, 30)];
    case 'Q3':
      return [new Date(year, 6, 1), new Date(year, 8, 30)];
    case 'Q4':
      return [new Date(year, 9, 1), new Date(year, 11, 31)];
    case 'ThisMonth': {
      return [new Date(year, now.getMonth(), 1), now];
    }
    case 'LastMonth': {
      const lm = new Date(year, now.getMonth() - 1, 1);
      const lmEnd = new Date(year, now.getMonth(), 0);
      return [lm, lmEnd];
    }
    case 'WTD': {
      return [lastSunday(now), now];
    }
    case 'LastWeek': {
      const sun = lastSunday(now);
      const prevSun = new Date(sun);
      prevSun.setDate(prevSun.getDate() - 7);
      const prevSat = new Date(prevSun);
      prevSat.setDate(prevSat.getDate() + 6);
      return [prevSun, prevSat];
    }
    case 'Rolling30':
      return [new Date(now.getTime() - 30 * 86400000), now];
    case 'Rolling90':
      return [new Date(now.getTime() - 90 * 86400000), now];
    case 'Rolling365':
      return [new Date(now.getTime() - 365 * 86400000), now];
    case 'AllTime':
      return [new Date(2000, 0, 1), now];
    default:
      return [new Date(year, 0, 1), now];
  }
}

function formatDateInput(d) {
  return d.toISOString().split('T')[0];
}

function App() {
  const [theme, setTheme] = useState('dark');
  const [timePeriod, setTimePeriod] = useState('YTD');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  // Live data state — null means "not yet received"
  const [liveData, setLiveData] = useState(null);
  const [hydrationError, setHydrationError] = useState(null);

  const [showSettings, setShowSettings] = useState(false);
  const [target, setTarget] = useState(() => Number(localStorage.getItem('cspm-forecast-target')) || 350000);
  const [workingDaysPerWeek, setWorkingDaysPerWeek] = useState(() => Number(localStorage.getItem('cspm-forecast-wdpw')) || 5);
  const [vacationDays, setVacationDays] = useState(() => Number(localStorage.getItem('cspm-forecast-vacation')) || 24);

  useEffect(() => {
    localStorage.setItem('cspm-forecast-target', target);
    localStorage.setItem('cspm-forecast-wdpw', workingDaysPerWeek);
    localStorage.setItem('cspm-forecast-vacation', vacationDays);
  }, [target, workingDaysPerWeek, vacationDays]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    window.hydrateDashboard = (payload) => {
      console.log("hydrateDashboard called", payload);
      if (!payload) {
        setHydrationError("hydrateDashboard was called with a null/undefined payload.");
        return;
      }
      if (!payload.ok) {
        setHydrationError(`Backend error: ${payload.message || "Unknown error from Python backend."}`);
        return;
      }
      setHydrationError(null);
      setLiveData(payload);
    };
    return () => { delete window.hydrateDashboard; };
  }, []);

  // Compute filtered KPIs from rawTime based on selected period
  const filteredKpis = useMemo(() => {
    if (!liveData || !liveData.rawTime) return null;

    let startDate, endDate;
    if (timePeriod === 'Custom') {
      if (!customStart || !customEnd) return null;
      startDate = new Date(customStart + 'T00:00:00');
      endDate = new Date(customEnd + 'T23:59:59');
    } else {
      [startDate, endDate] = getDateRange(timePeriod);
    }

    let totalFees = 0;
    let totalHours = 0;
    let wipTotal = 0;

    for (const entry of liveData.rawTime) {
      const d = new Date(entry.date + 'T00:00:00');
      if (d >= startDate && d <= endDate) {
        totalFees += entry.gross || 0;
        totalHours += entry.hours || 0;
        const status = (entry.status || '').toLowerCase();
        if (['unbilled', 'wip', '', 'draft', 'ready', 'ready for billing'].includes(status)) {
          wipTotal += entry.gross || 0;
        }
      }
    }

    const arTotal = liveData.kpiData?.arTotal || 0;

    // Calculate income from pipelineData
    const totalIncome = liveData.pipelineData
      ? liveData.pipelineData.reduce((acc, w) => acc + (w.income || 0), 0)
      : 0;

    return {
      totalFeesYTD: Math.round(totalFees * 100) / 100,
      totalWIP: Math.round(wipTotal * 100) / 100,
      totalAR: Math.round(arTotal * 100) / 100,
      totalIncomeYTD: Math.round(totalIncome * 100) / 100,
    };
  }, [liveData, timePeriod, customStart, customEnd]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  // Derive period label for metric cards
  const periodLabel = timePeriod === 'Custom'
    ? (customStart && customEnd ? `${customStart} – ${customEnd}` : 'Custom Range')
    : timePeriod;

  useEffect(() => {
    document.title = `Productivity_Report_${periodLabel.replace(/[^a-zA-Z0-9]/g, '_')}`;
  }, [periodLabel]);

  // --- ERROR STATE ---
  if (hydrationError) {
    return (
      <div className="dashboard-container">
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          borderRadius: '12px',
          padding: '24px',
          margin: '24px 0',
          color: '#EF4444',
          fontFamily: 'Inter, system-ui, sans-serif'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <AlertTriangle size={24} />
            <h2 style={{ margin: 0, fontSize: '18px' }}>Dashboard Data Error</h2>
          </div>
          <p style={{ fontSize: '14px', lineHeight: '1.6', color: 'var(--text-primary, #fff)', opacity: 0.85 }}>
            {hydrationError}
          </p>
          <p style={{ fontSize: '12px', marginTop: '12px', opacity: 0.6 }}>
            Check the Python logs at <code>logs/cspm.log</code> for details.
          </p>
        </div>
      </div>
    );
  }

  // --- LOADING STATE ---
  if (!liveData) {
    return (
      <div className="dashboard-container">
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '300px',
          color: 'var(--text-muted)',
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: '14px'
        }}>
          Waiting for data from backend…
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <header className="header animated delay-1">
        <h1>Productivity &amp; Performance</h1>
        <div className="header-controls">
          <select
            className="filter-select"
            value={timePeriod}
            onChange={(e) => setTimePeriod(e.target.value)}
          >
            <optgroup label="Year">
              <option value="YTD">Year to Date</option>
              <option value="Q1">Q1 (Jan – Mar)</option>
              <option value="Q2">Q2 (Apr – Jun)</option>
              <option value="Q3">Q3 (Jul – Sep)</option>
              <option value="Q4">Q4 (Oct – Dec)</option>
            </optgroup>
            <optgroup label="Month">
              <option value="ThisMonth">This Month</option>
              <option value="LastMonth">Last Month</option>
            </optgroup>
            <optgroup label="Week">
              <option value="WTD">Week to Date (from Sunday)</option>
              <option value="LastWeek">Last Week (Sun – Sat)</option>
            </optgroup>
            <optgroup label="Rolling">
              <option value="Rolling30">Last 30 Days</option>
              <option value="Rolling90">Last 90 Days</option>
              <option value="Rolling365">Rolling 365 Days</option>
            </optgroup>
            <optgroup label="All Time">
              <option value="AllTime">All Time</option>
            </optgroup>
            <optgroup label="Custom">
              <option value="Custom">Manual Date Range…</option>
            </optgroup>
          </select>

          {timePeriod === 'Custom' && (
            <div className="date-range-picker">
              <input
                type="date"
                className="filter-select"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
              />
              <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>to</span>
              <input
                type="date"
                className="filter-select"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
              />
            </div>
          )}

          <button className="theme-toggle" onClick={() => setShowSettings(true)} aria-label="Settings">
            <Settings size={20} />
          </button>
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle Theme">
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </header>

      {showSettings && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--bg-card)', padding: '24px', borderRadius: '12px', width: '400px', border: '1px solid var(--border-color)' }}>
            <h2 style={{ marginBottom: '16px' }}>Forecast Settings</h2>
            
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Annual Revenue Target ($)</label>
              <input type="number" value={target} onChange={e => setTarget(Number(e.target.value))} style={{ width: '100%', padding: '8px', background: 'var(--bg-app)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '4px' }} />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Working Days / Week</label>
              <input type="number" value={workingDaysPerWeek} onChange={e => setWorkingDaysPerWeek(Number(e.target.value))} style={{ width: '100%', padding: '8px', background: 'var(--bg-app)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '4px' }} />
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Anticipated Vacation/Holidays (Days)</label>
              <input type="number" value={vacationDays} onChange={e => setVacationDays(Number(e.target.value))} style={{ width: '100%', padding: '8px', background: 'var(--bg-app)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '4px' }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowSettings(false)} style={{ padding: '8px 16px', background: 'var(--accent-primary)', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Close</button>
            </div>
          </div>
        </div>
      )}

      <div className="kpi-grid">
        <MetricCard
          title={`Total Fees (${periodLabel})`}
          value={filteredKpis?.totalFeesYTD ?? 0}
          icon={DollarSign}
          delayClass="delay-1"
        />
        <MetricCard
          title={`WIP (${periodLabel})`}
          value={filteredKpis?.totalWIP ?? 0}
          icon={Clock}
          delayClass="delay-2"
        />
        <MetricCard
          title="Total A/R"
          value={filteredKpis?.totalAR ?? 0}
          icon={FileText}
          delayClass="delay-3"
        />
        <MetricCard
          title={`Actual Income (${periodLabel})`}
          value={filteredKpis?.totalIncomeYTD ?? 0}
          icon={CheckCircle}
          delayClass="delay-4"
        />
      </div>

      <div className="charts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px' }}>
        <AnnualForecast
          target={target}
          basisDays={(52 * workingDaysPerWeek) - vacationDays}
          totalFeesYTD={filteredKpis?.totalFeesYTD ?? 0}
          delayClass="delay-2"
        />
        <TopClients
          data={liveData.topClientsData}
          delayClass="delay-3"
        />
        <div style={{ gridColumn: 'span 2' }}>
          <ProductionChart data={liveData.productionData} delayClass="delay-4" />
        </div>
      </div>
      
      <div className="charts-grid" style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        <PipelineChart data={liveData.pipelineData} delayClass="delay-5" />
      </div>
    </div>
  );
}

export default App;
