import { createContext, useCallback, useContext, useState } from 'react'
import type { ReactNode } from 'react'

interface WineDetailContextType {
  selectedSku: string | null
  setSelectedSku: (sku: string | null) => void
}

const WineDetailContext = createContext<WineDetailContextType | null>(null)

export function WineDetailProvider({ children }: { children: ReactNode }) {
  const [selectedSku, setSelectedSkuRaw] = useState<string | null>(null)
  const setSelectedSku = useCallback((sku: string | null) => setSelectedSkuRaw(sku), [])

  return (
    <WineDetailContext.Provider value={{ selectedSku, setSelectedSku }}>
      {children}
    </WineDetailContext.Provider>
  )
}

export function useWineDetail(): WineDetailContextType {
  const ctx = useContext(WineDetailContext)
  if (!ctx) throw new Error('useWineDetail must be used inside WineDetailProvider')
  return ctx
}
