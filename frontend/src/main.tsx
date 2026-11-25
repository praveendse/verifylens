import '@fontsource-variable/geist';
import './styles/global.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element in index.html');

// StrictMode runs effects twice in development to surface missing cleanups.
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
