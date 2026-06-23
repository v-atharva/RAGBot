#!/usr/bin/env bun
/**
 * One-command dev launcher: starts the FastAPI backend and the Next.js frontend together,
 * with prefixed, colour-coded output and a clean shutdown on Ctrl-C.
 *
 *   bun dev
 */
import { spawn } from "bun";

const ROOT = `${import.meta.dir}/..`;
const HOME = process.env.HOME ?? "";

// Ensure the home-dir toolchains (uv venv, node) are visible to child processes.
const PATH = [`${HOME}/.bun/bin`, `${HOME}/.local/node/bin`, `${HOME}/.local/bin`, process.env.PATH]
  .filter(Boolean)
  .join(":");
const env = { ...process.env, PATH, FORCE_COLOR: "1" };

const RESET = "\x1b[0m";
const DIM = "\x1b[2m";

type Service = { name: string; color: string; cmd: string[]; cwd: string };

const services: Service[] = [
  {
    name: "api",
    color: "\x1b[36m", // cyan
    cmd: [`${ROOT}/.venv/bin/uvicorn`, "ragbot.api.app:app", "--port", "8000", "--reload"],
    cwd: ROOT,
  },
  {
    name: "web",
    color: "\x1b[35m", // magenta
    cmd: ["bun", "run", "dev"],
    cwd: `${ROOT}/web`,
  },
];

function pipePrefixed(stream: ReadableStream<Uint8Array>, name: string, color: string) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  (async () => {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) console.log(`${color}${name.padEnd(3)}${RESET} ${DIM}│${RESET} ${line}`);
    }
    if (buffer) console.log(`${color}${name.padEnd(3)}${RESET} ${DIM}│${RESET} ${buffer}`);
  })();
}

// Non-fatal heads-up if Ollama isn't reachable (lecture-only still works without it).
try {
  await fetch("http://localhost:11434/api/tags");
} catch {
  console.log(`${DIM}! Ollama not reachable on :11434 — run \`ollama serve\` for course-wide mode.${RESET}`);
}

const children = services.map((s) => {
  const child = spawn({ cmd: s.cmd, cwd: s.cwd, env, stdout: "pipe", stderr: "pipe" });
  pipePrefixed(child.stdout, s.name, s.color);
  pipePrefixed(child.stderr, s.name, s.color);
  return child;
});

console.log(`${DIM}Starting…  api → http://localhost:8000   web → http://localhost:3000${RESET}`);

let shuttingDown = false;
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const c of children) c.kill();
  process.exit(code);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

// If either service exits, tear the other down too.
await Promise.race(children.map((c) => c.exited));
console.log(`${DIM}A service exited — shutting down the other.${RESET}`);
shutdown(1);
