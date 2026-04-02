import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider } from '@/theme/ThemeContext'
import { AigcProvider } from '@/context/AigcContext'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <AigcProvider>
        <App />
      </AigcProvider>
    </ThemeProvider>
  </StrictMode>,
)
