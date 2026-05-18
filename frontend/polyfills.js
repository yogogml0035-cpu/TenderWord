/* eslint-disable @typescript-eslint/no-require-imports */
const { TextDecoder, TextEncoder } = require('util');
const streamWeb = require('stream/web');

class MessageChannelMock {
  constructor() {
    const port1 = { onmessage: null, postMessage: () => {} };
    const port2 = {
      onmessage: null,
      postMessage: () => {
        if (typeof port1.onmessage === 'function') {
          const handler = port1.onmessage;
          setTimeout(() => handler({ data: null }), 0);
        }
      },
    };

    this.port1 = port1;
    this.port2 = port2;
  }
}

const g = globalThis;

if (typeof g.TextDecoder === 'undefined') {
  g.TextDecoder = TextDecoder;
}
if (typeof g.TextEncoder === 'undefined') {
  g.TextEncoder = TextEncoder;
}

if (typeof g.MessageChannel === 'undefined') {
  g.MessageChannel = MessageChannelMock;
}

if (typeof g.ReadableStream === 'undefined') {
  g.ReadableStream = streamWeb.ReadableStream;
}
if (typeof g.WritableStream === 'undefined') {
  g.WritableStream = streamWeb.WritableStream;
}
if (typeof g.TransformStream === 'undefined') {
  g.TransformStream = streamWeb.TransformStream;
}
if (typeof g.ByteLengthQueuingStrategy === 'undefined') {
  g.ByteLengthQueuingStrategy = streamWeb.ByteLengthQueuingStrategy;
}
if (typeof g.CountQueuingStrategy === 'undefined') {
  g.CountQueuingStrategy = streamWeb.CountQueuingStrategy;
}
