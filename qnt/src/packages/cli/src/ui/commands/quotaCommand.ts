/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { getQuotaReport } from '@google/qnt-cli-core';
import type { SlashCommand, CommandContext } from './types.js';
import { CommandKind } from './types.js';
import { MessageType } from '../types.js';

export const quotaCommand: SlashCommand = {
  name: 'quota',
  description: 'Show qnt model quota status for today',
  kind: CommandKind.BUILT_IN,
  async action(context: CommandContext, _args: string) {
    const report = getQuotaReport();
    context.ui.addItem({
      type: MessageType.INFO,
      text: report,
    });
  },
};
