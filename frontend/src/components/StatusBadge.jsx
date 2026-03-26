import React from 'react';
import '../styles/terminal.css';

const StatusBadge = ({ status }) => {
  const normalizedStatus = status?.toLowerCase() || 'stable';
  
  const statusConfig = {
    critical: { icon: '🔴', text: 'CRITICAL', className: 'status-critical' },
    warning: { icon: '🟡', text: 'WARNING', className: 'status-warning' },
    stable: { icon: '🟢', text: 'STABLE', className: 'status-stable' },
    connected: { icon: '●', text: 'CONNECTED', className: 'status-connected' },
    disconnected: { icon: '○', text: 'DISCONNECTED', className: 'status-disconnected' }
  };

  const config = statusConfig[normalizedStatus] || statusConfig.stable;

  return (
    <span className={`status-badge ${config.className}`}>
      {config.icon} {config.text}
    </span>
  );
};

export default StatusBadge;
