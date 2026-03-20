import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkplanList } from './pages/WorkplanList';
import { BoardView } from './pages/BoardView';

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<WorkplanList />} />
          <Route path="/workplans/:id" element={<BoardView />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
