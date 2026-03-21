import { BrowserRouter, Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createContext, useContext, useEffect, useState } from 'react';
import { WorkplanList } from './pages/WorkplanList';
import { WorkplanDetail } from './pages/WorkplanDetail';
import { BoardView } from './pages/BoardView';
import { TaskPage } from './pages/TaskPage';
import { Sidebar } from './components/Sidebar';
import Login from './pages/Login';

const queryClient = new QueryClient();

interface AuthState {
  authenticated: boolean;
  loading: boolean;
  username: string;
}

const AuthContext = createContext<AuthState>({ authenticated: false, loading: true, username: '' });

export function useAuth() {
  return useContext(AuthContext);
}

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ authenticated: false, loading: true, username: '' });

  useEffect(() => {
    // Check if we have a token in localStorage (agent/CLI auth)
    const token = localStorage.getItem('vtf_token');
    if (token) {
      setAuth({ authenticated: true, loading: false, username: 'token-user' });
      return;
    }

    // Check session auth
    fetch('/v1/auth/login', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        setAuth({ authenticated: data.authenticated, loading: false, username: data.username || '' });
      })
      .catch(() => {
        setAuth({ authenticated: false, loading: false, username: '' });
      });
  }, []);

  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { authenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center' }}>Loading...</div>;
  }

  if (!authenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function AppLayout() {
  return (
    <RequireAuth>
      <div className="app-layout">
        <Sidebar />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </RequireAuth>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<AppLayout />}>
              <Route path="/" element={<WorkplanList />} />
              <Route path="/workplans/:id" element={<WorkplanDetail />} />
              <Route path="/workplans/:id/phases/:phaseId" element={<BoardView />} />
              <Route path="/tasks/:id" element={<TaskPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
