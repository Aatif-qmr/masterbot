/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { getModelQuotaInfo } from '@google/qnt-cli-core';
import type { SlashCommand, CommandContext } from './types.js';
import { CommandKind } from './types.js';
import { MessageType } from '../types.js';

export const qntModelCommand: SlashCommand = {
  name: 'model',
  description: 'Show which model qnt will use for next request',
  kind: CommandKind.BUILT_IN,
  async action(context: CommandContext, _args: string) {
    const config = context.services.agentContext?.config;
    if (!config) {
      context.ui.addItem({ type: MessageType.ERROR, text: 'Agent config not available.' });
      return;
    }
    const activeModel = config.getActiveModel();
    const quotaInfo = getModelQuotaInfo(activeModel);
    context.ui.addItem({
      type: MessageType.INFO,
      text: `Current model: ${activeModel} | Quota: ${quotaInfo}`,
    });
  },
};
