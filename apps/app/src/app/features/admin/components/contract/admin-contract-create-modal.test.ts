import { expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import CreateModal from './admin-contract-create-modal.vue'

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('@/app/core/clients/api', () => ({ apiFetch: apiMock }))

const Input = defineComponent({
  name: 'InputStub',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<input />',
})
const SelectMenu = defineComponent({
  name: 'SelectMenuStub',
  props: ['modelValue', 'placeholder'],
  emits: ['update:modelValue'],
  template: '<div />',
})
const FormField = defineComponent({
  name: 'FieldStub',
  props: ['label'],
  template: '<label>{{ label }}<slot /></label>',
})
const Form = defineComponent({
  name: 'FormStub',
  emits: ['submit'],
  template: '<div><slot /></div>',
})

it('loads custom fields for the selected template, resets them on switching, and submits entered values', async () => {
  const first = {
    id: 'first',
    name: 'Ensaio',
    variables: ['name', 'valor'],
    input_variables: ['name', 'valor'],
  }
  const second = { id: 'second', name: 'Evento', variables: ['local'], input_variables: ['local'] }
  apiMock.mockReset()
  apiMock.mockImplementation(async (url: string, options?: { method?: string }) => {
    if (url === '/api/contract-templates/') return { results: [first, second] }
    if (url === '/api/contract-templates/first/') return first
    if (url === '/api/contract-templates/second/') return second
    if (url === '/api/clients/') return { results: [{ id: 'client', name: 'Ana' }] }
    if (url === '/api/contracts/' && options?.method === 'POST') return { id: 'contract' }
    throw new Error(`Unexpected API call: ${url}`)
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/admin/contracts/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = mount(CreateModal, {
    props: { open: true },
    global: {
      plugins: [router, [VueQueryPlugin, { queryClient }]],
      stubs: {
        Modal: { template: '<div><slot name="body" /><slot name="footer" /></div>' },
        Form,
        FormField,
        Input,
        SelectMenu,
        Button: true,
        Alert: true,
        Skeleton: true,
        Separator: true,
      },
    },
  })
  try {
    await flushPromises()
    const selectors = wrapper.findAllComponents(SelectMenu)
    selectors[0]!.vm.$emit('update:modelValue', 'client')
    selectors[1]!.vm.$emit('update:modelValue', 'first')
    await vi.waitFor(() =>
      expect(wrapper.findAllComponents(FormField).map((field) => field.props('label'))).toContain(
        'valor',
      ),
    )
    expect(wrapper.findAllComponents(FormField).map((field) => field.props('label'))).toContain(
      'name',
    )
    selectors[1]!.vm.$emit('update:modelValue', 'second')
    await vi.waitFor(() =>
      expect(wrapper.findAllComponents(FormField).map((field) => field.props('label'))).toContain(
        'local',
      ),
    )
    expect(wrapper.findAllComponents(FormField).map((field) => field.props('label'))).not.toContain(
      'name',
    )
    const inputs = wrapper.findAllComponents(Input)
    inputs[0]!.vm.$emit('update:modelValue', 'Contrato de evento')
    inputs[1]!.vm.$emit('update:modelValue', 'São Paulo')
    await flushPromises()
    wrapper.findComponent(Form).vm.$emit('submit')
    await vi.waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith('/api/contracts/', {
        method: 'POST',
        body: {
          title: 'Contrato de evento',
          client: 'client',
          template: 'second',
          variables: { local: 'São Paulo' },
        },
      }),
    )
  } finally {
    wrapper.unmount()
    queryClient.clear()
  }
})
