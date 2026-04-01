import { Button } from '@/components/ui/button'

interface EmptyStateProps {
  icon: React.ReactNode
  title: string
  description?: string
  cta?: { label: string; onClick: () => void }
  secondaryCta?: { label: string; onClick: () => void }
}

function EmptyState({ icon, title, description, cta, secondaryCta }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-4 gap-4">
      <div className="w-14 h-14 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-muted-foreground">
        {icon}
      </div>
      <div className="flex flex-col gap-1.5 max-w-xs">
        <p className="text-[15px] font-medium text-foreground">{title}</p>
        {description && (
          <p className="text-[13px] font-light text-muted-foreground leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {(cta || secondaryCta) && (
        <div className="flex gap-3 mt-1">
          {cta && (
            <Button size="sm" onClick={cta.onClick}>
              {cta.label}
            </Button>
          )}
          {secondaryCta && (
            <Button variant="outline" size="sm" onClick={secondaryCta.onClick}>
              {secondaryCta.label}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

export default EmptyState
