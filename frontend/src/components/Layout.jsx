import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { BrandMark } from "./Logo.jsx";
import Icon from "./Icons.jsx";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  function handleLogout() {
    closeMenu();
    logout();
    navigate("/login");
  }

  const isSuperAdmin = user?.is_super_admin === true;
  const isAdmin = user?.role === "admin";
  const isManager = user?.role === "admin" || user?.role === "manager";
  const canLiveChat = isAdmin || isSuperAdmin || user?.can_live_chat === true;

  return (
    <div className="app-shell">
      {/* Mobile / tablet top bar with hamburger */}
      <header className="mobile-topbar">
        <button className="hamburger" onClick={() => setMenuOpen(true)} aria-label="Open menu">
          <Icon name="menu" size={22} />
        </button>
        <BrandMark size={26} />
        <span className="mobile-brand">PropX Estate</span>
      </header>

      {menuOpen && <div className="sidebar-backdrop" onClick={closeMenu} />}

      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <BrandMark size={38} />
          <div>
            <div className="brand-name">PropX Estate</div>
            <div className="brand-sub">Knowledge Guru</div>
          </div>
          <button className="drawer-close" onClick={closeMenu} aria-label="Close menu">
            <Icon name="close" size={20} />
          </button>
        </div>

        <nav className="nav" onClick={closeMenu}>
          <NavLink to="/" end className="nav-link">
            <span className="nav-ic"><Icon name="ask" /></span> Ask
          </NavLink>
          <NavLink to="/projects" className="nav-link">
            <span className="nav-ic"><Icon name="projects" /></span> Projects
          </NavLink>
          <NavLink to="/calculators" className="nav-link">
            <span className="nav-ic"><Icon name="calculator" /></span> Calculators
          </NavLink>
          {canLiveChat && (
            <NavLink to="/live" className="nav-link">
              <span className="nav-ic">💬</span> Live Chat
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/dashboard" className="nav-link">
              <span className="nav-ic"><Icon name="analytics" /></span> Analytics
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/knowledge" className="nav-link">
              <span className="nav-ic"><Icon name="knowledge" /></span> Knowledge
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/system" className="nav-link">
              <span className="nav-ic"><Icon name="health" /></span> System Health
            </NavLink>
          )}
          {isSuperAdmin && (
            <NavLink to="/platform" className="nav-link">
              <span className="nav-ic"><Icon name="platform" /></span> Platform
            </NavLink>
          )}
          {isAdmin && (
            <NavLink to="/admin" className="nav-link">
              <span className="nav-ic"><Icon name="admin" /></span> Admin
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
          <button className="btn btn-ghost btn-block signout-btn" onClick={handleLogout}>
            <Icon name="signout" size={15} /> Sign out
          </button>
        </div>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
