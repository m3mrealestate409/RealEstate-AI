import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import { useAuth } from "./auth/AuthContext.jsx";
import Login from "./pages/Login.jsx";
import Query from "./pages/Query.jsx";
import Projects from "./pages/Projects.jsx";
import ProjectDetail from "./pages/ProjectDetail.jsx";
import Calculators from "./pages/Calculators.jsx";
import Admin from "./pages/Admin.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Knowledge from "./pages/Knowledge.jsx";
import SystemHealth from "./pages/SystemHealth.jsx";
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
        <Route path="system" element={<SystemHealth />} />
        <Route path="platform" element={<Platform />} />
        <Route path="admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
