import React, { createContext, useContext, useState } from 'react';

const AppContext = createContext(null);

export const ROLES = [
  'Contract Manager',
  'Project Manager',
  'Site Engineer',
  'Auditor',
  'Contractor Rep',
];

export function AppProvider({ children }) {
  const [role, setRole] = useState(() => localStorage.getItem('role') || 'Contract Manager');
  const [contractId, setContractId] = useState(() => localStorage.getItem('contractId') || '');

  const updateContractId = (id) => {
    setContractId(id);
    localStorage.setItem('contractId', id);
  };

  const updateRole = (r) => {
    setRole(r);
    localStorage.setItem('role', r);
  };

  return (
    <AppContext.Provider value={{ role, setRole: updateRole, contractId, setContractId: updateContractId }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
