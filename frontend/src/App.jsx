import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import AnalysisPage from './pages/AnalysisPage';
import UploadContractPage from './pages/UploadContractPage';
import ProjectsPage from './pages/ProjectsPage';
import MprHistoryPage from './pages/MprHistoryPage';
import EscalationsPage from './pages/EscalationsPage';
import ReportsPage from './pages/ReportsPage';
import AdminPage from './pages/AdminPage';
import './index.css';

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <div className="app-container">
          <Sidebar />
          <main className="main-content">
            <Routes>
              <Route path="/"                 element={<Dashboard />} />
              <Route path="/projects"         element={<ProjectsPage />} />
              <Route path="/history"          element={<MprHistoryPage />} />
              <Route path="/analysis"         element={<AnalysisPage />} />
              <Route path="/upload-contract"  element={<UploadContractPage />} />
              <Route path="/escalations"      element={<EscalationsPage />} />
              <Route path="/reports"          element={<ReportsPage />} />
              <Route path="/admin"            element={<AdminPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
