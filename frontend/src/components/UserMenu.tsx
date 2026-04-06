import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { UserRole } from '@/lib/types'
import {
  HeartIcon as Heart,
  GearIcon as Gear,
  SignOutIcon,
  TerminalIcon as Terminal,
} from '@phosphor-icons/react'

interface UserMenuProps {
  displayName: string | null
  role?: UserRole
  onLogout: () => void
  onNavigate?: (to: string) => void
  placement?: 'above' | 'right'
}

function UserMenu({ displayName, role, onLogout, onNavigate, placement = 'above' }: UserMenuProps) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={ref}
      className={`bg-popover border-border absolute z-50 overflow-hidden rounded-xl border shadow-xl ${
        placement === 'right' ? 'bottom-0 left-full ml-2 w-64' : 'right-3 bottom-full left-3 mb-2'
      }`}
    >
      <div className="border-border flex items-center gap-3 border-b px-4 py-3.5">
        <div className="bg-primary/15 border-primary/20 text-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-[13px] font-medium">
          {displayName?.charAt(0) ?? '?'}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium">
            {displayName ?? t('userMenu.anonymous')}
          </p>
        </div>
      </div>

      <div className="border-border/50 border-b py-1">
        <div className="flex cursor-not-allowed items-center gap-3 px-4 py-2.5 opacity-40">
          <Heart size={15} className="text-muted-foreground shrink-0" />
          <span className="text-muted-foreground flex-1 text-[13px]">
            {t('userMenu.monPalais')}
          </span>
          <span className="border-primary/20 bg-primary/10 text-primary rounded border px-1.5 py-0.5 font-mono text-[9px]">
            {t('userMenu.soon')}
          </span>
        </div>
      </div>

      <div className="border-border/50 border-b py-1">
        <button
          type="button"
          onClick={() => onNavigate?.('/settings')}
          className="flex w-full items-center gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.04]"
        >
          <Gear size={15} className="text-muted-foreground shrink-0" />
          <span className="text-muted-foreground text-[13px]">{t('userMenu.settings')}</span>
        </button>
      </div>

      {role === 'admin' && (
        <div className="border-border/50 border-b py-1">
          <button
            type="button"
            onClick={() => onNavigate?.('/admin')}
            className="flex w-full items-center gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.04]"
          >
            <Terminal size={15} className="text-muted-foreground shrink-0" />
            <span className="text-muted-foreground text-[13px]">{t('nav.admin')}</span>
          </button>
        </div>
      )}

      <div className="py-1">
        <button
          type="button"
          onClick={onLogout}
          className="hover:bg-destructive/[0.06] flex w-full items-center gap-3 px-4 py-2.5 transition-colors"
        >
          <SignOutIcon size={15} className="text-destructive/70 shrink-0" />
          <span className="text-destructive text-[13px]">{t('userMenu.logout')}</span>
        </button>
      </div>
    </div>
  )
}

export default UserMenu
