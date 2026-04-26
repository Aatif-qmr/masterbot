/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { ThinkingLevel } from '@google/genai';
import type { ModelConfigServiceConfig } from '../services/modelConfigService.js';
import { DEFAULT_THINKING_MODE } from './models.js';

export const DEFAULT_MODEL_CONFIGS: ModelConfigServiceConfig = {
  aliases: {
    base: {
      modelConfig: {
        generateContentConfig: {
          temperature: 0,
          topP: 1,
        },
      },
    },
    'chat-base': {
      extends: 'base',
      modelConfig: {
        generateContentConfig: {
          thinkingConfig: {
            includeThoughts: true,
          },
          temperature: 1,
          topP: 0.95,
          topK: 64,
        },
      },
    },
    'chat-base-2.5': {
      extends: 'chat-base',
      modelConfig: {
        generateContentConfig: {
          thinkingConfig: {
            thinkingBudget: DEFAULT_THINKING_MODE,
          },
        },
      },
    },
    'chat-base-3': {
      extends: 'chat-base',
      modelConfig: {
        generateContentConfig: {
          thinkingConfig: {
            thinkingLevel: ThinkingLevel.HIGH,
          },
        },
      },
    },
    'gemini-3-pro-preview': {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3-pro-preview',
      },
    },
    'gemini-3-flash-preview': {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3-flash-preview',
      },
    },
    'gemini-2.5-pro': {
      extends: 'chat-base-2.5',
      modelConfig: {
        model: 'gemini-2.5-pro',
      },
    },
    'gemini-2.5-flash': {
      extends: 'chat-base-2.5',
      modelConfig: {
        model: 'gemini-2.5-flash',
      },
    },
    'gemini-2.5-flash-lite': {
      extends: 'chat-base-2.5',
      modelConfig: {
        model: 'gemini-2.5-flash-lite',
      },
    },
    'gemma-4-31b-it': {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemma-4-31b-it',
      },
    },
    'gemma-4-26b-a4b-it': {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemma-4-26b-a4b-it',
      },
    },

    // QNT ALIASES
    auto: {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3-flash-preview',
      },
    },
    flash: {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3-flash-preview',
      },
    },
    lite: {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3.1-flash-lite-preview',
      },
    },
    pro: {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3.1-pro-preview-customtools',
      },
    },
    fast: {
      extends: 'chat-base-3',
      modelConfig: {
        model: 'gemini-3.1-flash-lite-preview',
      },
    },

    // Bases for the internal model configs.
    'gemini-2.5-flash-base': {
      extends: 'base',
      modelConfig: {
        model: 'gemini-2.5-flash',
      },
    },
    'gemini-3-flash-base': {
      extends: 'base',
      modelConfig: {
        model: 'gemini-3-flash-preview',
      },
    },
    classifier: {
      modelConfig: {
        model: 'gemini-3-flash-preview',
        generateContentConfig: {
          temperature: 0,
        },
      },
    },
  },
  modelDefinitions: {
    'gemini-3-pro-preview': {
      displayName: 'Gemini 3 Pro',
      tier: 'pro',
      family: 'gemini-3',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'The most capable Gemini model for complex tasks',
      features: { thinking: true, multimodalToolUse: true },
    },
    'gemini-3.1-pro-preview': {
      displayName: 'Gemini 3.1 Pro',
      tier: 'pro',
      family: 'gemini-3',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'The most capable Gemini 3.1 model',
      features: { thinking: true, multimodalToolUse: true },
    },
    'gemini-3.1-pro-preview-customtools': {
      displayName: 'Gemini 3.1 Pro (+customtools)',
      tier: 'pro',
      family: 'gemini-3',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'Gemini 3.1 Pro with enhanced tool capabilities',
      features: { thinking: true, multimodalToolUse: true },
    },
    'gemini-3-flash-preview': {
      displayName: 'Gemini 3 Flash',
      tier: 'flash',
      family: 'gemini-3',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'Fast and capable for most development tasks',
      features: { thinking: true, multimodalToolUse: true },
    },
    'gemini-3.1-flash-lite-preview': {
      displayName: 'Gemini 3.1 Flash Lite',
      tier: 'flash-lite',
      family: 'gemini-3',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'Ultra-fast and cost-effective',
      features: { thinking: true, multimodalToolUse: true },
    },
    'gemini-2.5-pro': {
      displayName: 'Gemini 2.5 Pro',
      tier: 'pro',
      family: 'gemini-2',
      isPreview: false,
      isVisible: true,
      dialogDescription: 'Reliable and accurate for architectural decisions',
      features: { thinking: true, multimodalToolUse: false },
    },
    'gemini-2.5-flash': {
      displayName: 'Gemini 2.5 Flash',
      tier: 'flash',
      family: 'gemini-2',
      isPreview: false,
      isVisible: true,
      dialogDescription: 'Fast and reliable for general tasks',
      features: { thinking: true, multimodalToolUse: false },
    },
    'gemini-2.5-flash-lite': {
      displayName: 'Gemini 2.5 Flash Lite',
      tier: 'flash-lite',
      family: 'gemini-2',
      isPreview: false,
      isVisible: true,
      dialogDescription:
        'Cost-effective for high-frequency low-complexity tasks',
      features: { thinking: true, multimodalToolUse: false },
    },
    'gemma-4-31b-it': {
      displayName: 'Gemma 4 31B',
      tier: 'custom',
      family: 'gemma-4',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'Advanced open model from Google',
      features: { thinking: true, multimodalToolUse: false },
    },
    'gemma-4-26b-a4b-it': {
      displayName: 'Gemma 4 26B (A4B)',
      tier: 'custom',
      family: 'gemma-4',
      isPreview: true,
      isVisible: true,
      dialogDescription: 'Optimized open model from Google',
      features: { thinking: true, multimodalToolUse: false },
    },
    'auto-gemini-3': {
      displayName: 'Auto (Gemini 3)',
      tier: 'auto',
      isPreview: true,
      isVisible: true,
      dialogDescription:
        'Let Gemini CLI decide the best model for the task: gemini-3-pro, gemini-3-flash',
      features: { thinking: true, multimodalToolUse: false },
    },
    'auto-gemini-2.5': {
      displayName: 'Auto (Gemini 2.5)',
      tier: 'auto',
      isPreview: false,
      isVisible: true,
      dialogDescription:
        'Let Gemini CLI decide the best model for the task: gemini-2.5-pro, gemini-2.5-flash',
      features: { thinking: false, multimodalToolUse: false },
    },
  },
  modelIdResolutions: {
    'gemma-4-31b-it': { default: 'gemma-4-31b-it' },
    'gemma-4-26b-a4b-it': { default: 'gemma-4-26b-a4b-it' },
    'gemini-3.1-pro-preview': {
      default: 'gemini-3.1-pro-preview',
      contexts: [
        { condition: { hasAccessToPreview: false }, target: 'gemini-2.5-pro' },
        { condition: { useCustomTools: true }, target: 'gemini-3.1-pro-preview-customtools' },
      ],
    },
    'gemini-3.1-pro-preview-customtools': {
      default: 'gemini-3.1-pro-preview-customtools',
      contexts: [ { condition: { hasAccessToPreview: false }, target: 'gemini-2.5-pro' } ],
    },
    'gemini-3-flash-preview': {
      default: 'gemini-3-flash-preview',
      contexts: [ { condition: { hasAccessToPreview: false }, target: 'gemini-2.5-flash' } ],
    },
    'gemini-3-pro-preview': {
      default: 'gemini-3-pro-preview',
      contexts: [
        { condition: { hasAccessToPreview: false }, target: 'gemini-2.5-pro' },
        { condition: { useGemini3_1: true, useCustomTools: true }, target: 'gemini-3.1-pro-preview-customtools' },
        { condition: { useGemini3_1: true }, target: 'gemini-3.1-pro-preview' },
      ],
    },
    'auto-gemini-3': {
      default: 'gemini-3-pro-preview',
      contexts: [
        { condition: { hasAccessToPreview: false }, target: 'gemini-2.5-pro' },
        { condition: { useGemini3_1: true, useCustomTools: true }, target: 'gemini-3.1-pro-preview-customtools' },
        { condition: { useGemini3_1: true }, target: 'gemini-3.1-pro-preview' },
      ],
    },
    auto: { default: 'gemini-3-flash-preview' },
    flash: { default: 'gemini-3-flash-preview' },
    pro: { default: 'gemini-3.1-pro-preview-customtools' },
    lite: { default: 'gemini-3.1-flash-lite-preview' },
    fast: { default: 'gemini-3.1-flash-lite-preview' },
    'auto-gemini-2.5': { default: 'gemini-2.5-pro' },
    'flash-lite': { default: 'gemini-2.5-flash-lite' },
  },
  classifierIdResolutions: {
    auto: {
      default: 'gemini-3-flash-preview',
    },
    flash: {
      default: 'gemini-3-flash-preview',
    },
    lite: {
      default: 'gemini-3.1-flash-lite-preview',
    },
    pro: {
      default: 'gemini-3.1-pro-preview-customtools',
    },
    fast: {
      default: 'gemini-3.1-flash-lite-preview',
    },
    proactive: {
      default: 'gemini-3-flash-preview',
      contexts: [
        {
          condition: { requestedModels: ['auto-gemini-2.5', 'gemini-2.5-pro'] },
          target: 'gemini-2.5-flash',
        },
        {
          condition: {
            requestedModels: ['auto-gemini-3', 'gemini-3-pro-preview'],
          },
          target: 'gemini-3-flash-preview',
        },
      ],
    },
  },
  modelChains: {
    preview: [
      {
        model: 'gemini-3-pro-preview',
        actions: {
          terminal: 'prompt',
          transient: 'prompt',
          not_found: 'prompt',
          unknown: 'prompt',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
      {
        model: 'gemini-3-flash-preview',
        isLastResort: true,
        actions: {
          terminal: 'prompt',
          transient: 'prompt',
          not_found: 'prompt',
          unknown: 'prompt',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
    ],
    default: [
      {
        model: 'gemini-2.5-pro',
        actions: {
          terminal: 'prompt',
          transient: 'prompt',
          not_found: 'prompt',
          unknown: 'prompt',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
      {
        model: 'gemini-2.5-flash',
        isLastResort: true,
        actions: {
          terminal: 'prompt',
          transient: 'prompt',
          not_found: 'prompt',
          unknown: 'prompt',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
    ],
    lite: [
      {
        model: 'gemini-2.5-flash-lite',
        actions: {
          terminal: 'silent',
          transient: 'silent',
          not_found: 'silent',
          unknown: 'silent',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
      {
        model: 'gemini-2.5-flash',
        actions: {
          terminal: 'silent',
          transient: 'silent',
          not_found: 'silent',
          unknown: 'silent',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
      {
        model: 'gemini-2.5-pro',
        isLastResort: true,
        actions: {
          terminal: 'silent',
          transient: 'silent',
          not_found: 'silent',
          unknown: 'silent',
        },
        stateTransitions: {
          terminal: 'terminal',
          transient: 'terminal',
          not_found: 'terminal',
          unknown: 'terminal',
        },
      },
    ],
  },
};
