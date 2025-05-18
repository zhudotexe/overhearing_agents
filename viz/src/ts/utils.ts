export function sorted<T>(arr: Iterable<T> | T[], compareFn?: (a: T, b: T) => number): T[] {
  return [...arr].sort(compareFn);
}

export function base64ToInt16Array(base64: string): Int16Array {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return new Int16Array(bytes.buffer);
}
