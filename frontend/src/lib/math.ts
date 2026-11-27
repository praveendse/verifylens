/** Running start offsets: [3, 5, 2] -> [0, 3, 8]. Pure, so it is safe during render. */
export function startOffsets(lengths: number[]): number[] {
  return lengths.map((_, i) => lengths.slice(0, i).reduce((sum, n) => sum + n, 0));
}

/** "Nice" axis ticks (0, 2, 4, 6 ...) covering 0..max in about three steps. */
export function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / 3;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map(m => m * pow).find(s => s >= raw) ?? raw;
  const top = Math.ceil(max / step) * step;
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
}
