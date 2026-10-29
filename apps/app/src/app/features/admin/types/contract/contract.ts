export type ContractStatus = 'draft' | 'generating' | 'pending' | 'signed' | 'uncertain'

export interface Contract {
  id: string
  title: string
  template: string | null
  client: string
  client_name: string
  signature_provider: string
  provider_name: string
  provider_environment: 'sandbox' | 'production'
  content: string
  signer_name: string
  signer_email: string
  status: ContractStatus
  signing_url: string
  provider_document_id: string
  last_error: string
  last_synced_at: string | null
  signed_at: string | null
  created_at: string
  updated_at: string
}
