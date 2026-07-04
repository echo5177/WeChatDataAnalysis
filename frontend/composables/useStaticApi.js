import { useApi } from '~/composables/useApi'
import { useApiBase } from '~/composables/useApiBase'

// Static-archive API. Wraps the normal chat API but redirects message loading to
// the static archive (`/api/static/*`) so the existing chat composables/components
// can render archived records without any changes.
export const useStaticApi = () => {
  const baseURL = useApiBase()
  const baseApi = useApi()

  const request = async (url, options = {}) => {
    return await $fetch(url, { baseURL, ...options })
  }

  // Drop-in replacement for api.listChatMessages used by useChatMessages.
  // Mirrors the /api/chat/messages response shape ({ messages, total, hasMore }).
  const listChatMessages = async (params = {}) => {
    const query = new URLSearchParams()
    if (params && params.account) query.set('account', params.account)
    if (params && params.username) query.set('username', params.username)
    if (params && params.limit != null) query.set('limit', String(params.limit))
    if (params && params.offset != null) query.set('offset', String(params.offset))
    if (params && params.order) query.set('order', params.order)
    const url = '/static/messages' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const listStaticConversations = async (params = {}) => {
    const query = new URLSearchParams()
    if (params && params.account) query.set('account', params.account)
    const url = '/static/conversations' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const getStaticCheckpoint = async (params = {}) => {
    const query = new URLSearchParams()
    if (params && params.account) query.set('account', params.account)
    if (params && params.username) query.set('username', params.username)
    const url = '/static/checkpoint' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const importStaticConversation = async (payload = {}) => {
    return await request('/static/import', {
      method: 'POST',
      body: {
        account: payload.account || null,
        username: payload.username,
        name: payload.name || null,
        is_group: payload.is_group == null ? null : !!payload.is_group,
        mode: payload.mode || 'auto',
        max_messages: payload.max_messages == null ? 0 : Number(payload.max_messages)
      }
    })
  }

  const getStaticAiConfig = async () => {
    return await request('/static/ai/config')
  }

  const getStaticAiModels = async () => {
    return await request('/static/ai/models')
  }

  const analyzeStaticConversation = async (payload = {}) => {
    return await request('/static/ai/analyze', {
      method: 'POST',
      body: {
        account: payload.account || null,
        username: payload.username,
        kind: payload.kind || 'summary',
        model: payload.model || null,
        start_time: payload.start_time == null ? null : Number(payload.start_time),
        end_time: payload.end_time == null ? null : Number(payload.end_time),
        max_messages: payload.max_messages == null ? 500 : Number(payload.max_messages)
      }
    })
  }

  const listStaticAiArtifacts = async (params = {}) => {
    const query = new URLSearchParams()
    if (params && params.account) query.set('account', params.account)
    if (params && params.username) query.set('username', params.username)
    if (params && params.kind) query.set('kind', params.kind)
    const url = '/static/ai/artifacts' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  // Expose the full base API plus the archive-backed overrides.
  return {
    ...baseApi,
    listChatMessages,
    listStaticConversations,
    getStaticCheckpoint,
    importStaticConversation,
    getStaticAiConfig,
    getStaticAiModels,
    analyzeStaticConversation,
    listStaticAiArtifacts
  }
}
