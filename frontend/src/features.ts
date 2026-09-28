export function providerFeaturesEnabled(value: string | boolean | undefined): boolean {
  return value === true || value === 'true'
}

// The release build is template-only unless the operator opts in at build time.
export const PROVIDER_FEATURES_ENABLED = import.meta.env.MODE === 'test'
  || providerFeaturesEnabled(import.meta.env.VITE_ENABLE_PROVIDER_FEATURES)
