import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HashRouter } from 'react-router-dom';
import { App } from './App';
import './styles.scss';

const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={client}><HashRouter><App /></HashRouter></QueryClientProvider></StrictMode>);
