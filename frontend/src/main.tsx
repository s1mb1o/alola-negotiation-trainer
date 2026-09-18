import '@fontsource-variable/manrope'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { applyTheme, applyUiLanguage, initialTheme, initialUiLanguage } from './preferences'
import './styles.css'

applyUiLanguage(initialUiLanguage())
applyTheme(initialTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
