import type { EditorToolbarItem } from '@nuxt/ui'
import type { ContractStatus } from '../types/contract/contract'

export const contractStatusLabels: Record<ContractStatus, string> = {
  draft: 'Rascunho',
  generating: 'Gerando link',
  pending: 'Aguardando assinatura',
  signed: 'Assinado',
  uncertain: 'Verificar no provider',
}

export const contractEditorToolbar: EditorToolbarItem[][] = [
  [
    { kind: 'undo', icon: 'i-lucide-undo', tooltip: { text: 'Desfazer' } },
    { kind: 'redo', icon: 'i-lucide-redo', tooltip: { text: 'Refazer' } },
  ],
  [
    { kind: 'heading', level: 1, icon: 'i-lucide-heading-1' },
    { kind: 'heading', level: 2, icon: 'i-lucide-heading-2' },
  ],
  [
    { kind: 'mark', mark: 'bold', icon: 'i-lucide-bold', tooltip: { text: 'Negrito' } },
    { kind: 'mark', mark: 'italic', icon: 'i-lucide-italic', tooltip: { text: 'Itálico' } },
  ],
  [
    { kind: 'bulletList', icon: 'i-lucide-list' },
    { kind: 'orderedList', icon: 'i-lucide-list-ordered' },
  ],
]
