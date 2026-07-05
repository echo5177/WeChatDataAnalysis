<template>
  <div class="static-chat-shell h-screen flex overflow-hidden">
    <!-- Left: archived conversation list -->
    <div class="static-session-panel flex flex-col border-r min-h-0">
      <div class="static-panel-header flex items-center justify-between px-3 h-[52px] border-b">
        <div class="text-sm font-medium">
          静态归档
          <span class="text-xs text-gray-400">({{ conversations.length }})</span>
        </div>
        <button
          type="button"
          class="static-btn text-xs px-2.5 py-1 rounded-md"
          @click="openPicker"
        >＋ 添加会话</button>
      </div>

      <div class="flex-1 overflow-y-auto min-h-0">
        <div v-if="conversationsLoading" class="text-center text-xs text-gray-400 py-6">加载中...</div>
        <div v-else-if="!conversations.length" class="text-center text-xs text-gray-400 py-10 px-4 leading-relaxed">
          还没有归档任何会话。<br />点击右上角「添加会话」，<br />从现有聊天中选择并导入。
        </div>
        <div
          v-for="c in conversations"
          :key="c.username"
          class="static-session-item flex items-center gap-2.5 px-3 py-2.5 cursor-pointer"
          :class="{ 'static-session-item-active': selectedContact && selectedContact.username === c.username }"
          @click="selectConversation(c)"
        >
          <div class="w-9 h-9 rounded-md overflow-hidden bg-gray-300 flex-shrink-0" :class="{ 'privacy-blur': privacyMode }">
            <img v-if="avatarUrl(c.username)" :src="avatarUrl(c.username)" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm truncate" :class="{ 'privacy-blur': privacyMode }">{{ c.name || c.username }}</div>
            <div class="text-[11px] text-gray-400 truncate">
              {{ c.messageCount }} 条 · {{ c.isGroup ? '群聊' : '单聊' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Center: conversation -->
    <div class="flex-1 flex flex-col min-h-0 min-w-0">
      <template v-if="selectedContact">
        <div class="chat-header">
          <h2 class="chat-header-title text-base font-medium" :class="{ 'privacy-blur': privacyMode }">
            {{ selectedContact.name }}
          </h2>
          <div class="ml-auto flex items-center gap-3">
            <span v-if="importStatus" class="text-xs text-gray-400" :class="{ 'cursor-help': importStatusTip }" :title="importStatusTip">{{ importStatus }}</span>
            <button
              type="button"
              class="static-btn text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5"
              :disabled="importing"
              title="从断点接续导入最新消息"
              @click="exportLatest"
            >
              <svg v-if="!importing" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {{ importing ? '同步中...' : '导出最新消息' }}
            </button>
            <button
              type="button"
              class="static-btn text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5"
              :class="{ 'static-btn-active': aiPanelOpen }"
              title="AI 分析"
              @click="toggleAiPanel"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
              </svg>
              AI 分析
            </button>
          </div>
        </div>

        <MessageList :state="staticState" />
      </template>

      <div v-else class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-[#03C160]/10 to-[#03C160]/5 flex items-center justify-center">
            <svg class="w-10 h-10 text-[#03C160]/60" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 19.8C17.52 19.8 22 15.99 22 11.3C22 6.6 17.52 2.8 12 2.8C6.48 2.8 2 6.6 2 11.3C2 13.29 2.8 15.12 4.15 16.57C4.6 17.05 4.82 17.29 4.92 17.44C5.14 17.79 5.21 17.99 5.23 18.4C5.24 18.59 5.22 18.81 5.16 19.26C5.1 19.75 5.07 19.99 5.13 20.16C5.23 20.49 5.53 20.71 5.87 20.72C6.04 20.72 6.27 20.63 6.72 20.43L8.07 19.86C8.43 19.71 8.61 19.63 8.77 19.59C8.95 19.55 9.04 19.54 9.22 19.54C9.39 19.53 9.64 19.57 10.14 19.65C10.74 19.75 11.37 19.8 12 19.8Z" />
            </svg>
          </div>
          <h3 class="text-base font-medium mb-1.5">静态聊天归档</h3>
          <p class="text-sm text-gray-400">从左侧选择一个已归档会话，或点击「添加会话」导入</p>
        </div>
      </div>
    </div>

    <!-- AI analysis panel (dedicated component: summary chatbot + user profiles) -->
    <StaticAiPanel
      v-if="aiPanelOpen && selectedContact"
      :account="selectedAccount"
      :conversation="selectedContact"
      :privacy-mode="privacyMode"
      @close="aiPanelOpen = false"
    />

    <!-- Image preview overlay -->
    <div
      v-if="previewImageUrl"
      class="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center"
      @click="closeImagePreview"
    >
      <img :src="previewImageUrl" class="max-w-[92vw] max-h-[92vh] object-contain" referrerpolicy="no-referrer" @click.stop />
    </div>

    <!-- Video preview overlay -->
    <div
      v-if="previewVideoUrl"
      class="fixed inset-0 z-[200] bg-black/85 flex items-center justify-center"
      @click="closeVideoPreview"
    >
      <video :src="previewVideoUrl" :poster="previewVideoPosterUrl || ''" controls autoplay class="max-w-[92vw] max-h-[92vh]" @click.stop />
    </div>

    <!-- Add-conversation picker -->
    <div
      v-if="pickerOpen"
      class="fixed inset-0 z-[210] flex items-center justify-center bg-black/35 px-4"
      @click.self="closePicker"
    >
      <div class="static-picker-panel w-full max-w-[460px] max-h-[76vh] rounded-[12px] overflow-hidden flex flex-col shadow-2xl">
        <div class="flex items-center justify-between px-4 h-[48px] border-b">
          <div class="text-sm font-medium">添加会话到归档</div>
          <button type="button" class="text-gray-400 hover:text-gray-700" @click="closePicker">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
        <div class="px-3 py-2 border-b">
          <input
            v-model="pickerQuery"
            type="text"
            placeholder="搜索会话名称..."
            class="static-picker-input w-full text-sm px-3 py-1.5 rounded-md"
          />
        </div>
        <div class="flex-1 overflow-y-auto min-h-0">
          <div v-if="pickerLoading" class="text-center text-xs text-gray-400 py-6">加载会话中...</div>
          <div v-else-if="pickerError" class="text-center text-xs text-red-500 py-6 px-4 whitespace-pre-wrap">{{ pickerError }}</div>
          <div v-else-if="!filteredLiveSessions.length" class="text-center text-xs text-gray-400 py-6">无匹配会话</div>
          <div
            v-for="s in filteredLiveSessions"
            :key="s.username"
            class="static-session-item flex items-center gap-2.5 px-3 py-2.5 cursor-pointer"
            @click="importSession(s)"
          >
            <div class="w-9 h-9 rounded-md overflow-hidden bg-gray-300 flex-shrink-0">
              <img v-if="s.avatar" :src="s.avatar" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="text-sm truncate">{{ s.name || s.username }}</div>
              <div class="text-[11px] text-gray-400 truncate">{{ s.isGroup ? '群聊' : '单聊' }}</div>
            </div>
            <span
              v-if="archivedUsernames.has(s.username)"
              class="text-[10px] text-[#07b75b] border border-[#07b75b]/40 rounded px-1.5 py-0.5 flex-shrink-0"
            >已归档</span>
            <svg v-else-if="importingUsername === s.username" class="w-4 h-4 animate-spin text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import MessageList from '~/components/chat/MessageList.vue'
import StaticAiPanel from '~/components/static-chat/StaticAiPanel.vue'
import { useStaticApi } from '~/composables/useStaticApi'
import { useChatMessages } from '~/composables/chat/useChatMessages'
import { useChatHistoryWindows } from '~/composables/chat/useChatHistoryWindows'
import { useChatEditing } from '~/composables/chat/useChatEditing'
import { createEmptySearchContext } from '~/composables/chat/useChatSearch'
import {
  formatMessageFullTime,
  formatTransferAmount,
  getChatHistoryPreviewLines,
  getRedPacketText,
  getTransferTitle,
  highlightKeyword,
  isTransferOverdue,
  isTransferReturned
} from '~/lib/chat/formatters'
import { parseTextWithEmoji } from '~/lib/wechat-emojis'
import { useChatAccountsStore } from '~/stores/chatAccounts'
import { usePrivacyStore } from '~/stores/privacy'

useHead({ title: '静态聊天归档 - 微信数据库解密工具' })

const apiBase = useApiBase()
const api = useStaticApi()

const chatAccounts = useChatAccountsStore()
const { selectedAccount } = storeToRefs(chatAccounts)

const privacyStore = usePrivacyStore()
privacyStore.init()
const { privacyMode } = storeToRefs(privacyStore)

const selectedContact = ref(null)
const realtimeEnabled = ref(false)
const searchContext = ref(createEmptySearchContext())

// Reuse the real chat-message machinery, but message loading is redirected to the
// static archive via `api.listChatMessages` (see useStaticApi).
const messageState = useChatMessages({
  api,
  apiBase,
  selectedAccount,
  selectedContact,
  realtimeEnabled,
  privacyMode,
  searchContext
})

const {
  previewImageUrl,
  previewVideoUrl,
  previewVideoPosterUrl,
  closeImagePreview,
  closeVideoPreview,
  loadMessages,
  refreshSelectedMessages,
  resetMessageState,
  normalizeMessage,
  allMessages,
  messageContainerRef,
  hasMoreMessages,
  isLoadingMessages,
  loadMoreMessages,
  updateJumpToBottomState
} = messageState

const historyState = useChatHistoryWindows({
  api,
  apiBase,
  selectedAccount,
  selectedContact,
  openImagePreview: messageState.openImagePreview,
  openVideoPreview: messageState.openVideoPreview
})

const editingState = useChatEditing({
  api,
  selectedAccount,
  selectedContact,
  refreshSelectedMessages,
  normalizeMessage,
  allMessages,
  locateMessageByServerId: async () => false
})

// Lightweight scroll handler (auto-load older messages near the top).
const onMessageScroll = async () => {
  updateJumpToBottomState()
  const el = messageContainerRef.value
  if (el && el.scrollTop <= 40 && hasMoreMessages.value && !isLoadingMessages.value) {
    await loadMoreMessages()
  }
}

// The composed state consumed by MessageList / MessageItem / MessageContent —
// mirrors the live chat page's `chatState`, minus search/export/session panels.
const staticState = {
  selectedContact,
  privacyMode,
  searchContext,
  parseTextWithEmoji,
  formatMessageFullTime,
  highlightKeyword,
  formatTransferAmount,
  getChatHistoryPreviewLines,
  getRedPacketText,
  getTransferTitle,
  isTransferOverdue,
  isTransferReturned,
  ...messageState,
  ...historyState,
  ...editingState,
  onMessageScroll
}

// ---------------------------------------------------------------------------
// Archived conversations
// ---------------------------------------------------------------------------
const conversations = ref([])
const conversationsLoading = ref(false)

const archivedUsernames = computed(() => new Set(conversations.value.map((c) => c.username)))

const avatarUrl = (username) => {
  const acc = String(selectedAccount.value || '').trim()
  const u = String(username || '').trim()
  if (!acc || !u) return ''
  return `${apiBase}/chat/avatar?account=${encodeURIComponent(acc)}&username=${encodeURIComponent(u)}`
}

const loadConversations = async () => {
  if (!selectedAccount.value) return
  conversationsLoading.value = true
  try {
    const res = await api.listStaticConversations({ account: selectedAccount.value })
    conversations.value = Array.isArray(res?.conversations) ? res.conversations : []
  } catch (e) {
    console.error('[static-chat] loadConversations error', e)
    conversations.value = []
  } finally {
    conversationsLoading.value = false
  }
}

const buildContact = (conv) => ({
  id: conv.username,
  username: conv.username,
  name: conv.name || conv.username,
  avatar: conv.isGroup ? null : avatarUrl(conv.username),
  avatarColor: '#4B5563',
  isGroup: !!conv.isGroup,
  isTop: false
})

const selectConversation = async (conv) => {
  const contact = buildContact(conv)
  selectedContact.value = contact
  await loadMessages({ username: contact.username, reset: true })
}

// ---------------------------------------------------------------------------
// "导出最新消息" — incremental import from the checkpoint
// ---------------------------------------------------------------------------
const importing = ref(false)
const importStatus = ref('')
const importStatusTip = ref('')

const fmtLatest = (ts) => {
  const t = Number(ts || 0)
  if (!t) return ''
  try {
    return new Date(t * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const exportLatest = async () => {
  if (!selectedContact.value || importing.value) return
  importing.value = true
  importStatus.value = ''
  importStatusTip.value = ''
  try {
    const res = await api.importStaticConversation({
      account: selectedAccount.value,
      username: selectedContact.value.username,
      name: selectedContact.value.name,
      is_group: selectedContact.value.isGroup,
      mode: 'auto',
      timeout: 120000
    })
    const added = Number(res?.added || 0)
    const source = String(res?.source || 'decrypted')
    const srcLabel = source === 'realtime' ? '实时' : (source === 'decrypted' ? '快照' : source)
    const latest = fmtLatest(res?.latestTime || res?.conversation?.lastTime)
    const head = added > 0 ? `新增 ${added} 条` : '已是最新'
    importStatus.value = `${head} · ${srcLabel}${latest ? ` · 最新 ${latest}` : ''}`
    importStatusTip.value = source === 'realtime'
      ? '来源：实时读取微信活库（微信正在运行），已是真正的最新消息。'
      : '来源：已解密的数据库快照。若微信有更新的消息，需先在原版工具做实时同步/重新解密，或开着微信再点此按钮（会自动改读实时）。'
    await loadConversations()
    await refreshSelectedMessages()
  } catch (e) {
    console.error('[static-chat] exportLatest error', e)
    importStatus.value = '同步失败：' + (e?.message || '请检查后端')
    importStatusTip.value = ''
  } finally {
    importing.value = false
  }
}

// ---------------------------------------------------------------------------
// Add-conversation picker
// ---------------------------------------------------------------------------
const pickerOpen = ref(false)
const pickerLoading = ref(false)
const pickerError = ref('')
const pickerQuery = ref('')
const liveSessions = ref([])
const importingUsername = ref('')

const filteredLiveSessions = computed(() => {
  const q = pickerQuery.value.trim().toLowerCase()
  if (!q) return liveSessions.value
  return liveSessions.value.filter((s) => String(s.name || s.username || '').toLowerCase().includes(q))
})

const openPicker = async () => {
  pickerOpen.value = true
  pickerQuery.value = ''
  if (liveSessions.value.length) return
  pickerLoading.value = true
  pickerError.value = ''
  try {
    const res = await api.listChatSessions({ account: selectedAccount.value, limit: 1000, include_hidden: true })
    liveSessions.value = Array.isArray(res?.sessions) ? res.sessions : []
  } catch (e) {
    pickerError.value = e?.message || '加载会话失败'
  } finally {
    pickerLoading.value = false
  }
}

const closePicker = () => {
  pickerOpen.value = false
}

const importSession = async (session) => {
  if (importingUsername.value) return
  importingUsername.value = session.username
  try {
    await api.importStaticConversation({
      account: selectedAccount.value,
      username: session.username,
      name: session.name,
      is_group: session.isGroup,
      mode: 'full',
      max_messages: 0,
      timeout: 600000
    })
    await loadConversations()
    const conv = conversations.value.find((c) => c.username === session.username)
    if (conv) {
      closePicker()
      await selectConversation(conv)
    }
  } catch (e) {
    console.error('[static-chat] importSession error', e)
    pickerError.value = e?.message || '导入失败'
  } finally {
    importingUsername.value = ''
  }
}

// ---------------------------------------------------------------------------
// AI analysis panel (dedicated StaticAiPanel component handles the rest)
// ---------------------------------------------------------------------------
const aiPanelOpen = ref(false)
const toggleAiPanel = () => { aiPanelOpen.value = !aiPanelOpen.value }

onMounted(async () => {
  await chatAccounts.ensureLoaded()
  await loadConversations()
})

watch(selectedAccount, async () => {
  selectedContact.value = null
  resetMessageState()
  await loadConversations()
})
</script>

<style scoped>
.static-chat-shell {
  background: var(--app-surface-bg, #fff);
}

.static-session-panel {
  width: 280px;
  min-width: 280px;
  background: var(--app-surface-bg, #fff);
  border-color: var(--app-border, #e7e7e7);
}

.static-panel-header {
  border-color: var(--app-border, #e7e7e7);
}

.static-session-item {
  transition: background-color 0.12s ease;
}

.static-session-item:hover {
  background: var(--app-surface-soft, #f5f5f5);
}

.static-session-item-active {
  background: var(--app-surface-soft, #ececec);
}

.static-btn {
  border: 1px solid var(--app-border, #ddd);
  color: var(--app-text-primary, #333);
  background: var(--app-surface-bg, #fff);
  transition: background-color 0.12s ease;
}

.static-btn:hover:not(:disabled) {
  background: var(--app-surface-soft, #f2f2f2);
}

.static-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.static-btn-active {
  background: var(--app-surface-soft, #ececec);
  border-color: #07b75b;
  color: #07b75b;
}

.chat-header {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 52px;
  border-bottom: 1px solid var(--app-border, #e7e7e7);
  flex-shrink: 0;
}

.static-picker-panel {
  background: var(--app-surface-bg, #fff);
  border: 1px solid var(--app-border, #e7e7e7);
  color: var(--app-text-primary, #222);
}

.static-picker-panel .border-b {
  border-color: var(--app-border, #e7e7e7);
}

.static-picker-input {
  border: 1px solid var(--app-border, #ddd);
  background: var(--app-surface-soft, #fafafa);
  color: var(--app-text-primary, #222);
  outline: none;
}

.static-picker-input:focus {
  border-color: #07b75b;
}
</style>
