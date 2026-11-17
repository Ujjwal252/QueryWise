
import { useEffect, useState } from "react";
import { api } from "./services/api";
import DatabaseConnections from "./components/DatabaseConnections";
import SQLWorkspace from "./components/SQLWorkspace";
import QueryHistory from "./components/QueryHistory";
import PerformanceDashboard from "./components/PerformanceDashboard";
import ExecutionPlans from "./components/ExecutionPlans";
import SecurityAnalysis from "./components/SecurityAnalysis";
import "./App.css";

const NAVIGATION_ITEMS = [
  { name: "Dashboard", icon: "▦" },
  { name: "SQL Workspace", icon: "⌘" },
  { name: "Database Connections", icon: "▤" },
  { name: "Query History", icon: "◷" },
  { name: "Performance", icon: "↗" },
  { name: "Execution Plans", icon: "⌁" },
  { name: "Security Analysis", icon: "⬡" },
];

function App() {
  const [user, setUser] = useState(null);
  const [activePage, setActivePage] = useState("Dashboard");

  const [authLoading, setAuthLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState("Checking...");

  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState("");

  const [authMode, setAuthMode] = useState("login");
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authMessage, setAuthMessage] = useState("");

  const [loginForm, setLoginForm] = useState({
    identifier: "",
    password: "",
  });

  const [registerForm, setRegisterForm] = useState({
    full_name: "",
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  // Restore login session and check backend health.
  useEffect(() => {
    let mounted = true;

    async function initializeApp() {
      try {
        const health = await api.checkHealth();

        if (mounted) {
          setBackendStatus(
            health.status === "success" || health.status === "healthy"
              ? "Connected"
              : "Available"
          );
        }
      } catch {
        if (mounted) {
          setBackendStatus("Disconnected");
        }
      }

      try {
        const response = await api.getCurrentUser();

        if (mounted && response.user) {
          setUser(response.user);
        }
      } catch {
        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setAuthLoading(false);
        }
      }
    }

    initializeApp();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    async function loadDashboardSummary() {
      if (!user || activePage !== "Dashboard") return;

      setDashboardLoading(true);
      setDashboardError("");

      try {
        const response = await api.getDashboardSummary();
        if (mounted) setDashboardSummary(response.data || response);
      } catch (error) {
        if (mounted) {
          setDashboardError(error.message || "Unable to load dashboard statistics.");
        }
      } finally {
        if (mounted) setDashboardLoading(false);
      }
    }

    loadDashboardSummary();
    return () => { mounted = false; };
  }, [user, activePage]);

  function handleLoginChange(event) {
    const { name, value } = event.target;

    setLoginForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function handleRegisterChange(event) {
    const { name, value } = event.target;

    setRegisterForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function switchAuthMode(mode) {
    setAuthMode(mode);
    setAuthError("");
    setAuthMessage("");
  }

  // Login.
  async function handleLogin(event) {
    event.preventDefault();

    setAuthError("");
    setAuthMessage("");

    if (!loginForm.identifier.trim() || !loginForm.password) {
      setAuthError("Please enter your username/email and password.");
      return;
    }

    try {
      setAuthSubmitting(true);

      const response = await api.login(
        loginForm.identifier.trim(),
        loginForm.password
      );

      if (!response.user) {
        throw new Error(
          "Login succeeded but user information was not returned."
        );
      }

      setUser(response.user);
      setActivePage("Dashboard");

      setLoginForm({
        identifier: "",
        password: "",
      });
    } catch (error) {
      setAuthError(error.message || "Unable to log in. Please try again.");
    } finally {
      setAuthSubmitting(false);
    }
  }

  // Registration.
  async function handleRegister(event) {
    event.preventDefault();

    setAuthError("");
    setAuthMessage("");

    const {
      full_name,
      username,
      email,
      password,
      confirmPassword,
    } = registerForm;

    if (!username.trim() || !email.trim() || !password) {
      setAuthError("Please fill in all required fields.");
      return;
    }

    if (password.length < 8) {
      setAuthError("Password must contain at least 8 characters.");
      return;
    }

    if (new TextEncoder().encode(password).length > 72) {
      setAuthError("Password must not exceed 72 UTF-8 bytes.");
      return;
    }

    if (password !== confirmPassword) {
      setAuthError("Passwords do not match.");
      return;
    }

    try {
      setAuthSubmitting(true);

      await api.register({
        full_name: full_name.trim(),
        username: username.trim(),
        email: email.trim(),
        password,
      });

      setRegisterForm({
        full_name: "",
        username: "",
        email: "",
        password: "",
        confirmPassword: "",
      });

      setAuthMode("login");

      setLoginForm({
        identifier: email.trim(),
        password: "",
      });

      setAuthMessage(
        "Registration successful! Please log in using your credentials."
      );
    } catch (error) {
      setAuthError(error.message || "Registration failed. Please try again.");
    } finally {
      setAuthSubmitting(false);
    }
  }

  // Logout.
  async function handleLogout() {
    try {
      await api.logout();
    } catch (error) {
      console.error("Logout request failed:", error);
    } finally {
      setUser(null);
      setActivePage("Dashboard");
      setAuthMode("login");
      setAuthError("");
      setAuthMessage("");
    }
  }

  if (authLoading) {
    return (
      <div className="auth-loading-screen">
        Loading QueryWise...
      </div>
    );
  }

  // Authentication screens.
  if (!user) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-logo">
            QueryWise<span>.</span>
          </div>

          {authMode === "login" ? (
            <>
              <h1>Welcome back</h1>

              <p className="auth-subtitle">
                Sign in to access your intelligent database query optimizer.
              </p>

              {authError && (
                <div className="auth-error">{authError}</div>
              )}

              {authMessage && (
                <div className="auth-message">{authMessage}</div>
              )}

              <form className="auth-form" onSubmit={handleLogin}>
                <label>
                  Username or Email
                  <input
                    type="text"
                    name="identifier"
                    placeholder="Enter your username or email"
                    value={loginForm.identifier}
                    onChange={handleLoginChange}
                    autoComplete="username"
                    required
                  />
                </label>

                <label>
                  Password
                  <input
                    type="password"
                    name="password"
                    placeholder="Enter your password"
                    value={loginForm.password}
                    onChange={handleLoginChange}
                    autoComplete="current-password"
                    required
                  />
                </label>

                <button
                  type="submit"
                  className="auth-button"
                  disabled={authSubmitting}
                >
                  {authSubmitting ? "Signing in..." : "Sign In"}
                </button>
              </form>

              <div className="auth-switch">
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => switchAuthMode("register")}
                >
                  Create Account
                </button>
              </div>
            </>
          ) : (
            <>
              <h1>Create account</h1>

              <p className="auth-subtitle">
                Register to start analyzing and optimizing your SQL queries.
              </p>

              {authError && (
                <div className="auth-error">{authError}</div>
              )}

              <form className="auth-form" onSubmit={handleRegister}>
                <label>
                  Full Name
                  <input
                    type="text"
                    name="full_name"
                    placeholder="Enter your full name"
                    value={registerForm.full_name}
                    onChange={handleRegisterChange}
                    autoComplete="name"
                  />
                </label>

                <label>
                  Username
                  <input
                    type="text"
                    name="username"
                    placeholder="Choose a username"
                    value={registerForm.username}
                    onChange={handleRegisterChange}
                    autoComplete="username"
                    required
                  />
                </label>

                <label>
                  Email
                  <input
                    type="email"
                    name="email"
                    placeholder="Enter your email"
                    value={registerForm.email}
                    onChange={handleRegisterChange}
                    autoComplete="email"
                    required
                  />
                </label>

                <label>
                  Password
                  <input
                    type="password"
                    name="password"
                    placeholder="Create a password"
                    value={registerForm.password}
                    onChange={handleRegisterChange}
                    autoComplete="new-password"
                    required
                  />
                </label>

                <label>
                  Confirm Password
                  <input
                    type="password"
                    name="confirmPassword"
                    placeholder="Confirm your password"
                    value={registerForm.confirmPassword}
                    onChange={handleRegisterChange}
                    autoComplete="new-password"
                    required
                  />
                </label>

                <button
                  type="submit"
                  className="auth-button"
                  disabled={authSubmitting}
                >
                  {authSubmitting ? "Creating Account..." : "Create Account"}
                </button>
              </form>

              <div className="auth-switch">
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => switchAuthMode("login")}
                >
                  Sign In
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  const displayName =
    user.full_name || user.username || user.email || "User";

  const avatarLetter = displayName.charAt(0).toUpperCase();

  async function refreshDashboard() {
    setDashboardLoading(true);
    setDashboardError("");
    try {
      const response = await api.getDashboardSummary();
      setDashboardSummary(response.data || response);
    } catch (error) {
      setDashboardError(error.message || "Unable to refresh dashboard statistics.");
    } finally {
      setDashboardLoading(false);
    }
  }

  // Dashboard.
  function renderDashboard() {
    return (
      <>
        <div className="dashboard-welcome">
          <div>
            <h2>Welcome back, {displayName}!</h2>
            <p>Here's an overview of your QueryWise workspace.</p>
          </div>
          <button
            type="button"
            className="quick-action"
            onClick={refreshDashboard}
            disabled={dashboardLoading}
          >
            {dashboardLoading ? "Refreshing..." : "↻ Refresh"}
          </button>
        </div>

        {dashboardError && (
          <div className="auth-error" role="alert">{dashboardError}</div>
        )}

        <div className="metrics-grid">
          <div className="metric-card">
            <h3>Database Connections</h3>
            <div className="metric-value">{dashboardLoading && !dashboardSummary ? "…" : (dashboardSummary?.database_connections ?? "—")}</div>
            <div className="metric-description">
              Your saved database connections
            </div>
          </div>

          <div className="metric-card">
            <h3>Recorded Queries</h3>
            <div className="metric-value">{dashboardLoading && !dashboardSummary ? "…" : (dashboardSummary?.queries_analyzed ?? "—")}</div>
            <div className="metric-description">
              Query history records saved
            </div>
          </div>

          <div className="metric-card">
            <h3>Optimizations</h3>
            <div className="metric-value">{dashboardLoading && !dashboardSummary ? "…" : (dashboardSummary?.optimizations_generated ?? "—")}</div>
            <div className="metric-description">
              Optimization reports generated
            </div>
          </div>

          <div className="metric-card">
            <h3>Security Findings</h3>
            <div className="metric-value">{dashboardLoading && !dashboardSummary ? "…" : (dashboardSummary?.security_findings ?? "—")}</div>
            <div className="metric-description">
              Database security findings
            </div>
          </div>
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-panel">
            <h3>Quick Actions</h3>

            <div className="quick-actions">
              <button
                className="quick-action"
                onClick={() => setActivePage("SQL Workspace")}
              >
                ⌘ &nbsp; Analyze SQL Query
              </button>

              <button
                className="quick-action"
                onClick={() => setActivePage("Database Connections")}
              >
                ▤ &nbsp; Add Database
              </button>

              <button
                className="quick-action"
                onClick={() => setActivePage("Performance")}
              >
                ↗ &nbsp; Compare Performance
              </button>

              <button
                className="quick-action"
                onClick={() => setActivePage("Security Analysis")}
              >
                ⬡ &nbsp; Security Analysis
              </button>
            </div>
          </div>

          <div className="dashboard-panel">
            <h3>System Status</h3>

            <div className="system-status">
              <div className="status-item">
                <span>Backend API</span>
                <span
                  className={`status-indicator ${
                    backendStatus === "Disconnected" ? "disconnected" : ""
                  }`}
                >
                  {backendStatus}
                </span>
              </div>

              <div className="status-item">
                <span>Authentication</span>
                <span className="status-indicator">Active</span>
              </div>

              <div className="status-item">
                <span>Query Optimizer</span>
                <span className="status-indicator">Ready</span>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  // Page routing.
  function renderActivePage() {
    switch (activePage) {
      case "Dashboard":
        return renderDashboard();

      case "SQL Workspace":
        return <SQLWorkspace />;

      case "Database Connections":
        return <DatabaseConnections />;

      case "Query History":
        return <QueryHistory />;

      case "Performance":
        return <PerformanceDashboard />;

      case "Execution Plans":
        return <ExecutionPlans />;

      case "Security Analysis":
        return <SecurityAnalysis />;

      default:
        return (
          <div className="placeholder-page">
            <h2>{activePage}</h2>
            <p>
              This module will be implemented in the upcoming development
              phase.
            </p>
          </div>
        );
    }
  }

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          Query<span>Wise</span>
        </div>

        <nav className="sidebar-nav">
          {NAVIGATION_ITEMS.map((item) => (
            <button
              key={item.name}
              type="button"
              className={activePage === item.name ? "active" : ""}
              onClick={() => setActivePage(item.name)}
            >
              <span>{item.icon}</span>
              {item.name}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            type="button"
            className="logout-button"
            onClick={handleLogout}
          >
            ↪ &nbsp; Logout
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <h1>{activePage}</h1>
            <p>Intelligent Database Query Optimizer</p>
          </div>

          <div className="user-profile">
            <div className="user-avatar">{avatarLetter}</div>

            <div>
              <div className="user-profile-name">{displayName}</div>
              <div className="user-profile-email">{user.email}</div>
            </div>
          </div>
        </header>

        {renderActivePage()}
      </main>
    </div>
  );
}

export default App;
