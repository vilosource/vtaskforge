import { BrowserRouter, Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createContext, useContext, useEffect, useState } from 'react';
import { ActiveProjectProvider } from './contexts/ActiveProjectContext';
import { Home } from './pages/Home';
import { ProjectList } from './pages/ProjectList';
import { ProjectDashboard } from './pages/ProjectDashboard';
import { WorkplanDetail } from './pages/WorkplanDetail';
import { BoardView } from './pages/BoardView';
import { BacklogView } from './pages/BacklogView';
import { TaskPage } from './pages/TaskPage';
import { AgentList } from './pages/AgentList';
import { AgentDetail } from './pages/AgentDetail';
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
    return <div className="p-10 text-center text-on-surface-variant font-body">Loading...</div>;
  }

  if (!authenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function AppLayout() {
  return (
    <RequireAuth>
      <div className="flex min-h-screen w-full bg-surface font-body text-on-surface">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-x-auto ml-64">
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
          <ActiveProjectProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<AppLayout />}>
              <Route path="/" element={<Home />} />
              <Route path="/projects" element={<ProjectList />} />
              <Route path="/projects/:id" element={<ProjectDashboard />} />
              <Route path="/projects/:id/backlog" element={<BacklogView />} />
              <Route path="/projects/:id/workplans/:wid" element={<WorkplanDetail />} />
              <Route path="/projects/:id/workplans/:wid/milestones/:milestoneId" element={<BoardView />} />
              <Route path="/tasks/:id" element={<TaskPage />} />
              <Route path="/agents" element={<AgentList />} />
              <Route path="/agents/:id" element={<AgentDetail />} />
            </Route>
          </Routes>
          </ActiveProjectProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
