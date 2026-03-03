// @ts-nocheck

/**
 * Polyfills for Jest/JSDOM environment
 * This file MUST be loaded before any other setup files
 * Add this to setupFiles in jest.config.ts
 */

const { TextDecoder, TextEncoder } = require('util');

// @ts-ignore
if (typeof global.TextDecoder === 'undefined') {
  // @ts-ignore
  global.TextDecoder = TextDecoder;
}
// @ts-ignore
if (typeof global.TextEncoder === 'undefined') {
  // @ts-ignore
  global.TextEncoder = TextEncoder;
}

// Polyfill for MessageChannel/MessagePort - required by undici
const { MessageChannel, MessagePort } = require('worker_threads');

// @ts-ignore
if (typeof global.MessageChannel === 'undefined') {
  // @ts-ignore
  global.MessageChannel = MessageChannel;
}
// @ts-ignore
if (typeof global.MessagePort === 'undefined') {
  // @ts-ignore
  global.MessagePort = MessagePort;
}

// Polyfill for ReadableStream and related APIs
const streamWeb = require('stream/web');

// @ts-ignore
if (typeof global.ReadableStream === 'undefined') {
  // @ts-ignore
  global.ReadableStream = streamWeb.ReadableStream;
}
// @ts-ignore
if (typeof global.TransformStream === 'undefined') {
  // @ts-ignore
  global.TransformStream = streamWeb.TransformStream;
}
// @ts-ignore
if (typeof global.ByteLengthQueuingStrategy === 'undefined') {
  // @ts-ignore
  global.ByteLengthQueuingStrategy = streamWeb.ByteLengthQueuingStrategy;
}
// @ts-ignore
if (typeof global.CountQueuingStrategy === 'undefined') {
  // @ts-ignore
  global.CountQueuingStrategy = streamWeb.CountQueuingStrategy;
}

// Load undici and set up fetch polyfills
const undici = require('undici');

// @ts-ignore
if (typeof global.Response === 'undefined') {
  // @ts-ignore
  global.Response = undici.Response;
}
// @ts-ignore
if (typeof global.Headers === 'undefined') {
  // @ts-ignore
  global.Headers = undici.Headers;
}
// @ts-ignore
if (typeof global.Request === 'undefined') {
  // @ts-ignore
  global.Request = undici.Request;
}
