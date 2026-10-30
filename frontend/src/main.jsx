import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './app/App.jsx';
import { ToastHost } from './ds/index.jsx';
import './ds/tokens.css';
import './ds/ds.css';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastHost>
        <App />
      </ToastHost>
    </BrowserRouter>
  </React.StrictMode>,
);
