<script setup lang="ts">
interface LogEntry {
  source: string;
  line: string;
}

const entries = ref<LogEntry[]>([]);
const container = ref<HTMLElement | null>(null);
let es: EventSource | null = null;

function lineClass(line: string) {
  const l = line.toUpperCase();
  if (l.includes('ERROR') || l.includes('CRITICAL')) return 'text-red-400';
  if (l.includes('WARNING') || l.includes('WARN')) return 'text-yellow-400';
  if (l.includes('BUY') || l.includes('ENTER')) return 'text-green-400';
  if (l.includes('SELL') || l.includes('EXIT')) return 'text-blue-400';
  return 'text-gray-400';
}

function connect() {
  es = new EventSource('/api/qnt/logs');
  es.onmessage = (event) => {
    try {
      const newEntries: LogEntry[] = JSON.parse(event.data);
      entries.value = [...entries.value, ...newEntries].slice(-100);
      nextTick(() => {
        if (container.value) {
          container.value.scrollTop = container.value.scrollHeight;
        }
      });
    } catch {
      // ignore parse errors
    }
  };
  es.onerror = () => {
    es?.close();
    setTimeout(connect, 5_000);
  };
}

onMounted(connect);
onUnmounted(() => es?.close());
</script>

<template>
  <UCard class="flex flex-col">
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-mdi-console-line" class="text-gray-400 text-lg" />
        <span class="font-semibold text-sm">Live Log Feed</span>
        <UBadge color="success" variant="subtle" size="xs">live</UBadge>
      </div>
    </template>

    <div
      ref="container"
      class="font-mono text-xs overflow-y-auto max-h-48 space-y-0.5 bg-gray-900 rounded p-2"
    >
      <div v-if="entries.length === 0" class="text-gray-600">Waiting for log events…</div>
      <div v-for="(entry, i) in entries" :key="i" :class="lineClass(entry.line)" class="leading-tight">
        <span class="text-gray-600 mr-1">[{{ entry.source }}]</span>{{ entry.line }}
      </div>
    </div>
  </UCard>
</template>
