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
  const [role, setRole] = useState('Project Manager');
  const [contractId, setContractId] = useState('');

  return (
    <AppContext.Provider value={{ role, setRole, contractId, setContractId }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
