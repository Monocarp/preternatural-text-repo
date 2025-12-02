/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_STACK_PROJECT_ID: string
  readonly VITE_STACK_PUBLISHABLE_CLIENT_KEY: string
  readonly VITE_EDITOR_EMAILS: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
