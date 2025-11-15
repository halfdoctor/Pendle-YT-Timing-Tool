import { useState } from 'react'
import { Main } from './components/Main'
import { MarketAnalysis } from './components/MarketAnalysis'
import Header from './components/Header'
import { ThemeProvider } from "@/components/ThemeProvider"

export type TabType = 'main' | 'analysis'

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('main')

  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <div className="min-h-screen">
        <Header activeTab={activeTab} onTabChange={setActiveTab} />
        <main>
          {activeTab === 'main' && <Main />}
          {activeTab === 'analysis' && <MarketAnalysis />}
        </main>
      </div>
    </ThemeProvider>
  )
}

export default App
