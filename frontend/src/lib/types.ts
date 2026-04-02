// API response types — mirrors backend Pydantic *Out schemas

// --- Chat ---

export interface ChatSessionOut {
  id: number
  title: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessageOut {
  message_id: number
  session_id: number
  role: 'user' | 'assistant'
  content: string | RecommendationOut
  created_at: string
}

export interface ChatSessionDetailOut extends ChatSessionOut {
  messages: ChatMessageOut[]
}

// --- Recommendations (inline in chat) ---

export interface IntentResult {
  is_wine: boolean
  categories: string[]
  min_price: string | null
  max_price: string | null
  country: string | null
  semantic_query: string
  exclude_grapes: string[]
}

export interface RecommendationProductOut {
  product: ProductOut
  reason: string
}

export interface RecommendationOut {
  products: RecommendationProductOut[]
  intent: IntentResult
  summary: string
  log_id: number | null
}

export interface ProductOut {
  sku: string
  name: string | null
  category: string | null
  country: string | null
  size: string | null
  price: string | null // Decimal serialized as string
  url: string | null
  online_availability: boolean | null
  store_availability: string[] | null
  rating: number | null
  review_count: number | null
  region: string | null
  appellation: string | null
  designation: string | null
  classification: string | null
  grape: string | null
  grape_blend: Record<string, unknown>[] | null
  alcohol: string | null
  sugar: string | null
  producer: string | null
  vintage: string | null
  taste_tag: string | null
  created_at: string
  updated_at: string
}

// --- Tasting Journal ---

export interface TastingNoteOut {
  id: number
  sku: string
  rating: number
  notes: string | null
  pairing: string | null
  tasted_at: string // ISO date YYYY-MM-DD
  created_at: string
  updated_at: string
  product_name: string | null
  product_image_url: string | null
}

export interface WatchOut {
  id: number
  user_id: string
  sku: string
  created_at: string
}

export interface WatchWithProduct {
  watch: WatchOut
  product: ProductOut | null
}

export interface StoreOut {
  saq_store_id: string
  name: string
  store_type: string | null
  address: string | null
  city: string
  postcode: string | null
  telephone: string | null
  latitude: number | null
  longitude: number | null
  temporarily_closed: boolean
}

export interface StoreWithDistance extends StoreOut {
  distance_km: number
}

export interface UserStorePreferenceOut {
  saq_store_id: string
  created_at: string
  store: StoreOut
}

export interface PaginatedOut {
  products: ProductOut[]
  total: number
  limit: number
  offset: number
}

export interface PriceRange {
  min: string // Decimal serialized as string
  max: string
}

export interface CategoryGroupOut {
  key: string
  label: string
  categories: string[]
}

export interface CategoryFamilyOut {
  key: string
  label: string
  children: string[] // group keys
}

export interface CountryFacet {
  name: string
  count: number
}

export interface FacetsOut {
  categories: string[]
  grouped_categories: CategoryGroupOut[]
  category_families: CategoryFamilyOut[]
  countries: CountryFacet[]
  regions: string[]
  grapes: string[]
  price_range: PriceRange | null
}
