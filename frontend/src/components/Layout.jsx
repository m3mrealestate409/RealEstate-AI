import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const isAdmin = user?.role === "admin";
  const isManager = user?.role === "admin" || user?.role === "manager";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CH</div>
          <div>
            <div className="brand-name">Chaahat Homes</div>
            <div className="brand-sub">Knowledge Engine</div>
          </div>
        </div>

        <nav className="nav">
          <NavLink to="/" end className="nav-link">
            <span className="nav-ic">💬</span> Ask
          </NavLink>
          <NavLink to="/projects" className="nav-link">
            <span className="nav-ic">🏢</span> Projects
          </NavLink>
          <NavLink to="/calculators" className="nav-link">
            <span className="nav-ic">🧮</span> Calculators
          </NavLink>
          {isManager && (
            <NavLink to="/dashboard" className="nav-link">
              <span className="nav-ic">📊</span> Analytics
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/knowledge" className="nav-link">
              <span className="nav-ic">📚</span> Knowledge
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/system" className="nav-link">
              <span className="nav-ic">🩺</span> System Health
            </NavLink>
          )}
          {isAdmin && (
            <NavLink to="/admin" className="nav-link">
              <span className="nav-ic">⚙️</span> Admin
            </NavLink>
          )}
        </nav>

        <div className="sidebar-foot">
          <div className="user-chip">
            <div className="avatar">{(user?.name || user?.email || "?")[0].toUpperCase()}</div>
            <div className="user-meta">
              <div className="user-name">{user?.name || user?.email}</div>
              <div className={`role-badge role-${user?.role}`}>{user?.role}</div>
            </div>
          </div>
          <button className="btn btn-ghost btn-block" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
