<template>
  <div class="flex-1 flex flex-col min-h-0">
    <div v-if="showBack" class="px-3 py-1.5 border-b">
      <button type="button" class="text-[11px] text-gray-400 hover:text-gray-700" @click="$emit('back')">{{ backLabel }}</button>
    </div>

    <div ref="scrollEl" class="flex-1 overflow-y-auto min-h-0 p-3">
      <template v-if="turns.length || sending">
        <div
          v-for="(t, i) in turns"
          :key="i"
          class="ai-msg-row"
          :class="t.role === 'user' ? 'ai-msg-user' : 'ai-msg-assistant'"
        >
          <div
            class="ai-bubble"
            :class="[t.role === 'user' ? 'ai-bubble-user' : 'ai-bubble-assistant', { 'privacy-blur': privacyMode && t.role === 'user' }]"
          >{{ t.content }}</div>
        </div>
        <div v-if="sending" class="ai-msg-row ai-msg-assistant">
          <div class="ai-bubble ai-bubble-assistant ai-typing">AI 思考中…</div>
        </div>
      </template>
      <div v-else class="text-center text-xs text-gray-400 py-6">点下方预设问题，或直接输入你的问题</div>
      <div v-if="error" class="text-xs text-red-500 whitespace-pre-wrap mt-2">{{ error }}</div>
    </div>

    <div v-if="presets.length" class="flex flex-wrap gap-1.5 px-3 pb-2">
      <button
        v-for="(q, i) in presets"
        :key="i"
        type="button"
        class="ai-preset text-[11px] px-2 py-1 rounded-full"
        :disabled="sending"
        @click="$emit('send', q)"
      >{{ q }}</button>
    </div>

    <div class="flex items-end gap-2 px-3 pb-3">
      <textarea
        v-model="input"
        class="ai-input flex-1 text-[13px] px-2 py-1.5 rounded resize-none"
        rows="2"
        placeholder="输入你的问题…（Enter 发送，Shift+Enter 换行）"
        :disabled="sending"
        @keydown="onKeydown"
      ></textarea>
      <button
        type="button"
        class="ai-btn text-xs px-3 py-2 rounded shrink-0"
        :disabled="sending || !input.trim()"
        @click="submit"
      >{{ sending ? '…' : '发送' }}</button>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  turns: { type: Array, default: () => [] },
  sending: { type: Boolean, default: false },
  error: { type: String, default: '' },
  presets: { type: Array, default: () => [] },
  privacyMode: { type: Boolean, default: false },
  showBack: { type: Boolean, default: false },
  backLabel: { type: String, default: '‹ 返回对话列表' }
})
const emit = defineEmits(['send', 'back'])

const input = ref('')
const scrollEl = ref(null)

const submit = () => {
  const text = input.value.trim()
  if (!text || props.sending) return
  input.value = ''
  emit('send', text)
}

const onKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    const el = scrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(() => props.turns.length, scrollToBottom)
watch(() => props.sending, scrollToBottom)
</script>

<style scoped>
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

.ai-input {
  border: 1px solid var(--app-border, #ddd);
  background: var(--app-surface-soft, #fafafa);
  color: var(--app-text-primary, #222);
  outline: none;
}
.ai-input:focus { border-color: #07b75b; }
.ai-btn { background: #07b75b; color: #fff; border: none; transition: opacity .12s; }
.ai-btn:hover:not(:disabled) { opacity: .88; }
.ai-btn:disabled { opacity: .5; cursor: not-allowed; }
.ai-preset {
  border: 1px solid var(--app-border, #ddd);
  color: var(--app-text-muted, #666);
  background: var(--app-surface-bg, #fff);
}
.ai-preset:hover:not(:disabled) { border-color: #07b75b; color: #07b75b; }
.ai-preset:disabled { opacity: .5; cursor: not-allowed; }
</style>
