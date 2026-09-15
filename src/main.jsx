import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
// Display serif (wordmark, year readout) and a mono for tabular data — years, counts,
// coordinates. An atlas reads as an instrument when its numbers line up.
import '@fontsource-variable/newsreader'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
