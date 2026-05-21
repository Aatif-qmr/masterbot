<script setup lang="ts">
import OraclePanel from '@/components/QNT/OraclePanel.vue';
import ShieldPanel from '@/components/QNT/ShieldPanel.vue';
import LogViewer from '@/components/QNT/LogViewer.vue';

const botStore = useBotStore();
const alertStore = useAlertsStore();

const stopping = ref(false);

async function emergencyStopAll() {
  stopping.value = true;
  try {
    await Promise.allSettled(
      botStore.allBotStores.map((s) => s.stopBuy()),
    );
    alertStore.addAlert({
      title: 'Emergency Stop',
      message: 'Stop-entry sent to all bots.',
      severity: 'success',
      timeout: 5000,
    });
  } catch {
    alertStore.addAlert({
      title: 'Emergency Stop Failed',
      message: 'Stop-entry failed on one or more bots.',
      severity: 'error',
      timeout: 8000,
    });
  } finally {
    stopping.value = false;
  }
}

function profitColor(value: number | undefined) {
  if (value === undefined) return 'text-gray-400';
  return value >= 0 ? 'text-green-400' : 'text-red-400';
}

function profitDisplay(value: number | undefined) {
  if (value === undefined) return '—';
  const pct = (value * 100).toFixed(2);
  return `${value >= 0 ? '+' : ''}${pct}%`;
}
</script>

<template>
  <div class="p-4 space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div class="flex items-center gap-3">
        <UIcon name="i-mdi-robot" class="text-purple-400 text-2xl" />
        <div>
          <h1 class="text-xl font-bold">MasterBot Command Center</h1>
          <p class="text-xs text-gray-500">
            {{ botStore.botCount }} bot{{ botStore.botCount !== 1 ? 's' : '' }} configured
          </p>
        </div>
      </div>
      <UButton
        color="error"
        variant="soft"
        icon="i-mdi-alert-octagon"
        :loading="stopping"
        @click="emergencyStopAll"
      >
        Stop Entry All Bots
      </UButton>
    </div>

    <!-- QNT panels row -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <OraclePanel />
      <ShieldPanel />
    </div>

    <!-- Bot grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <UCard
        v-for="bot in botStore.allBotStores"
        :key="bot.$id"
        class="cursor-pointer transition-shadow hover:shadow-lg"
        @click="botStore.selectBot(bot.$id)"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-semibold truncate">{{ bot.uiBotName }}</span>
            <UBadge
              :color="bot.isBotOnline ? 'success' : 'error'"
              variant="subtle"
              size="xs"
            >
              {{ bot.isBotOnline ? 'ONLINE' : 'OFFLINE' }}
            </UBadge>
          </div>
        </template>

        <div class="space-y-2 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-400">Balance</span>
            <span class="font-mono">
              {{
                bot.balance?.total !== undefined
                  ? `${bot.balance.total.toFixed(2)} ${bot.balance.stake ?? 'USDT'}`
                  : '—'
              }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">Open Trades</span>
            <span class="font-mono">{{ bot.openTradeCount }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">Profit (all)</span>
            <span :class="profitColor(bot.profit?.profit_factor)" class="font-mono">
              {{
                bot.profit?.profit_all_coin !== undefined
                  ? `${bot.profit.profit_all_coin.toFixed(2)} USDT`
                  : '—'
              }}
            </span>
          </div>
          <div v-if="bot.openTradeCount > 0" class="border-t border-gray-700 pt-2 space-y-1">
            <div
              v-for="trade in bot.openTrades.slice(0, 3)"
              :key="trade.trade_id"
              class="flex justify-between text-xs"
            >
              <span class="text-gray-400 truncate max-w-[8rem]">{{ trade.pair }}</span>
              <span :class="profitColor(trade.profit_ratio)" class="font-mono">
                {{ profitDisplay(trade.profit_ratio) }}
              </span>
            </div>
            <div v-if="bot.openTradeCount > 3" class="text-xs text-gray-600">
              +{{ bot.openTradeCount - 3 }} more
            </div>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Log viewer -->
    <LogViewer />
  </div>
</template>
