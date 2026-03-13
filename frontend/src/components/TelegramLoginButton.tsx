import { useEffect, useRef } from 'react'

export interface TelegramLoginData {
  id: number
  first_name: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

interface TelegramLoginButtonProps {
  botUsername: string
  onAuth: (data: TelegramLoginData) => void
}

export function TelegramLoginButton({ botUsername, onAuth }: TelegramLoginButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Telegram's widget calls this global function on successful auth
    const callbackName = '__telegram_login_callback'
    ;(window as unknown as Record<string, unknown>)[callbackName] = (data: TelegramLoginData) => {
      onAuth(data)
    }

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.async = true
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', `${callbackName}(user)`)
    script.setAttribute('data-request-access', 'write')

    const container = containerRef.current
    container?.appendChild(script)

    return () => {
      delete (window as unknown as Record<string, unknown>)[callbackName]
      if (container) {
        container.innerHTML = ''
      }
    }
  }, [botUsername, onAuth])

  return <div ref={containerRef} />
}
