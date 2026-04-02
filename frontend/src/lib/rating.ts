// MW non-linear rating table — /100 + /5, no /20 (doesn't map linearly onto Parker scale).
export const BUCKETS: {
  min: number
  max: number
  stars: string
  description: string
  color: string
}[] = [
  {
    min: 0,
    max: 59,
    stars: '★1.0–1.4',
    description: 'Défaut technique évident. On repose le verre.',
    color: 'text-red-400',
  },
  {
    min: 60,
    max: 69,
    stars: '★1.5–1.9',
    description: 'Vin propre mais plat. On boit par politesse.',
    color: 'text-red-400',
  },
  {
    min: 70,
    max: 79,
    stars: '★2.0–2.9',
    description: 'Vin de soif, de passable à honnête.',
    color: 'text-orange-400',
  },
  {
    min: 80,
    max: 84,
    stars: '★3.0–3.4',
    description: "Vin avec du caractère. On en achète à l'occasion.",
    color: 'text-amber-400',
  },
  {
    min: 85,
    max: 89,
    stars: '★3.5–3.9',
    description: 'Vraie qualité, personnalité affirmée. La cave commence ici.',
    color: 'text-amber-400',
  },
  {
    min: 90,
    max: 93,
    stars: '★4.0–4.2',
    description: 'Grand vin, complexe et profond. Pour les belles occasions.',
    color: 'text-lime-400',
  },
  {
    min: 94,
    max: 96,
    stars: '★4.3–4.5',
    description: 'Exceptionnel. On fait des km pour le retrouver.',
    color: 'text-green-400',
  },
  {
    min: 97,
    max: 99,
    stars: '★4.6–4.9',
    description: "Bouleversant. On ne l'ouvre pas sans la bonne personne.",
    color: 'text-green-400',
  },
  {
    min: 100,
    max: 100,
    stars: '★5.0',
    description: 'Perfection technique et émotion absolue.',
    color: 'text-green-400',
  },
]

export function ratingColor(rating: number): string {
  if (rating >= 97) return '#4ade80'
  if (rating >= 90) return '#a3e635'
  if (rating >= 80) return '#fbbf24'
  if (rating >= 70) return '#fb923c'
  return '#f87171'
}

export function getBucket(rating: number) {
  return BUCKETS.find((b) => rating >= b.min && rating <= b.max) ?? BUCKETS[0]
}
