import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { BrandMark } from "./Logo.jsx";
import Icon from "./Icons.jsx";

// Platform-owner alerts. Lives in the shell rather than on the Platform page,
// because the whole point is to be seen from wherever you happen to be — a
// tenant asking to change plan is money waiting on you.
function AlertsBell() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const load = () => api.saRequests().then(setRows).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  // Click-away, so the panel doesn't sit there once you've moved on.
  useEffect(() => {
    if (!open) return;
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const n = rows.length;
  return (
    <div className="bell-wrap" ref={box}>
      <button className="bell-btn" onClick={() => setOpen((o) => !o)}
        aria-label={n ? `${n} alerts` : "Alerts"} title={n ? `${n} waiting` : "No alerts"}>
        <Icon name="bell" size={18} />
        {n > 0 && <span className="bell-dot">{n > 9 ? "9+" : n}</span>}
      </button>

      {open && (
        <div className="bell-pop">
          <div className="bell-pop-head">Alerts{n > 0 && ` · ${n}`}</div>
          {n === 0 ? (
            <div className="bell-empty">Nothing waiting. Plan-change requests show up here.</div>
          ) : (
            rows.map((r) => (
              <button key={r.organization_id} className="bell-item"
                onClick={() => { setOpen(false); navigate("/platform"); }}>
                <div><b>{r.name}</b> wants <b>{r.requested_plan}</b></div>
                <div className="muted small">
                  from {r.current_plan || "—"}
                  {r.requested_at ? ` · ${new Date(r.requested_at).toLocaleDateString()}` : ""}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

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
          <div className="brand-text">
            <div className="brand-name">PropX Estate</div>
            <div className="brand-sub">Knowledge Guru</div>
          </div>
          {isSuperAdmin && <AlertsBell />}
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
