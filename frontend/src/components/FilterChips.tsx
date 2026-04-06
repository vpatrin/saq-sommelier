interface FilterChipOption {
  label: string
  value: string
}

interface FilterChipsProps {
  options: FilterChipOption[]
  value: string
  onChange: (value: string) => void
}

function FilterChips({ options, value, onChange }: FilterChipsProps) {
  return (
    <div className="flex flex-wrap gap-1.5 overflow-x-auto">
      {options.map((opt) => {
        const isActive = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(isActive ? '' : opt.value)}
            className={`rounded-full border px-3 py-1 text-[12px] whitespace-nowrap transition-colors ${
              isActive
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80'
            }`}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export default FilterChips
