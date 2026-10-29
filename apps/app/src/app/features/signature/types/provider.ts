export interface SignatureProvider {
  id: string
  name: string
  provider: string
  environment: 'sandbox' | 'production'
  is_active: boolean
}

export interface SignatureProviderDefinition {
  value: string
  label: string
  docs_url: string
}

export interface SignatureCatalog {
  providers: SignatureProviderDefinition[]
}
