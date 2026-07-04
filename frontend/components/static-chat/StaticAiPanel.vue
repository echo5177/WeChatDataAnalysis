<template>
  <div class="static-ai-panel flex flex-col border-l min-h-0">
    <!-- Header -->
    <div class="static-panel-header flex items-center gap-2 px-3 h-[52px] border-b">
      <div class="text-sm font-medium shrink-0">AI 分析</div>
      <select v-if="configured && models.length" v-model="model" class="ai-input ml-auto text-[11px] px-1.5 py-1 rounded max-w-[130px]" :title="'模型：' + model">
        <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
      </select>
      <button type="button" class="text-gray-400 hover:text-gray-700 shrink-0" @click="$emit('close')">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" /></svg>
      </button>
    </div>

    <!-- Not configured -->
    <div v-if="configured === false" class="p-3">
      <div class="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] leading-relaxed text-amber-900">
        未配置 LLM。请设置环境变量 <code>LLM_API_KEY</code>（可选 <code>LLM_BASE_URL</code> / <code>LLM_MODEL</code>）后重启后端。默认 DeepSeek。
      </div>
    </div>

    <template v-else>
      <!-- Tabs -->
      <div class="flex items-stretch border-b text-[13px]">
        <button
          type="button"
          class="ai-tab flex-1 py-2"
          :class="{ 'ai-tab-active': activeTab === 'summary' }"
          @click="activeTab = 'summary'"
        >会话总结</button>
        <button
          type="button"
          class="ai-tab flex-1 py-2"
          :class="{ 'ai-tab-active': activeTab === 'profile' }"
          @click="switchToProfile"
        >用户画像</button>
      </div>

      <!-- Time range -->
      <div class="flex items-center gap-1.5 px-3 py-2 border-b text-[11px] text-gray-500">
        <span class="shrink-0">时间</span>
        <input type="date" v-model="startDate" class="ai-input flex-1 px-1 py-0.5 rounded min-w-0" />
        <span>~</span>
        <input type="date" v-model="endDate" class="ai-input flex-1 px-1 py-0.5 rounded min-w-0" />
        <button v-if="startDate || endDate" type="button" class="shrink-0 text-gray-400 hover:text-gray-700" title="清除" @click="clearRange">✕</button>
      </div>

      <!-- ===== SUMMARY TAB ===== -->
      <div v-show="activeTab === 'summary'" class="flex-1 flex flex-col min-h-0">
        <div class="flex items-center gap-2 px-3 py-2 border-b">
          <div class="text-[11px] text-gray-400 flex-1 truncate">
            {{ summaryChats.length }} 个总结对话{{ rangeLabel }}
          </div>
          <button type="button" class="ai-btn text-[11px] px-2 py-1 rounded" @click="startChat('summary')">＋ 新对话</button>
        </div>
        <div v-if="!activeChat || activeChat.kind !== 'summary'" class="flex-1 overflow-y-auto min-h-0">
          <div v-if="!summaryChats.length" class="text-center text-xs text-gray-400 py-8 px-4 leading-relaxed">
            还没有总结对话。<br />选好时间范围后点「＋ 新对话」，<br />像聊天一样问 AI 关于这段记录的问题。
          </div>
          <div
            v-for="c in summaryChats"
            :key="c.id"
            class="ai-chat-row flex items-center gap-2 px-3 py-2 cursor-pointer"
            @click="openChat(c)"
          >
            <svg class="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M8 12h8M8 8h8m-8 8h5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <div class="min-w-0 flex-1">
              <div class="text-[13px] truncate">{{ c.title || '新对话' }}</div>
              <div class="text-[10px] text-gray-400">{{ c.turnCount }} 轮 · {{ scopeLabel(c) }}</div>
            </div>
            <button type="button" class="shrink-0 text-gray-300 hover:text-red-500" title="删除" @click.stop="removeChat(c)">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M6 7h12M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2m-7 0v11a1 1 0 001 1h6a1 1 0 001-1V7" /></svg>
            </button>
          </div>
        </div>
        <StaticAiThread
          v-else
          :turns="turns"
          :sending="sending"
          :error="threadError"
          :presets="currentPresets"
          :privacy-mode="privacyMode"
          :show-back="true"
          @send="send"
          @back="backToChatList"
        />
      </div>

      <!-- ===== PROFILE TAB ===== -->
      <div v-show="activeTab === 'profile'" class="flex-1 flex flex-col min-h-0">
        <!-- member list -->
        <template v-if="!selectedMember">
          <div class="px-3 py-2 border-b text-[11px] text-gray-400">
            {{ members.length }} 位成员 · 按活跃度排序{{ rangeLabel }}
          </div>
          <div class="flex-1 overflow-y-auto min-h-0">
            <div v-if="membersLoading" class="text-center text-xs text-gray-400 py-8">加载成员中...</div>
            <div v-else-if="!members.length" class="text-center text-xs text-gray-400 py-8">无成员数据</div>
            <div
              v-for="(m, i) in members"
              :key="m.username"
              class="ai-chat-row flex items-center gap-2.5 px-3 py-2 cursor-pointer"
              @click="openMemberProfile(m)"
            >
              <div class="text-[11px] text-gray-400 w-5 text-right shrink-0">{{ i + 1 }}</div>
              <div class="w-8 h-8 rounded-md overflow-hidden bg-gray-300 flex-shrink-0" :class="{ 'privacy-blur': privacyMode }">
                <img v-if="memberAvatar(m)" :src="memberAvatar(m)" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
              </div>
              <div class="min-w-0 flex-1" :class="{ 'privacy-blur': privacyMode }">
                <div class="text-[13px] truncate">{{ m.name }}<span v-if="m.isSelf" class="text-[10px] text-[#07b75b]"> (我)</span></div>
                <div class="text-[10px] text-gray-400">{{ m.count }} 条发言</div>
              </div>
              <svg class="w-4 h-4 text-gray-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            </div>
          </div>
        </template>
        <!-- member chat -->
        <template v-else>
          <div class="flex items-center gap-2 px-3 py-2 border-b">
            <button type="button" class="text-gray-400 hover:text-gray-700 shrink-0" title="返回成员列表" @click="backToMembers">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
            </button>
            <div class="w-6 h-6 rounded overflow-hidden bg-gray-300 flex-shrink-0" :class="{ 'privacy-blur': privacyMode }">
              <img v-if="memberAvatar(selectedMember)" :src="memberAvatar(selectedMember)" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
            </div>
            <div class="text-[13px] font-medium truncate" :class="{ 'privacy-blur': privacyMode }">{{ selectedMember.name }}</div>
          </div>
          <StaticAiThread
            v-if="activeChat && activeChat.kind === 'profile'"
            :turns="turns"
            :sending="sending"
            :error="threadError"
            :presets="currentPresets"
            :privacy-mode="privacyMode"
            :show-back="false"
            @send="send"
          />
          <div v-else class="flex-1 flex items-center justify-center text-xs text-gray-400">准备对话中...</div>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useStaticApi } from '~/composables/useStaticApi'
import StaticAiThread from '~/components/static-chat/StaticAiThread.vue'

const props = defineProps({
  account: { type: String, default: '' },
  conversation: { type: Object, default: null },
  privacyMode: { type: Boolean, default: false }
})
defineEmits(['close'])

const api = useStaticApi()
const apiBase = useApiBase()

const configured = ref(null)
const models = ref([])
const model = ref('')
const activeTab = ref('summary')

const startDate = ref('')
const endDate = ref('')

const toUnix = (s, end = false) => {
  if (!s) return null
  const d = new Date(s + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return null
  return Math.floor(d.getTime() / 1000) + (end ? 86399 : 0)
}

const rangeLabel = computed(() => {
  if (startDate.value && endDate.value) return `（${startDate.value} ~ ${endDate.value}）`
  if (startDate.value) return `（${startDate.value} 起）`
  if (endDate.value) return `（截至 ${endDate.value}）`
  return '（全部）'
})

const scopeLabel = (c) => {
  const fmt = (t) => (t ? new Date(t * 1000).toLocaleDateString('zh-CN') : '')
  if (c.startTime && c.endTime) return `${fmt(c.startTime)}~${fmt(c.endTime)}`
  if (c.startTime) return `${fmt(c.startTime)}起`
  if (c.endTime) return `截至${fmt(c.endTime)}`
  return '全部'
}

const clearRange = () => {
  startDate.value = ''
  endDate.value = ''
}

// ---- shared chat thread state ----
const activeChat = ref(null)
const turns = ref([])
const sending = ref(false)
const threadError = ref('')

const summaryPresets = ['总结这段记录的主要话题', '有哪些重要决定和待办事项', '梳理关键事件的时间线', '最近大家主要在聊什么']
const profilePresets = ['分析 TA 的性格特点，并给出依据', 'TA 主要关注 / 擅长什么', 'TA 和群里谁互动最多', 'TA 的说话风格是怎样的']

const currentPresets = computed(() => (activeChat.value?.kind === 'profile' ? profilePresets : summaryPresets))

// ---- config ----
const loadConfig = async () => {
  try {
    const cfg = await api.getStaticAiConfig()
    configured.value = !!cfg?.configured
    if (configured.value) {
      const res = await api.getStaticAiModels()
      models.value = Array.isArray(res?.models) ? res.models : []
      model.value = res?.default || models.value[0] || ''
    }
  } catch {
    configured.value = false
  }
}

// ---- summary chats ----
const summaryChats = ref([])
const loadSummaryChats = async () => {
  if (!props.conversation) return
  try {
    const res = await api.listStaticAiChats({ account: props.account, username: props.conversation.username, kind: 'summary' })
    summaryChats.value = Array.isArray(res?.chats) ? res.chats : []
  } catch {
    summaryChats.value = []
  }
}

const startChat = async (kind, member = null) => {
  if (!props.conversation) return
  try {
    const res = await api.createStaticAiChat({
      account: props.account,
      username: props.conversation.username,
      kind,
      target_user: member?.username || '',
      target_name: member?.name || '',
      start_time: toUnix(startDate.value),
      end_time: toUnix(endDate.value, true)
    })
    if (kind === 'summary') await loadSummaryChats()
    await openChat(res.chat)
  } catch (e) {
    threadError.value = e?.data?.detail || e?.message || '新建对话失败'
  }
}

const openChat = async (chat) => {
  threadError.value = ''
  try {
    const res = await api.getStaticAiChat(chat.id)
    activeChat.value = res.chat
    turns.value = Array.isArray(res?.turns) ? res.turns : []
  } catch (e) {
    threadError.value = e?.data?.detail || e?.message || '打开对话失败'
  }
}

const removeChat = async (chat) => {
  try {
    await api.deleteStaticAiChat(chat.id)
    if (activeChat.value?.id === chat.id) activeChat.value = null
    await loadSummaryChats()
  } catch {}
}

const backToChatList = () => {
  activeChat.value = null
  if (activeTab.value === 'summary') loadSummaryChats()
}

const send = async (text) => {
  const content = String(text ?? '').trim()
  if (!content || sending.value || !activeChat.value) return
  sending.value = true
  threadError.value = ''
  turns.value = [...turns.value, { role: 'user', content }]
  try {
    const res = await api.sendStaticAiChat(activeChat.value.id, { content, model: model.value })
    turns.value = [...turns.value, { role: 'assistant', content: res?.reply || '(空回复)' }]
    if (activeChat.value.kind === 'summary') void loadSummaryChats()
  } catch (e) {
    threadError.value = e?.data?.detail || e?.message || 'AI 回复失败'
  } finally {
    sending.value = false
  }
}

// ---- profile members ----
const members = ref([])
const membersLoading = ref(false)
const selectedMember = ref(null)

const loadMembers = async () => {
  if (!props.conversation) return
  membersLoading.value = true
  try {
    const res = await api.listStaticAiMembers({
      account: props.account,
      username: props.conversation.username,
      start_time: toUnix(startDate.value),
      end_time: toUnix(endDate.value, true)
    })
    members.value = Array.isArray(res?.members) ? res.members : []
  } catch {
    members.value = []
  } finally {
    membersLoading.value = false
  }
}

const switchToProfile = () => {
  activeTab.value = 'profile'
  activeChat.value = null
  if (!members.value.length) loadMembers()
}

const memberAvatar = (m) => {
  const acc = String(props.account || '').trim()
  const u = m?.isSelf ? acc : String(m?.username || '').trim()
  if (!acc || !u) return ''
  return `${apiBase}/chat/avatar?account=${encodeURIComponent(acc)}&username=${encodeURIComponent(u)}`
}

const openMemberProfile = async (m) => {
  selectedMember.value = m
  activeChat.value = null
  await startChat('profile', m)
}

const backToMembers = () => {
  selectedMember.value = null
  activeChat.value = null
}

// ---- reset when conversation changes ----
watch(() => props.conversation?.username, () => {
  activeChat.value = null
  turns.value = []
  selectedMember.value = null
  members.value = []
  summaryChats.value = []
  if (props.conversation) {
    loadSummaryChats()
    if (activeTab.value === 'profile') loadMembers()
  }
})

// reload member ranking when range changes on profile tab
watch([startDate, endDate], () => {
  if (activeTab.value === 'profile' && !selectedMember.value) loadMembers()
})

loadConfig()
if (props.conversation) loadSummaryChats()
</script>

<style scoped>
.static-ai-panel {
  width: 420px;
  min-width: 420px;
  background: var(--app-surface-bg, #fff);
  border-color: var(--app-border, #e7e7e7);
}
.static-panel-header { border-color: var(--app-border, #e7e7e7); }
.static-ai-panel :is(.border-b, .border-l) { border-color: var(--app-border, #e7e7e7); }
.static-ai-panel code {
  background: var(--app-surface-soft, #f2f2f2);
  padding: 0 4px; border-radius: 3px; font-size: 11px;
}

.ai-tab { color: var(--app-text-muted, #888); transition: color .12s, border-color .12s; border-bottom: 2px solid transparent; }
.ai-tab:hover { color: var(--app-text-primary, #333); }
.ai-tab-active { color: #07b75b; border-bottom-color: #07b75b; }

.ai-input {
  border: 1px solid var(--app-border, #ddd);
  background: var(--app-surface-soft, #fafafa);
  color: var(--app-text-primary, #222);
  outline: none;
}
.ai-input:focus { border-color: #07b75b; }

.ai-btn {
  background: #07b75b; color: #fff; border: none; transition: opacity .12s;
}
.ai-btn:hover:not(:disabled) { opacity: .88; }
.ai-btn:disabled { opacity: .5; cursor: not-allowed; }

.ai-preset {
  border: 1px solid var(--app-border, #ddd);
  color: var(--app-text-muted, #666);
  background: var(--app-surface-bg, #fff);
}
.ai-preset:hover:not(:disabled) { border-color: #07b75b; color: #07b75b; }
.ai-preset:disabled { opacity: .5; cursor: not-allowed; }

.ai-chat-row { transition: background-color .12s; }
.ai-chat-row:hover { background: var(--app-surface-soft, #f5f5f5); }

.ai-msg-row { display: flex; margin-bottom: 10px; }
.ai-msg-user { justify-content: flex-end; }
.ai-msg-assistant { justify-content: flex-start; }
.ai-bubble {
  max-width: 88%; padding: 7px 10px; border-radius: 8px;
  font-size: 13px; line-height: 1.55; white-space: pre-wrap; word-break: break-word;
}
.ai-bubble-user { background: #95ec69; color: #111; }
.ai-bubble-assistant { background: var(--app-surface-soft, #f2f2f2); color: var(--app-text-primary, #222); }
.ai-typing { color: var(--app-text-muted, #999); }

html[data-theme='dark'] .ai-bubble-user { background: #3a6b3f; color: #eaffea; }
</style>
