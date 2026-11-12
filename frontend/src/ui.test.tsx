import { expect, test } from 'vitest';
import { formatRange, isoToZoned, weekStart, zonedToIso } from './ui';

test('converte horário local da clínica para ISO com deslocamento explícito', () => {
  expect(zonedToIso('2026-11-15T12:00', 'America/Sao_Paulo')).toBe('2026-11-15T12:00:00-03:00');
  expect(zonedToIso('2026-07-01T09:30', 'Europe/Lisbon')).toBe('2026-07-01T09:30:00+01:00');
  expect(zonedToIso('2026-01-10T08:00', 'America/New_York')).toBe('2026-01-10T08:00:00-05:00');
  expect(isoToZoned('2026-11-15T15:00:00Z', 'America/Sao_Paulo')).toBe('2026-11-15T12:00');
});

test('semana da agenda começa na segunda-feira', () => {
  expect(weekStart('2026-11-09')).toBe('2026-11-09');
  expect(weekStart('2026-11-12')).toBe('2026-11-09');
  expect(weekStart('2026-11-15')).toBe('2026-11-09');
  expect(formatRange('2026-11-09', '2026-11-15')).toBe('9 – 15 de nov. de 2026');
});
