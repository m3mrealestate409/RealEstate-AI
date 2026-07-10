import { createContext, useContext, useState } from "react";
import { api, clearSession, getUser, setSession } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getUser());

  async function login(email, password) {
    const res = await api.login(email, password);
    const u = {
      email, name: res.name, role: res.role,
      is_super_admin: res.is_super_admin, organization_id: res.organization_id,
    };
    setSession(res.access_token, u);
    setUser(u);
    return u;
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
