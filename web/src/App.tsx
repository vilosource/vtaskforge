import { BrowserRouter, Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { ActiveProjectProvider } from './contexts/ActiveProjectContext';
import { ConsoleWidgetProvider, useConsoleWidget } from './contexts/ConsoleWidgetContext';
import { ChatWidgetProvider, useChatWidget } from './contexts/ChatWidgetContext';
import { ConsoleWidget } from './components/ConsoleWidget';
import { ChatWidget } from './components/ChatWidget';
import { Home } from './pages/Home';
import { ProjectList } from './pages/ProjectList';
import { ProjectDashboard } from './pages/ProjectDashboard';
import { WorkplanDetail } from './pages/WorkplanDetail';
import { BoardView } from './pages/BoardView';
import { BacklogView } from './pages/BacklogView';
import { TaskPage } from './pages/TaskPage';
import { AgentList } from './pages/AgentList';
import { AgentDetail } from './pages/AgentDetail';
import { ProfilePage } from './pages/ProfilePage';
import { AdminUsersPage } from './pages/AdminUsersPage';
import { AdminUserDetailPage } from './pages/AdminUserDetailPage';
import { AdminLocksPage } from './pages/AdminLocksPage';
import { AdminChannelMappingsPage } from './pages/AdminChannelMappingsPage';
import { Sidebar } from './components/Sidebar';
import Login from './pages/Login';

const queryClient = new QueryClient();

interface AuthState {
  authenticated: boolean;
  loading: boolean;
  username: string;
  isStaff: boolean;
  userType: string;
  projects: { project_id: string; role: string }[];
  tokenReady: boolean;
}

const AUTH_DEFAULT: AuthState = {
  authenticated: false, loading: true, username: '',
  isStaff: false, userType: '', projects: [], tokenReady: false,
};

const AuthContext = createContext<AuthState>(AUTH_DEFAULT);

export function useAuth() {
  return useContext(AuthContext);
}

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(AUTH_DEFAULT);

  useEffect(() => {
    // Note if a token already exists (from previous session or CLI auth)
    const hasToken = !!localStorage.getItem('vtf_token');

    // Check session auth via login endpoint first
    fetch('/v1/auth/login', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        if (!data.authenticated) {
          setAuth({ ...AUTH_DEFAULT, loading: false });
          return;
        }
        // Enrich with validate endpoint for staff/type/projects
        fetch('/v1/auth/validate/', {
          credentials: 'include',
          headers: { Accept: 'application/json' },
        })
          .then((r) => r.json())
          .then((profile) => {
            setAuth((prev) => ({
              authenticated: true,
              loading: false,
              username: profile.username || data.username || '',
              isStaff: profile.is_staff || false,
              userType: profile.user_type || 'human',
              projects: profile.projects || [],
              tokenReady: prev.tokenReady || hasToken,
            }));
          })
          .catch(() => {
            // Validate failed but login succeeded — use basic info
            setAuth({
              ...AUTH_DEFAULT,
              authenticated: true, loading: false,
              username: data.username || '',
            });
          });

        // Ensure vtf_token exists for bridge chat widget
        if (!localStorage.getItem('vtf_token')) {
          const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
          const csrfToken = csrfMatch ? csrfMatch[1] : '';
          fetch('/v1/auth/token/', {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
              ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
            },
          })
            .then((r) => (r.ok ? r.json() : null))
            .then((tokenData) => {
              if (tokenData?.token) {
                localStorage.setItem('vtf_token', tokenData.token);
                setAuth((prev) => ({ ...prev, tokenReady: true }));
              }
            })
            .catch((err) => {
              console.warn('Token provisioning failed:', err);
            });
        }
      })
      .catch(() => {
        setAuth({ ...AUTH_DEFAULT, loading: false });
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const toggleSidebar = useCallback(() => setSidebarCollapsed(prev => !prev), []);
  const { isOpen: consoleOpen, layout: consoleLayout, dockWidth: consoleDockWidth } = useConsoleWidget();
  const { isOpen: chatOpen, layout: chatLayout, dockWidth: chatDockWidth } = useChatWidget();
  const consoleDocked = consoleOpen && consoleLayout === 'docked';
  const chatDocked = chatOpen && chatLayout === 'docked';
  const totalMarginRight = (consoleDocked ? consoleDockWidth : 0) + (chatDocked ? chatDockWidth : 0);

  return (
    <RequireAuth>
      <div className="flex min-h-screen w-full bg-surface font-body text-on-surface">
        <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
        <main
          className={`flex-1 min-w-0 overflow-x-auto transition-[margin] duration-200 ${sidebarCollapsed ? 'ml-10' : 'ml-64'}`}
          style={totalMarginRight > 0 ? { marginRight: totalMarginRight } : undefined}
        >
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
          <ConsoleWidgetProvider>
          <ChatWidgetProvider>
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
              <Route path="/settings" element={<ProfilePage />} />
              <Route path="/settings/profile" element={<ProfilePage />} />
              <Route path="/manage/users" element={<AdminUsersPage />} />
              <Route path="/manage/users/:id" element={<AdminUserDetailPage />} />
              <Route path="/manage/locks" element={<AdminLocksPage />} />
              <Route path="/manage/channel-mappings" element={<AdminChannelMappingsPage />} />
            </Route>
          </Routes>
          <ConsoleWidget />
          <ChatWidget />
          </ChatWidgetProvider>
          </ConsoleWidgetProvider>
          </ActiveProjectProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
