import { useApi } from '~/composables/useApi'
import { useApiBase } from '~/composables/useApiBase'

// Static-archive API. Wraps the normal chat API but redirects message loading to
// the static archive (`/api/static/*`) so the existing chat composables/components
// can render archived records without any changes.
export const useStaticApi = () => {
  const baseURL = useApiBase()
  const baseApi = useApi()

  // Default 30s timeout so an unresponsive/dead backend surfaces as an error
  // instead of hanging the UI forever. Long operations pass a larger timeout.
  const request = async (url, options = {}) => {
    try {
      return await $fetch(url, { baseURL, timeout: 30000, ...options })
    } catch (e) {
      if (e?.name === 'AbortError' || /aborted|timeout/i.test(String(e?.message || ''))) {
        throw new Error('请求超时，请确认后端(dev 服务)是否在运行')
      }
      throw e
    }
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
      // full import of a huge group can take minutes; caller may override.
      timeout: payload.timeout == null ? 300000 : Number(payload.timeout),
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

  const listStaticAiMembers = async (params = {}) => {
    const query = new URLSearchParams()
    if (params && params.account) query.set('account', params.account)
    if (params && params.username) query.set('username', params.username)
    if (params && params.start_time != null) query.set('start_time', String(params.start_time))
    if (params && params.end_time != null) query.set('end_time', String(params.end_time))
    const url = '/static/ai/members' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const listStaticPersonMessages = async (params = {}) => {
    const query = new URLSearchParams()
    if (params.account) query.set('account', params.account)
    if (params.username) query.set('username', params.username)
    if (params.target_user != null) query.set('target_user', params.target_user)
    if (params.is_self) query.set('is_self', 'true')
    if (params.start_time != null) query.set('start_time', String(params.start_time))
    if (params.end_time != null) query.set('end_time', String(params.end_time))
    if (params.limit != null) query.set('limit', String(params.limit))
    const url = '/static/ai/person_messages' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const listStaticPersons = async (params = {}) => {
    const query = new URLSearchParams()
    if (params.account) query.set('account', params.account)
    if (params.start_time != null) query.set('start_time', String(params.start_time))
    if (params.end_time != null) query.set('end_time', String(params.end_time))
    if (params.top != null) query.set('top', String(params.top))
    const url = '/static/persons' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const listStaticPersonGlobalMessages = async (params = {}) => {
    const query = new URLSearchParams()
    if (params.account) query.set('account', params.account)
    if (params.target_user != null) query.set('target_user', params.target_user)
    if (params.start_time != null) query.set('start_time', String(params.start_time))
    if (params.end_time != null) query.set('end_time', String(params.end_time))
    if (params.limit != null) query.set('limit', String(params.limit))
    const url = '/static/persons/messages' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const listStaticAiChats = async (params = {}) => {
    const query = new URLSearchParams()
    if (params && params.account) query.set('account', params.account)
    if (params && params.username) query.set('username', params.username)
    if (params && params.kind) query.set('kind', params.kind)
    if (params && params.target_user != null) query.set('target_user', params.target_user)
    const url = '/static/ai/chats' + (query.toString() ? `?${query.toString()}` : '')
    return await request(url)
  }

  const createStaticAiChat = async (payload = {}) => {
    return await request('/static/ai/chats', {
      method: 'POST',
      body: {
        account: payload.account || null,
        username: payload.username,
        kind: payload.kind || 'summary',
        target_user: payload.target_user || '',
        target_name: payload.target_name || '',
        title: payload.title || '',
        start_time: payload.start_time == null ? null : Number(payload.start_time),
        end_time: payload.end_time == null ? null : Number(payload.end_time)
      }
    })
  }

  const getStaticAiChat = async (chatId) => {
    return await request(`/static/ai/chats/${encodeURIComponent(String(chatId))}`)
  }

  const deleteStaticAiChat = async (chatId) => {
    return await request(`/static/ai/chats/${encodeURIComponent(String(chatId))}`, { method: 'DELETE' })
  }

  const sendStaticAiChat = async (chatId, payload = {}) => {
    return await request(`/static/ai/chats/${encodeURIComponent(String(chatId))}/send`, {
      method: 'POST',
      timeout: 300000,
      body: { content: payload.content, model: payload.model || null }
    })
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
    listStaticAiArtifacts,
    listStaticAiMembers,
    listStaticPersonMessages,
    listStaticPersons,
    listStaticPersonGlobalMessages,
    listStaticAiChats,
    createStaticAiChat,
    getStaticAiChat,
    deleteStaticAiChat,
    sendStaticAiChat
  }
}
