import React, { useState, useEffect } from 'react';
import { Calendar, CheckSquare, AlertCircle, AlertTriangle, FileText } from 'lucide-react';
import './index.css';

function App() {
  const [briefing, setBriefing] = useState(null);
  const [hydrationError, setHydrationError] = useState(null);

  useEffect(() => {
    window.hydrateBriefing = (payload) => {
      console.log("hydrateBriefing called", payload);
      if (!payload) {
        setHydrationError("hydrateBriefing was called with a null/undefined payload.");
        return;
      }
      if (!payload.ok) {
        setHydrationError(`Backend error: ${payload.message || "Unknown error from Python backend."}`);
        return;
      }
      setHydrationError(null);
      setBriefing(payload);
    };
    return () => { delete window.hydrateBriefing; };
  }, []);

  // --- ERROR STATE ---
  if (hydrationError) {
    return (
      <div className="dashboard-container">
        <div className="error-banner">
          <h2><AlertTriangle size={20} /> Practice Briefing Error</h2>
          <p>{hydrationError}</p>
          <p style={{ fontSize: '12px', marginTop: '8px', opacity: 0.6 }}>
            Check <code>logs/cspm.log</code> for details.
          </p>
        </div>
      </div>
    );
  }

  // --- LOADING STATE ---
  if (!briefing) {
    return (
      <div className="dashboard-container">
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          minHeight: '300px', color: 'var(--text-muted)', fontSize: '14px'
        }}>
          Waiting for briefing data from backend…
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <header className="header animated delay-1">
        <div>
          <h1>Practice Briefing</h1>
          <div className="subtitle">As of {briefing.asOfDate}</div>
        </div>
      </header>

      <div className="grid">
        {/* Today's Tasks */}
        <div className="panel animated delay-1">
          <div className="panel-header">
            <CheckSquare className="icon" size={20} />
            <h2>Today's Tasks</h2>
            <span className="badge" style={{marginLeft: 'auto'}}>{briefing.todaysTasks?.length || 0}</span>
          </div>
          <div className="list">
            {briefing.todaysTasks?.length === 0 ? (
              <div className="item-subtitle" style={{padding: '12px'}}>No tasks scheduled for today.</div>
            ) : (
              briefing.todaysTasks?.map((task, i) => (
                <div key={i} className="list-item">
                  <div className="item-title">{task.title || task.matterName || "Task"}</div>
                  <div className="item-subtitle">{task.client || task.clientName || ""}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Upcoming Deadlines */}
        <div className="panel animated delay-2">
          <div className="panel-header">
            <Calendar className="icon" size={20} />
            <h2>Upcoming Deadlines</h2>
            <span className="badge warning" style={{marginLeft: 'auto'}}>{briefing.upcomingDeadlines?.length || 0}</span>
          </div>
          <div className="list">
            {briefing.upcomingDeadlines?.length === 0 ? (
              <div className="item-subtitle" style={{padding: '12px'}}>No upcoming deadlines.</div>
            ) : (
              briefing.upcomingDeadlines?.map((item, i) => (
                <div key={i} className="list-item">
                  <div className="item-title">{item.title || item.matterName || "Deadline"}</div>
                  <div className="item-subtitle">{item.date} • {item.client || item.clientName || ""}</div>
                </div>
              ))
            )}
          </div>
        </div>
        
        {/* Overdue Items */}
        <div className="panel animated delay-3">
          <div className="panel-header">
            <AlertCircle className="icon" size={20} color="var(--error)" />
            <h2>Overdue Action Items</h2>
            <span className="badge error" style={{marginLeft: 'auto'}}>
              {(briefing.overdueDeadlines?.length || 0) + (briefing.overdueBills?.length || 0)}
            </span>
          </div>
          <div className="list">
            {briefing.overdueDeadlines?.length === 0 && briefing.overdueBills?.length === 0 ? (
              <div className="item-subtitle" style={{padding: '12px'}}>No overdue items. Great job!</div>
            ) : (
              <>
                {briefing.overdueDeadlines?.map((item, i) => (
                  <div key={`od-${i}`} className="list-item">
                    <span className="badge error" style={{width: 'fit-content', marginBottom: '4px'}}>Overdue Deadline</span>
                    <div className="item-title">{item.title || item.matterName || "Deadline"}</div>
                    <div className="item-subtitle">{item.date} • {item.client || item.clientName || ""}</div>
                  </div>
                ))}
                {briefing.overdueBills?.map((item, i) => (
                  <div key={`ob-${i}`} className="list-item">
                    <span className="badge error" style={{width: 'fit-content', marginBottom: '4px'}}>Overdue Invoice</span>
                    <div className="item-title">Invoice {item.invoice || "Unknown"} — {item.client || item.workClient || ""}</div>
                    <div className="item-subtitle">
                      ${Number(item.wipAmount || 0).toLocaleString()} outstanding • {item.daysOld || 0} days overdue
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>

        {/* Ready to Bill */}
        <div className="panel animated delay-3">
          <div className="panel-header">
            <FileText className="icon" size={20} color="var(--success)" />
            <h2>Ready to Bill</h2>
            <span className="badge success" style={{marginLeft: 'auto'}}>{briefing.readyToBillMatters?.length || 0}</span>
          </div>
          <div className="list">
            {briefing.readyToBillMatters?.length === 0 ? (
              <div className="item-subtitle" style={{padding: '12px'}}>No matters ready for billing.</div>
            ) : (
              briefing.readyToBillMatters?.map((item, i) => (
                <div key={i} className="list-item">
                  <div className="item-title">{item.matterName || item.matterId || "Matter"}</div>
                  <div className="item-subtitle">
                    {item.clientName || ""} • {item.entryCount || 0} entries • ${Number(item.wipAmount || 0).toLocaleString()} WIP
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
