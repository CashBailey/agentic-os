import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { Dashboard } from './routes/Dashboard';
import { Context } from './routes/Context';
import { Memory } from './routes/Memory';
import { Adapters } from './routes/Adapters';
import { Policies } from './routes/Policies';
import { Skills } from './routes/Skills';
import { Approvals } from './routes/Approvals';
import { Audit } from './routes/Audit';

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/context" element={<Context />} />
        <Route path="/memory" element={<Memory />} />
        <Route path="/adapters" element={<Adapters />} />
        <Route path="/policies" element={<Policies />} />
        <Route path="/skills" element={<Skills />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
