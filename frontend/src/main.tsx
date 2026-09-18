import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { CommunicationDialogProvider } from './CommunicationContent'
import { fetchRuntimeConfig } from './api'
import { setBusinessNow } from './dateTime'

async function boot() {
  try {
    const runtime = await fetchRuntimeConfig()
    setBusinessNow(runtime.current_business_datetime)
  } catch {
    // Без API остаётся живое время браузера — как в обычном production.
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <CommunicationDialogProvider>
        <App />
      </CommunicationDialogProvider>
    </StrictMode>,
  )
}

void boot()
