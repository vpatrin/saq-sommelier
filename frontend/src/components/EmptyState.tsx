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
    <div className="flex flex-col items-center justify-center gap-4 px-4 py-16 text-center">
      <div className="text-muted-foreground flex h-14 w-14 items-center justify-center rounded-xl border border-white/[0.06] bg-white/[0.04]">
        {icon}
      </div>
      <div className="flex max-w-xs flex-col gap-1.5">
        <p className="text-foreground text-[15px] font-medium">{title}</p>
        {description && (
          <p className="text-muted-foreground text-[13px] leading-relaxed font-light">
            {description}
          </p>
        )}
      </div>
      {(cta || secondaryCta) && (
        <div className="mt-1 flex gap-3">
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
