import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import { useAuth } from "./auth/AuthContext.jsx";
import Login from "./pages/Login.jsx";
import Query from "./pages/Query.jsx";
import Projects from "./pages/Projects.jsx";
import ProjectDetail from "./pages/ProjectDetail.jsx";
import Calculators from "./pages/Calculators.jsx";
import Admin from "./pages/Admin.jsx";
import LiveChat from "./pages/LiveChat.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Knowledge from "./pages/Knowledge.jsx";
import Billing from "./pages/Billing.jsx";
import Platform from "./pages/Platform.jsx";

function Protected({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Query />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:id" element={<ProjectDetail />} />
        <Route path="calculators" element={<Calculators />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="knowledge" element={<Knowledge />} />
        {/* System Health moved into Admin → System; billing came the other way. */}
        <Route path="system" element={<Navigate to="/admin" replace />} />
        <Route path="billing" element={<Billing />} />
        <Route path="platform" element={<Platform />} />
        <Route path="live" element={<LiveChat />} />
        <Route path="admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
