import React, { useEffect } from 'react';
import '../styles/terminal.css';

const TerminalLayout = ({ children, pageTitle = 'SYSTEM DASHBOARD' }) => {
  useEffect(() => {
    document.body.classList.add('terminal-mode');
    return () => {
      document.body.classList.remove('terminal-mode');
    };
  }, []);

  const handleLogout = () => {
    console.log('Logging out...');
  };

  return (
    <div className="term-layout">
      <header className="term-header">
        <div className="term-header-left">
          <h1>MediRoute</h1>
          <span className="term-header-title">[{pageTitle}]</span>
        </div>
        <button className="term-btn" onClick={handleLogout}>
          [ LOGOUT ]
        </button>
      </header>
      <main className="term-content">
        {children}
      </main>
    </div>
  );
};

export default TerminalLayout;
