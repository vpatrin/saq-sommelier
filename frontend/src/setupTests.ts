import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import i18n from './i18n'

// Pin locale so text-based assertions don't depend on jsdom's navigator.language
i18n.changeLanguage('en')

// RTL auto-cleanup needs a global afterEach — wire it explicitly since globals: false
afterEach(cleanup)
