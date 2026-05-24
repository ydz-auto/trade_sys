export const isMockMode = import.meta.env.VITE_USE_MOCK_API === 'true'

export function getMockValue<T>(mockValue: T, realValue: T | undefined | null): T | undefined {
  if (isMockMode) {
    return mockValue
  }
  return realValue ?? undefined
}

export function requireRealData<T>(realValue: T | undefined | null, fallbackMessage?: string): T {
  if (!isMockMode && (realValue === undefined || realValue === null)) {
    console.warn(fallbackMessage || 'Real data not available, consider enabling mock mode')
  }
  return realValue as T
}
