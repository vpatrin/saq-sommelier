import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  HeartIcon as Heart,
  GearIcon as Gear,
  GlobeIcon as Globe,
  SignOutIcon,
} from '@phosphor-icons/react'

interface UserMenuProps {
  firstName: string
  onLogout: () => void
  currentLanguage: string
  onLanguageChange: (lang: string) => void
  placement?: 'above' | 'right'
}

function UserMenu({
  firstName,
  onLogout,
  currentLanguage,
  onLanguageChange,
  placement = 'above',
}: UserMenuProps) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)

  const nextLang = currentLanguage === 'fr' ? 'en' : 'fr'

  return (
    <div
      ref={ref}
      className={`absolute z-50 rounded-xl bg-popover border border-border shadow-xl overflow-hidden ${
        placement === 'right' ? 'left-full bottom-0 ml-2 w-64' : 'bottom-full left-3 right-3 mb-2'
      }`}
    >
      <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
        <div className="w-9 h-9 rounded-full bg-primary/15 border border-primary/20 flex items-center justify-center text-[13px] font-medium text-primary shrink-0">
          {firstName.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium truncate">{firstName}</p>
          <p className="text-[11px] text-muted-foreground/50">
            {t('userMenu.connectedViaTelegram')}
          </p>
        </div>
      </div>

      <div className="py-1 border-b border-border/50">
        <div className="flex items-center gap-3 px-4 py-2.5 opacity-40 cursor-not-allowed">
          <Heart size={15} className="text-muted-foreground shrink-0" />
          <span className="text-[13px] text-muted-foreground flex-1">
            {t('userMenu.monPalais')}
          </span>
          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded border border-primary/20 bg-primary/10 text-primary">
            {t('userMenu.soon')}
          </span>
        </div>
      </div>

      <div className="py-1 border-b border-border/50">
        <div className="flex items-center gap-3 px-4 py-2.5 opacity-40 cursor-not-allowed">
          <Gear size={15} className="text-muted-foreground shrink-0" />
          <span className="text-[13px] text-muted-foreground">{t('userMenu.settings')}</span>
        </div>
        <button
          type="button"
          onClick={() => onLanguageChange(nextLang)}
          className="flex items-center gap-3 px-4 py-2.5 w-full hover:bg-white/[0.04] transition-colors"
        >
          <Globe size={15} className="text-muted-foreground shrink-0" />
          <span className="text-[13px] text-muted-foreground flex-1 text-left">
            {t('userMenu.language')}
          </span>
          <span className="font-mono text-[11px] text-muted-foreground/60 uppercase">
            {currentLanguage}
          </span>
        </button>
      </div>

      <div className="py-1">
        <button
          type="button"
          onClick={onLogout}
          className="flex items-center gap-3 px-4 py-2.5 w-full hover:bg-destructive/[0.06] transition-colors"
        >
          <SignOutIcon size={15} className="text-destructive/70 shrink-0" />
          <span className="text-[13px] text-destructive">{t('userMenu.logout')}</span>
        </button>
      </div>
    </div>
  )
}

export default UserMenu
