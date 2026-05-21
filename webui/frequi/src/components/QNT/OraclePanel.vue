<script setup lang="ts">
interface OracleData {
  score?: number;
  regime?: string;
  macro_risk?: string;
  funding_rate?: number;
  components?: Record<string, number>;
  timestamp?: string;
  error?: string;
}

const data = ref<OracleData>({});
const loading = ref(true);

function regimeColor(regime: string | undefined) {
  if (!regime) return 'neutral';
  const r = regime.toUpperCase();
  if (r.includes('BULL')) return 'success';
  if (r.includes('BEAR')) return 'error';
  return 'neutral';
}

function scoreColor(score: number | undefined) {
  if (score === undefined) return 'text-gray-400';
  if (score >= 0.3) return 'text-green-400';
  if (score <= -0.3) return 'text-red-400';
  return 'text-yellow-400';
}

function macroColor(risk: string | undefined) {
  if (!risk) return 'neutral';
  const r = risk.toUpperCase();
  if (r === 'LOW') return 'success';
  if (r === 'HIGH') return 'error';
  return 'warning';
}

async function fetchOracle() {
  try {
    const res = await fetch('/api/qnt/oracle');
    data.value = await res.json();
  } catch {
    data.value = { error: 'Unreachable' };
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchOracle();
  setInterval(fetchOracle, 15_000);
});
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-mdi-crystal-ball" class="text-purple-400 text-lg" />
        <span class="font-semibold text-sm">Market Oracle</span>
        <UBadge v-if="loading" color="neutral" variant="subtle" size="xs">loading</UBadge>
      </div>
    </template>

    <div v-if="data.error" class="text-gray-500 text-xs">{{ data.error }}</div>
    <div v-else class="space-y-2 text-sm">
      <div class="flex justify-between items-center">
        <span class="text-gray-400">Sentiment</span>
        <span :class="scoreColor(data.score)" class="font-mono font-bold">
          {{ data.score !== undefined ? data.score.toFixed(3) : '—' }}
        </span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-gray-400">Regime</span>
        <UBadge :color="regimeColor(data.regime)" size="xs">
          {{ data.regime ?? 'NEUTRAL' }}
        </UBadge>
      </div>
      <div v-if="data.macro_risk" class="flex justify-between items-center">
        <span class="text-gray-400">Macro Risk</span>
        <UBadge :color="macroColor(data.macro_risk)" size="xs">
          {{ data.macro_risk }}
        </UBadge>
      </div>
      <div v-if="data.funding_rate !== undefined" class="flex justify-between items-center">
        <span class="text-gray-400">Funding Rate</span>
        <span class="font-mono text-xs">{{ data.funding_rate.toFixed(4) }}</span>
      </div>
    </div>
  </UCard>
</template>
