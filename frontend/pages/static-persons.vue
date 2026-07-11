<template>
  <div class="static-persons-shell h-screen flex overflow-hidden">
    <!-- Left: cross-group person list -->
    <div class="persons-panel flex flex-col border-r min-h-0">
      <div class="persons-header flex items-center justify-between px-3 h-[52px] border-b">
        <div class="text-sm font-medium">
          跨群人物
          <span class="text-xs text-gray-400">({{ filteredPersons.length }})</span>
        </div>
      </div>

      <!-- Time range + presets -->
      <div class="flex items-center gap-1.5 px-3 pt-2 text-[11px] text-gray-500">
        <span class="shrink-0">时间</span>
        <input type="date" v-model="startDate" class="pp-input flex-1 px-1 py-0.5 rounded min-w-0" />
        <span>~</span>
        <input type="date" v-model="endDate" class="pp-input flex-1 px-1 py-0.5 rounded min-w-0" />
        <button v-if="startDate || endDate" type="button" class="shrink-0 text-gray-400 hover:text-gray-700" title="清除" @click="clearRange">✕</button>
      </div>
      <div class="flex items-center flex-wrap gap-1 px-3 py-2 border-b">
        <button
          v-for="p in rangePresets"
          :key="p.days"
          type="button"
          class="pp-preset text-[11px] px-2 py-0.5 rounded-full"
          :class="{ 'pp-preset-active': activePreset === p.days }"
          @click="applyPreset(p.days)"
        >{{ p.label }}</button>
      </div>

      <!-- Search -->
      <div class="px-3 py-2 border-b">
        <input
          v-model="query"
          type="text"
          placeholder="搜索人物名称..."
          class="pp-input w-full text-sm px-3 py-1.5 rounded"
        />
        <label class="flex items-center gap-1.5 mt-2 text-[11px] text-gray-500 cursor-pointer select-none">
          <input type="checkbox" v-model="onlyMultiGroup" />
          只看出现在 2 个及以上群聊的人
        </label>
      </div>

      <div class="flex-1 overflow-y-auto min-h-0">
        <div v-if="personsLoading" class="text-center text-xs text-gray-400 py-8">聚合人物中...</div>
        <div v-else-if="!filteredPersons.length" class="text-center text-xs text-gray-400 py-10 px-4 leading-relaxed">
          没有符合条件的人物。<br />先在「静态归档」里导入几个群聊，<br />这里会自动按人聚合。
        </div>
        <div
          v-for="(p, i) in filteredPersons"
          :key="p.username"
          class="person-row flex items-center gap-2.5 px-3 py-2.5 cursor-pointer"
          :class="{ 'person-row-active': selectedPerson && selectedPerson.username === p.username }"
          @click="selectPerson(p)"
        >
          <div class="text-[11px] text-gray-400 w-5 text-right shrink-0">{{ i + 1 }}</div>
          <div class="w-9 h-9 rounded-md overflow-hidden bg-gray-300 flex-shrink-0" :class="{ 'privacy-blur': privacyMode }">
            <img v-if="personAvatar(p)" :src="personAvatar(p)" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
          </div>
          <div class="min-w-0 flex-1" :class="{ 'privacy-blur': privacyMode }">
            <div class="text-sm truncate">{{ p.name }}<span v-if="p.isSelf" class="text-[10px] text-[#07b75b]"> (我)</span></div>
            <div class="text-[11px] text-gray-400 truncate">{{ p.count }} 条 · {{ p.groupCount }} 个群</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Center -->
    <div class="flex-1 flex flex-col min-h-0 min-w-0">
      <template v-if="selectedPerson">
        <div class="pp-detail-header">
          <div class="w-8 h-8 rounded-md overflow-hidden bg-gray-300 flex-shrink-0" :class="{ 'privacy-blur': privacyMode }">
            <img v-if="personAvatar(selectedPerson)" :src="personAvatar(selectedPerson)" class="w-full h-full object-cover" referrerpolicy="no-referrer" />
          </div>
          <div class="min-w-0">
            <div class="text-base font-medium truncate" :class="{ 'privacy-blur': privacyMode }">{{ selectedPerson.name }}</div>
            <div class="text-[11px] text-gray-400">{{ selectedPerson.count }} 条发言 · 出现在 {{ selectedPerson.groupCount }} 个群</div>
          </div>
          <div class="ml-auto flex items-center gap-2">
            <select v-if="models.length" v-model="model" class="pp-input text-[11px] px-1.5 py-1 rounded max-w-[130px]" :title="'模型：' + model">
              <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
            </select>
            <div class="flex rounded-md overflow-hidden border" :style="{ borderColor: 'var(--app-border,#ddd)' }">
              <button type="button" class="pp-seg text-[12px] px-3 py-1" :class="{ 'pp-seg-active': view === 'messages' }" @click="view = 'messages'">跨群发言</button>
              <button type="button" class="pp-seg text-[12px] px-3 py-1" :class="{ 'pp-seg-active': view === 'chat' }" @click="goToChat">AI 画像</button>
            </div>
          </div>
        </div>

        <!-- group chips -->
        <div class="flex items-center flex-wrap gap-1.5 px-4 py-2 border-b">
          <span
            v-for="g in selectedPerson.groups"
            :key="g.username"
            class="pp-chip text-[11px] px-2 py-0.5 rounded-full"
            :class="{ 'privacy-blur': privacyMode }"
          >{{ g.name }} · {{ g.count }}</span>
        </div>

        <!-- messages view -->
        <div v-if="view === 'messages'" class="flex-1 overflow-y-auto min-h-0 px-4 py-3">
          <div v-if="messagesLoading" class="text-center text-xs text-gray-400 py-10">加载跨群发言中...</div>
          <div v-else-if="!messages.length" class="text-center text-xs text-gray-400 py-10">该时间段内没有发言</div>
          <div v-for="(m, i) in messages" :key="i" class="pp-msg text-[13px] leading-relaxed py-1.5">
            <span class="text-gray-400 mr-1.5 whitespace-nowrap">{{ msgTime(m) }}</span>
            <span class="pp-msg-group mr-1.5" :class="{ 'privacy-blur': privacyMode }">{{ m._conversationName }}</span>
            <span :class="{ 'privacy-blur': privacyMode }">{{ msgText(m) }}</span>
          </div>
        </div>

        <!-- AI chat view -->
        <StaticAiThread
          v-else
          :turns="turns"
          :sending="sending"
          :error="threadError"
          :presets="personPresets"
          :privacy-mode="privacyMode"
          :show-back="true"
          back-label="‹ 返回跨群发言"
          @send="send"
          @back="view = 'messages'"
        />
      </template>

      <div v-else class="flex-1 flex items-center justify-center">
        <div class="text-center max-w-[320px] px-6">
          <div class="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-[#03C160]/10 to-[#03C160]/5 flex items-center justify-center">
            <svg class="w-10 h-10 text-[#03C160]/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-1.13a4 4 0 10-4-4 4 4 0 004 4zm7-3a3 3 0 10-3-3M4 10a3 3 0 003-3" />
            </svg>
          </div>
          <h3 class="text-base font-medium mb-1.5">跨群人物画像</h3>
          <p class="text-sm text-gray-400 leading-relaxed">同一个人可能出现在多个群聊。从左侧选择一个人，查看 TA 在所有归档群里的发言，并让 AI 综合分析。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import StaticAiThread from '~/components/static-chat/StaticAiThread.vue'
import { useStaticApi } from '~/composables/useStaticApi'
import { useChatAccountsStore } from '~/stores/chatAccounts'
import { usePrivacyStore } from '~/stores/privacy'

useHead({ title: '跨群人物画像 - 微信数据库解密工具' })

// Kept in sync with static_archive_ai.GLOBAL_PERSON_USERNAME (backend sentinel).
const GLOBAL_PERSON_USERNAME = '@person'

const api = useStaticApi()
const apiBase = useApiBase()

const chatAccounts = useChatAccountsStore()
const { selectedAccount } = storeToRefs(chatAccounts)

const privacyStore = usePrivacyStore()
privacyStore.init()
const { privacyMode } = storeToRefs(privacyStore)

// ---- time range ----
const startDate = ref('')
const endDate = ref('')
const pad2 = (n) => String(n).padStart(2, '0')
const fmtDate = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
const rangePresets = [
  { label: '今天', days: 1 },
  { label: '近7天', days: 7 },
  { label: '近30天', days: 30 },
  { label: '近90天', days: 90 },
  { label: '全部', days: 0 }
]
const presetRange = (days) => {
  if (!days) return { start: '', end: '' }
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - (days - 1))
  return { start: fmtDate(start), end: fmtDate(end) }
}
const applyPreset = (days) => {
  const r = presetRange(days)
  startDate.value = r.start
  endDate.value = r.end
}
const activePreset = computed(() => {
  for (const p of rangePresets) {
    const r = presetRange(p.days)
    if (r.start === (startDate.value || '') && r.end === (endDate.value || '')) return p.days
  }
  return null
})
const clearRange = () => { startDate.value = ''; endDate.value = '' }
const toUnix = (s, end = false) => {
  if (!s) return null
  const d = new Date(s + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return null
  return Math.floor(d.getTime() / 1000) + (end ? 86399 : 0)
}

// ---- message rendering ----
const MEDIA = {
  image: '[图片]', video: '[视频]', voice: '[语音]', emoji: '[表情]', file: '[文件]',
  link: '[链接]', transfer: '[转账]', redPacket: '[红包]', chatHistory: '[聊天记录]', voip: '[通话]'
}
const msgText = (m) => {
  const rt = String(m?.renderType || 'text')
  if (rt === 'text' || rt === 'quote') return String(m?.content || '').trim() || '[空]'
  return MEDIA[rt] || (String(m?.content || '').trim() || `[${rt}]`)
}
const msgTime = (m) => {
  const t = Number(m?.createTime || 0)
  if (!t) return ''
  try {
    return new Date(t * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

// ---- persons ----
const persons = ref([])
const personsLoading = ref(false)
const query = ref('')
const onlyMultiGroup = ref(false)

const filteredPersons = computed(() => {
  const q = query.value.trim().toLowerCase()
  return persons.value.filter((p) => {
    if (onlyMultiGroup.value && p.groupCount < 2) return false
    if (q && !String(p.name || p.username || '').toLowerCase().includes(q)) return false
    return true
  })
})

const personAvatar = (p) => {
  const acc = String(selectedAccount.value || '').trim()
  const u = p?.isSelf ? acc : String(p?.username || '').trim()
  if (!acc || !u) return ''
  return `${apiBase}/chat/avatar?account=${encodeURIComponent(acc)}&username=${encodeURIComponent(u)}`
}

const loadPersons = async () => {
  if (!selectedAccount.value) return
  personsLoading.value = true
  try {
    const res = await api.listStaticPersons({
      account: selectedAccount.value,
      start_time: toUnix(startDate.value),
      end_time: toUnix(endDate.value, true),
      top: 800
    })
    persons.value = Array.isArray(res?.persons) ? res.persons : []
  } catch (e) {
    console.error('[static-persons] loadPersons error', e)
    persons.value = []
  } finally {
    personsLoading.value = false
  }
}

// ---- selected person ----
const selectedPerson = ref(null)
const view = ref('messages')
const messages = ref([])
const messagesLoading = ref(false)

const loadPersonMessages = async () => {
  if (!selectedPerson.value) return
  messagesLoading.value = true
  try {
    const res = await api.listStaticPersonGlobalMessages({
      account: selectedAccount.value,
      target_user: selectedPerson.value.isSelf ? '__self__' : selectedPerson.value.username,
      start_time: toUnix(startDate.value),
      end_time: toUnix(endDate.value, true),
      limit: 3000
    })
    messages.value = Array.isArray(res?.messages) ? res.messages : []
  } catch (e) {
    console.error('[static-persons] loadPersonMessages error', e)
    messages.value = []
  } finally {
    messagesLoading.value = false
  }
}

const selectPerson = async (p) => {
  selectedPerson.value = p
  view.value = 'messages'
  activeChat.value = null
  turns.value = []
  await loadPersonMessages()
}

// ---- AI (cross-group profile chat) ----
const models = ref([])
const model = ref('')
const activeChat = ref(null)
const turns = ref([])
const sending = ref(false)
const threadError = ref('')
const personPresets = [
  '综合 TA 在各个群里的发言，分析 TA 的性格与关注点',
  'TA 在不同群里的表现有什么差异',
  'TA 最擅长 / 最常聊什么',
  'TA 给人的整体印象是怎样的（附依据）'
]

const loadModels = async () => {
  try {
    const cfg = await api.getStaticAiConfig()
    if (!cfg?.configured) return
    const res = await api.getStaticAiModels()
    models.value = Array.isArray(res?.models) ? res.models : []
    model.value = res?.default || models.value[0] || ''
  } catch {}
}

const goToChat = async () => {
  view.value = 'chat'
  if (!activeChat.value) {
    threadError.value = ''
    try {
      const res = await api.createStaticAiChat({
        account: selectedAccount.value,
        username: GLOBAL_PERSON_USERNAME,
        kind: 'profile',
        target_user: selectedPerson.value.isSelf ? '__self__' : selectedPerson.value.username,
        target_name: selectedPerson.value.name,
        start_time: toUnix(startDate.value),
        end_time: toUnix(endDate.value, true)
      })
      const detail = await api.getStaticAiChat(res.chat.id)
      activeChat.value = detail.chat
      turns.value = Array.isArray(detail?.turns) ? detail.turns : []
    } catch (e) {
      threadError.value = e?.data?.detail || e?.message || '新建画像对话失败'
    }
  }
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
  } catch (e) {
    threadError.value = e?.data?.detail || e?.message || 'AI 回复失败'
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  await chatAccounts.ensureLoaded()
  await Promise.all([loadPersons(), loadModels()])
})

// Range change → reload persons; if a person is open, reload their messages and
// invalidate the current chat so a fresh range is used next time.
watch([startDate, endDate], () => {
  loadPersons()
  if (selectedPerson.value) {
    activeChat.value = null
    if (view.value === 'messages') loadPersonMessages()
  }
})

watch(selectedAccount, async () => {
  selectedPerson.value = null
  persons.value = []
  await loadPersons()
})
</script>

<style scoped>
.static-persons-shell { background: var(--app-surface-bg, #fff); }

.persons-panel {
  width: 300px;
  min-width: 300px;
  background: var(--app-surface-bg, #fff);
  border-color: var(--app-border, #e7e7e7);
}
.persons-header { border-color: var(--app-border, #e7e7e7); }
.persons-panel :is(.border-b) { border-color: var(--app-border, #e7e7e7); }

.person-row { transition: background-color .12s; }
.person-row:hover { background: var(--app-surface-soft, #f5f5f5); }
.person-row-active { background: var(--app-surface-soft, #ececec); }

.pp-detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  height: 56px;
  border-bottom: 1px solid var(--app-border, #e7e7e7);
  flex-shrink: 0;
}
.pp-detail-header :is(.border-b) { border-color: var(--app-border, #e7e7e7); }

.pp-input {
  border: 1px solid var(--app-border, #ddd);
  background: var(--app-surface-soft, #fafafa);
  color: var(--app-text-primary, #222);
  outline: none;
}
.pp-input:focus { border-color: #07b75b; }

.pp-preset {
  border: 1px solid var(--app-border, #ddd);
  color: var(--app-text-muted, #666);
  background: var(--app-surface-bg, #fff);
  transition: border-color .12s, color .12s, background-color .12s;
}
.pp-preset:hover { border-color: #07b75b; color: #07b75b; }
.pp-preset-active { border-color: #07b75b; color: #fff; background: #07b75b; }

.pp-seg { color: var(--app-text-muted, #666); background: var(--app-surface-bg, #fff); transition: background-color .12s, color .12s; }
.pp-seg-active { background: #07b75b; color: #fff; }

.pp-chip {
  border: 1px solid var(--app-border, #e2e2e2);
  background: var(--app-surface-soft, #f6f6f6);
  color: var(--app-text-muted, #555);
}

.pp-msg { border-bottom: 1px solid var(--app-border, #f0f0f0); }
.pp-msg:last-child { border-bottom: none; }
.pp-msg-group { color: #07b75b; font-size: 11px; }
</style>
