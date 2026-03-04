import { TextDecoder, TextEncoder } from 'util';
import * as streamWeb from 'stream/web';

type GlobalPolyfills = typeof globalThis & {
  TextDecoder?: typeof TextDecoder;
  TextEncoder?: typeof TextEncoder;
  MessageChannel?: unknown;
  ReadableStream?: typeof streamWeb.ReadableStream;
  WritableStream?: typeof streamWeb.WritableStream;
  TransformStream?: typeof streamWeb.TransformStream;
  ByteLengthQueuingStrategy?: typeof streamWeb.ByteLengthQueuingStrategy;
  CountQueuingStrategy?: typeof streamWeb.CountQueuingStrategy;
};

type MessagePortLike = {
  onmessage: ((event: { data: unknown }) => void) | null;
  postMessage: (data: unknown) => void;
};

class MessageChannelMock {
  port1: MessagePortLike;
  port2: MessagePortLike;

  constructor() {
    const port1: MessagePortLike = { onmessage: null, postMessage: () => {} };
    const port2: MessagePortLike = {
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

const g = globalThis as GlobalPolyfills;

if (typeof g.TextDecoder === 'undefined') {
  g.TextDecoder = TextDecoder as unknown as GlobalPolyfills['TextDecoder'];
}
if (typeof g.TextEncoder === 'undefined') {
  g.TextEncoder = TextEncoder as unknown as GlobalPolyfills['TextEncoder'];
}

if (typeof g.MessageChannel === 'undefined') {
  g.MessageChannel = MessageChannelMock as unknown as GlobalPolyfills['MessageChannel'];
}

if (typeof g.ReadableStream === 'undefined') {
  g.ReadableStream = streamWeb.ReadableStream as unknown as GlobalPolyfills['ReadableStream'];
}
if (typeof g.WritableStream === 'undefined') {
  g.WritableStream = streamWeb.WritableStream as unknown as GlobalPolyfills['WritableStream'];
}
if (typeof g.TransformStream === 'undefined') {
  g.TransformStream = streamWeb.TransformStream as unknown as GlobalPolyfills['TransformStream'];
}
if (typeof g.ByteLengthQueuingStrategy === 'undefined') {
  g.ByteLengthQueuingStrategy =
    streamWeb.ByteLengthQueuingStrategy as unknown as GlobalPolyfills['ByteLengthQueuingStrategy'];
}
if (typeof g.CountQueuingStrategy === 'undefined') {
  g.CountQueuingStrategy =
    streamWeb.CountQueuingStrategy as unknown as GlobalPolyfills['CountQueuingStrategy'];
}
