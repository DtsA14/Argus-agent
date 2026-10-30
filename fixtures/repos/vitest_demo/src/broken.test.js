import { expect, test } from 'vitest'
import { missing } from './missing.js'

test('never runs', () => { expect(missing).toBe(1) })
