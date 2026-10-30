// @vitest-environment node
import { writeFileSync } from 'node:fs'
import { expect, test } from 'vitest'

test('no network', async () => {
  await expect(fetch('http://1.1.1.1/', { signal: AbortSignal.timeout(3000) })).rejects.toThrow()
})
test('workspace is read-only', () => {
  expect(() => writeFileSync('/workspace/written_by_a_test.txt', 'x')).toThrow()
})
test('node_modules is read-only', () => {
  expect(() => writeFileSync('/node_modules/written_by_a_test.txt', 'x')).toThrow()
})
test('runs as nobody', () => { expect(process.getuid()).toBe(65534) })
