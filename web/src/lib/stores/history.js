import { writable, get } from 'svelte/store';
import { transcript, boardStream } from './connection.js';

// ── Session persistence ─────────────────────────────────────────────────────

const STORAGE_KEY = 'minerva_session_history';
const MAX_SESSIONS = 10;

export const sessionHistory = writable(loadHistory());

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(sessions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
  } catch {}
}

sessionHistory.subscribe(sessions => {
  saveHistory(sessions);
});

/**
 * Save the current transcript and board as a session snapshot.
 */
export function saveCurrentSession(name) {
  const transcriptData = get(transcript);
  const boardData = get(boardStream);

  if (transcriptData.length === 0 && boardData.length === 0) return null;

  const session = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    name: name || `Session ${new Date().toLocaleString()}`,
    timestamp: Date.now(),
    messageCount: transcriptData.filter(e => e.role === 'user' || e.role === 'assistant').length,
    transcript: transcriptData,
    board: boardData,
  };

  sessionHistory.update(sessions => [session, ...sessions].slice(0, MAX_SESSIONS));
  return session;
}

/**
 * Export current conversation as Markdown.
 */
export function exportAsMarkdown() {
  const transcriptData = get(transcript);
  const boardData = get(boardStream);
  const lines = [];

  lines.push(`# Minerva Conversation`);
  lines.push(`*${new Date().toLocaleString()}*\n`);

  // Transcript
  if (transcriptData.length > 0) {
    lines.push(`## Conversation\n`);
    for (const entry of transcriptData) {
      if (entry.type === 'tool_call') {
        lines.push(`> **Tool:** \`${entry.tool}\` ${entry.tool_args ? JSON.stringify(entry.tool_args) : ''}`);
      } else if (entry.type === 'tool_result') {
        lines.push(`> **Result:** \`${entry.tool}\` ${entry.tool_result || ''}`);
      } else if (entry.role === 'user') {
        lines.push(`**You:** ${entry.text}\n`);
      } else if (entry.role === 'assistant') {
        lines.push(`**Minerva:** ${entry.text}\n`);
      }
    }
  }

  // Board posts
  if (boardData.length > 0) {
    lines.push(`\n## Board Posts\n`);
    for (const post of boardData) {
      const time = new Date(post.timestamp * 1000).toLocaleTimeString();
      lines.push(`### ${post.author} (${time})\n`);
      lines.push(post.content);
      lines.push('');
    }
  }

  return lines.join('\n');
}

/**
 * Trigger a markdown file download.
 */
export function downloadConversation() {
  const md = exportAsMarkdown();
  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `minerva-${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Delete a saved session by ID.
 */
export function deleteSession(sessionId) {
  sessionHistory.update(sessions => sessions.filter(s => s.id !== sessionId));
}
