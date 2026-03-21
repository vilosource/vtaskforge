import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/global.css';
import './styles/kanban.css';
import './styles/modal.css';
import './styles/components.css';
import './styles/sidebar.css';
import './styles/workplan-detail.css';
import { App } from './App';

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('No root element found');

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
