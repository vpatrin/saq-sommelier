import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'

// RTL auto-cleanup needs a global afterEach — wire it explicitly since globals: false
afterEach(cleanup)
