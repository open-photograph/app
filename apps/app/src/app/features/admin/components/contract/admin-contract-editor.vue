<script setup lang="ts">
import { contractEditorToolbar } from '../../constants/contract'

withDefaults(defineProps<{ readonly?: boolean }>(), { readonly: false })
const content = defineModel<string>({ required: true })
</script>

<template>
  <UEditor
    :key="String(readonly)"
    v-slot="{ editor }"
    v-model="content"
    content-type="markdown"
    :starter-kit="{ link: { autolink: false, linkOnPaste: false } }"
    :editable="!readonly"
    :image="false"
    placeholder="Escreva as cláusulas do contrato…"
    class="w-full"
    :ui="{ base: 'min-h-96 px-5 py-6 sm:px-8', content: 'w-full' }"
  >
    <UEditorToolbar
      v-if="!readonly"
      :editor="editor"
      :items="contractEditorToolbar"
      class="flex-wrap border-b border-default p-2"
    />
  </UEditor>
</template>
