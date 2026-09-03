import { invoke } from '@tauri-apps/api/core'

/**
 * Call the Rust backend hello command.
 * @param {string} name
 * @returns {Promise<string>}
 */
export async function hello (name) {
  return await invoke('hello', { name })
}
