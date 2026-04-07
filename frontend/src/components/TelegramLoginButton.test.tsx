import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TelegramLoginButton } from './TelegramLoginButton'

describe('TelegramLoginButton', () => {
  it('appends Telegram widget script to container', () => {
    const { container } = render(<TelegramLoginButton botUsername="CoupetteBot" onAuth={vi.fn()} />)
    const script = container.querySelector('script')
    expect(script).toBeInTheDocument()
    expect(script?.src).toContain('telegram.org/js/telegram-widget.js')
    expect(script?.getAttribute('data-telegram-login')).toBe('CoupetteBot')
    expect(script?.getAttribute('data-size')).toBe('large')
  })

  it('sets data-lang on the script when lang prop is provided', () => {
    const { container } = render(
      <TelegramLoginButton botUsername="CoupetteBot" onAuth={vi.fn()} lang="fr" />,
    )
    const script = container.querySelector('script')
    expect(script?.getAttribute('data-lang')).toBe('fr')
  })

  it('registers __telegram_login_callback on window', () => {
    render(<TelegramLoginButton botUsername="CoupetteBot" onAuth={vi.fn()} />)
    expect(
      (window as unknown as Record<string, unknown>)['__telegram_login_callback'],
    ).toBeDefined()
  })

  it('removes __telegram_login_callback from window on unmount', () => {
    const { unmount } = render(<TelegramLoginButton botUsername="CoupetteBot" onAuth={vi.fn()} />)
    unmount()
    expect(
      (window as unknown as Record<string, unknown>)['__telegram_login_callback'],
    ).toBeUndefined()
  })
})
