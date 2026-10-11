import React, { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);

// Admin credentials — change these to whatever you want
const ADMIN_EMAIL    = 'admin@loanrisk.ai';
const ADMIN_PASSWORD = 'Admin@1234';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('loanAgentUser');
    return saved ? JSON.parse(saved) : null;
  });

  /**
   * Returns 'admin' | 'user' | null depending on credentials.
   * Call this from the Login page to know where to redirect.
   */
  const login = (email, password, name = '') => {
    if (email === ADMIN_EMAIL && password === ADMIN_PASSWORD) {
      const adminData = { email, name: 'Admin', role: 'admin' };
      localStorage.setItem('loanAgentUser', JSON.stringify(adminData));
      setUser(adminData);
      return 'admin';
    }
    // Regular user — any email + password ≥ 6 chars
    // user_id is the email so it matches what's stored in MongoDB decisions
    const userData = { email, name: name || email.split('@')[0], role: 'user', user_id: email };
    localStorage.setItem('loanAgentUser', JSON.stringify(userData));
    setUser(userData);
    return 'user';
  };

  const logout = () => {
    localStorage.removeItem('loanAgentUser');
    setUser(null);
  };

  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
