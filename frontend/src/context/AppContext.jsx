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
  const [role, setRole] = useState('Contract Manager');
  const [contractId, setContractId] = useState(() => localStorage.getItem('contractId') || '');

  const updateContractId = (id) => {
    setContractId(id);
    localStorage.setItem('contractId', id);
  };

  return (
    <AppContext.Provider value={{ role, setRole, contractId, setContractId: updateContractId }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
