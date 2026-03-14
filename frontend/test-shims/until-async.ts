type UntilOptions = {
  interval?: number;
  timeout?: number;
};

export async function until<T>(
  check: () => T | Promise<T>,
  options: UntilOptions = {}
): Promise<T> {
  const interval = options.interval ?? 50;
  const timeout = options.timeout ?? 5000;
  const startedAt = Date.now();

  for (;;) {
    try {
      return await check();
    } catch (error) {
      if (Date.now() - startedAt >= timeout) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, interval));
    }
  }
}
