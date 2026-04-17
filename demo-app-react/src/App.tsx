import { useCallback, useState } from 'react'
import { HashRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import AppNav from '@/components/layout/AppNav'
import LabTabs from '@/components/layout/LabTabs'
import LabHero from '@/components/layout/LabHero'
import ArchitecturePage from '@/pages/ArchitecturePage'
import Lab1RiskScoring from '@/labs/Lab1RiskScoring'
import Lab2Signing from '@/labs/Lab2Signing'
import Lab3AuditChain from '@/labs/Lab3AuditChain'
import Lab4Composition from '@/labs/Lab4Composition'
import Lab5Loaders from '@/labs/Lab5Loaders'
import Lab6CustomGates from '@/labs/Lab6CustomGates'
import Lab7Compliance from '@/labs/Lab7Compliance'
import Lab8GovernedKnowledgeBase from '@/labs/Lab8GovernedKnowledgeBase'
import Lab9GovernedVsUngoverned from '@/labs/Lab9GovernedVsUngoverned'
import Lab10SplitEnforcementExplorer from '@/labs/Lab10SplitEnforcementExplorer'
import Lab11WorkflowLab from '@/labs/Lab11WorkflowLab'
import HelpButton from '@/components/HelpButton'
import HelpDrawer from '@/components/HelpDrawer'

const LABS = [
  { num: 1,  title: 'Risk Scoring',            short: 'Risk'    },
  { num: 2,  title: 'Signing',                 short: 'Sign'    },
  { num: 3,  title: 'Audit Chain',             short: 'Chain'   },
  { num: 4,  title: 'Composition',             short: 'Compose' },
  { num: 5,  title: 'Loaders',                 short: 'Loaders' },
  { num: 6,  title: 'Custom Gates',            short: 'Gates'   },
  { num: 7,  title: 'Compliance',              short: 'Comply'  },
  { num: 8,  title: 'Knowledge Base',          short: 'KB'      },
  { num: 9,  title: 'Governed vs Ungoverned',  short: 'Compare' },
  { num: 10, title: 'Split Enforcement',       short: 'Split'   },
  { num: 11, title: 'Workflow Lab (v0.9.0 Beta)', short: 'Workflow' },
]

function AppContent() {
  const location = useLocation()
  const [isHelpOpen, setIsHelpOpen] = useState(false)

  const match = location.pathname.match(/\/lab\/(\d+)/)
  const activeLabId = location.pathname === '/architecture' ? 0 : (match ? parseInt(match[1], 10) : 1)

  const handleOpen = useCallback(() => setIsHelpOpen(true), [])
  const handleClose = useCallback(() => setIsHelpOpen(false), [])

  return (
    <div className="min-h-screen flex flex-col bg-base text-text-1">
      <AppNav />
      <LabTabs labs={LABS} />
      <Routes>
        <Route path="/" element={<Navigate to="/architecture" replace />} />
        <Route path="/architecture" element={<ArchitecturePage />} />
        <Route path="/lab/1" element={<><LabHero labNum={1} title="Risk Scoring" /><Lab1RiskScoring /></>} />
        <Route path="/lab/2" element={<><LabHero labNum={2} title="Signing & Verification" /><Lab2Signing /></>} />
        <Route path="/lab/3" element={<><LabHero labNum={3} title="Audit Chain" /><Lab3AuditChain /></>} />
        <Route path="/lab/4" element={<><LabHero labNum={4} title="Policy Composition" /><Lab4Composition /></>} />
        <Route path="/lab/5" element={<><LabHero labNum={5} title="Loaders & Versioning" /><Lab5Loaders /></>} />
        <Route path="/lab/6" element={<><LabHero labNum={6} title="Custom Gates" /><Lab6CustomGates /></>} />
        <Route path="/lab/7" element={<><LabHero labNum={7} title="Compliance Dashboard" /><Lab7Compliance /></>} />
        <Route path="/lab/8"  element={<><LabHero labNum={8}  title="Governed Knowledge Base"   /><Lab8GovernedKnowledgeBase /></>} />
        <Route path="/lab/9"  element={<><LabHero labNum={9}  title="Governed vs. Ungoverned"   /><Lab9GovernedVsUngoverned /></>} />
        <Route path="/lab/10" element={<><LabHero labNum={10} title="Split Enforcement Explorer"/><Lab10SplitEnforcementExplorer /></>} />
        <Route path="/lab/11" element={<><LabHero labNum={11} title="Workflow Governance (v0.9.0 Beta)" /><Lab11WorkflowLab /></>} />
      </Routes>
      <HelpButton isOpen={isHelpOpen} onOpen={handleOpen} />
      <HelpDrawer
        labId={activeLabId}
        isOpen={isHelpOpen}
        onClose={handleClose}
      />
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <AppContent />
    </HashRouter>
  )
}

export { LABS }
