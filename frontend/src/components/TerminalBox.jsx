import React from 'react';
import '../styles/terminal.css';

const TerminalBox = ({ title = '', children, width = '100%' }) => {
  return (
    <div className="term-box-container" style={{ width, maxWidth: '90vw' }}>
      {title && (
        <div className="term-box-top">
          {title}
        </div>
      )}
      <div className="term-box-content">
        {children}
      </div>
    </div>
  );
};

export default TerminalBox;
