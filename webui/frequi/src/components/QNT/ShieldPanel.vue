<script setup lang="ts">
interface ShieldData {
  status?: string;
  daily_drawdown?: number;
  weekly_drawdown?: number;
  daily_limit?: number;
  weekly_limit?: number;
  last_balance?: number;
  last_updated?: string;
  error?: string;
}

const data = ref<ShieldData>({});
const loading = ref(true);

function statusColor(status: string | undefined) {
  if (!status) return 'neutral';
  if (status === 'PROTECTED') return 'success';
  if (status === 'BREACHED') return 'error';
  return 'warning';
}

function drawdownColor(dd: number | undefined, limit: number | undefined) {
  if (dd === undefined || limit === undefined) return 'text-gray-400';
  const ratio = dd / limit;
  if (ratio < 0.5) return 'text-green-400';
  if (ratio < 0.8) return 'text-yellow-400';
  return 'text-red-400';
}

function drawdownPercent(dd: number | undefined, limit: number | undefined) {
  if (dd === undefined || limit === undefined) return '—';
  return `${dd.toFixed(2)}% / ${limit.toFixed(1)}%`;
}

function drawdownBarWidth(dd: number | undefined, limit: number | undefined) {
  if (dd === undefined || limit === undefined) return 0;
  return Math.min(100, (dd / limit) * 100);
}

async function fetchShield() {
  try {
    const res = await fetch('/api/qnt/shield');
    data.value = await res.json();
  } catch {
    data.value = { error: 'Unreachable' };
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchShield();
  setInterval(fetchShield, 30_000);
});
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-mdi-shield-check" class="text-blue-400 text-lg" />
        <span class="font-semibold text-sm">QNT Shield</span>
        <UBadge v-if="!loading && data.status" :color="statusColor(data.status)" size="xs">
          {{ data.status }}
        </UBadge>
      </div>
    </template>

    <div v-if="data.error" class="text-gray-500 text-xs">{{ data.error }}</div>
    <div v-else class="space-y-3 text-sm">
      <div>
        <div class="flex justify-between mb-1">
          <span class="text-gray-400">Daily Drawdown</span>
          <span :class="drawdownColor(data.daily_drawdown, data.daily_limit)" class="font-mono text-xs">
            {{ drawdownPercent(data.daily_drawdown, data.daily_limit) }}
          </span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-1.5">
          <div
            class="h-1.5 rounded-full transition-all"
            :class="(data.daily_drawdown ?? 0) / (data.daily_limit ?? 3) < 0.8 ? 'bg-green-500' : 'bg-red-500'"
            :style="{ width: `${drawdownBarWidth(data.daily_drawdown, data.daily_limit)}%` }"
          />
        </div>
      </div>
      <div>
        <div class="flex justify-between mb-1">
          <span class="text-gray-400">Weekly Drawdown</span>
          <span :class="drawdownColor(data.weekly_drawdown, data.weekly_limit)" class="font-mono text-xs">
            {{ drawdownPercent(data.weekly_drawdown, data.weekly_limit) }}
          </span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-1.5">
          <div
            class="h-1.5 rounded-full transition-all"
            :class="(data.weekly_drawdown ?? 0) / (data.weekly_limit ?? 7) < 0.8 ? 'bg-blue-500' : 'bg-red-500'"
            :style="{ width: `${drawdownBarWidth(data.weekly_drawdown, data.weekly_limit)}%` }"
          />
        </div>
      </div>
      <div v-if="data.last_balance" class="flex justify-between">
        <span class="text-gray-400">Balance</span>
        <span class="font-mono text-xs">${{ data.last_balance.toLocaleString() }}</span>
      </div>
    </div>
  </UCard>
</template>
