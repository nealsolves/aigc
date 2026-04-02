import { createContext, useContext, useReducer, type ReactNode } from 'react'
import type { Artifact } from '@/types/artifact'

interface AigcState {
  apiUrl: string
  auditHistory: Artifact[]
}

type Action =
  | { type: 'ADD_AUDIT'; artifact: Artifact }
  | { type: 'CLEAR_HISTORY' }

function reducer(state: AigcState, action: Action): AigcState {
  switch (action.type) {
    case 'ADD_AUDIT':
      return { ...state, auditHistory: [...state.auditHistory, action.artifact] }
    case 'CLEAR_HISTORY':
      return { ...state, auditHistory: [] }
    default:
      return state
  }
}

interface AigcContextValue extends AigcState {
  addAudit: (artifact: Artifact) => void
  clearHistory: () => void
}

const AigcContext = createContext<AigcContextValue | null>(null)

export function AigcProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    apiUrl: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
    auditHistory: [],
  })

  return (
    <AigcContext.Provider value={{
      ...state,
      addAudit: (artifact) => dispatch({ type: 'ADD_AUDIT', artifact }),
      clearHistory: () => dispatch({ type: 'CLEAR_HISTORY' }),
    }}>
      {children}
    </AigcContext.Provider>
  )
}

export function useAigc(): AigcContextValue {
  const ctx = useContext(AigcContext)
  if (!ctx) throw new Error('useAigc must be used within AigcProvider')
  return ctx
}
