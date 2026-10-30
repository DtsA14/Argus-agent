export function boom() {
  const missing = null
  return missing.value
}

export async function boomLater() {
  await null
  return boom()
}
