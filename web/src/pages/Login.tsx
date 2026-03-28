import { useState } from 'react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // First GET to get CSRF cookie
      await fetch('/v1/auth/login', { credentials: 'include' });

      const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
      const csrfToken = csrfMatch ? csrfMatch[1] : '';

      const res = await fetch('/v1/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Login failed');
        return;
      }

      if (data.authenticated) {
        // Clear any stale token — we're using session auth now
        localStorage.removeItem('vtf_token');
        // Full reload to re-initialize AuthProvider with session cookie
        window.location.href = '/';
      }
    } catch {
      setError('Connection failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center px-4">
      {/* Brand */}
      <div className="flex flex-col items-center mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center">
            <span className="material-symbols-outlined text-on-primary text-2xl">deployed_code</span>
          </div>
          <span className="text-3xl font-headline font-extrabold text-on-surface">VTaskForge</span>
        </div>
        <span className="text-[10px] uppercase tracking-widest text-on-surface-variant">
          Task Orchestration Platform
        </span>
      </div>

      {/* Login card */}
      <div className="w-full max-w-[400px] bg-surface-container-lowest p-8 rounded-xl shadow-lg">
        <h2 className="text-xl font-headline font-bold text-on-surface mb-1">Welcome back</h2>
        <p className="text-sm text-on-surface-variant mb-6">
          Sign in to access your fleet and projects.
        </p>

        {error && (
          <div className="flex items-center gap-2 px-4 py-3 mb-4 bg-error-container rounded-lg text-on-error-container text-sm">
            <span className="material-symbols-outlined text-lg">error</span>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Username */}
          <div className="mb-4">
            <label
              htmlFor="username"
              className="block mb-1.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant"
            >
              Username
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
                person
              </span>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                className="w-full pl-10 pr-3 py-2.5 bg-surface-container-low border-none rounded-lg text-on-surface text-sm placeholder:text-outline focus:ring-2 focus:ring-primary"
                placeholder="Enter your username"
              />
            </div>
          </div>

          {/* Password */}
          <div className="mb-4">
            <label
              htmlFor="password"
              className="block mb-1.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant"
            >
              Password
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
                lock
              </span>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full pl-10 pr-3 py-2.5 bg-surface-container-low border-none rounded-lg text-on-surface text-sm placeholder:text-outline focus:ring-2 focus:ring-primary"
                placeholder="Enter your password"
              />
            </div>
          </div>

          {/* Remember me + Forgot password */}
          <div className="flex items-center justify-between mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-outline text-primary focus:ring-primary"
              />
              <span className="text-xs text-on-surface-variant">Remember me</span>
            </label>
            <button type="button" className="text-xs text-primary hover:underline">
              Forgot password?
            </button>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className={`w-full primary-gradient text-on-primary py-3 rounded-full font-headline text-sm font-bold transition-opacity ${
              loading ? 'opacity-70 cursor-wait' : 'opacity-100 cursor-pointer hover:opacity-90'
            }`}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>

      {/* Footer */}
      <p className="mt-6 text-xs text-on-surface-variant">
        Don't have an account?{' '}
        <button type="button" className="text-primary font-semibold hover:underline">
          Contact your admin
        </button>
      </p>
    </div>
  );
}
