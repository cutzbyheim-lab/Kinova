#!/usr/bin/env node
// Renders one KINOVA cut with the motion layer.
//   node render.mjs --props props.json --assets <dir> --out out.mp4 [--bundle build]
// Assets (the assembled cut + B-roll files) are served from <dir> on a private
// 127.0.0.1 port for the duration of the render. Output is video-only (muted);
// the worker muxes the mixed audio back in.
import { createReadStream, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { cpus } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderMedia, selectComposition } from "@remotion/renderer";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
for (const k of ["props", "assets", "out"]) {
  if (!args[k]) {
    console.error(`missing --${k}`);
    process.exit(2);
  }
}
const assetsDir = path.resolve(args.assets);
const serveUrl = path.resolve(args.bundle ?? path.join(here, "build"));
const props = JSON.parse(readFileSync(args.props, "utf8"));
const browserExecutable = process.env.CHROME_EXECUTABLE || null;
const concurrency = Number(process.env.MOTION_CONCURRENCY) || Math.max(1, Math.min(4, Math.floor(cpus().length / 2)));

const types = { ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm" };
const server = createServer((req, res) => {
  // Only flat file names inside the assets dir.
  const name = decodeURIComponent((req.url ?? "/").split("?")[0].slice(1));
  if (!name || name.includes("/") || name.includes("\\") || name.startsWith(".")) {
    res.writeHead(404).end();
    return;
  }
  const file = path.join(assetsDir, name);
  let size;
  try {
    size = statSync(file).size;
  } catch {
    res.writeHead(404).end();
    return;
  }
  const type = types[path.extname(file).toLowerCase()] ?? "application/octet-stream";
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
  if (range) {
    const start = range[1] ? Number(range[1]) : 0;
    const end = range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    res.writeHead(206, { "Content-Type": type, "Content-Length": end - start + 1, "Content-Range": `bytes ${start}-${end}/${size}`, "Accept-Ranges": "bytes" });
    if (req.method === "HEAD") return res.end();
    createReadStream(file, { start, end }).pipe(res);
    return;
  }
  res.writeHead(200, { "Content-Type": type, "Content-Length": size, "Accept-Ranges": "bytes" });
  if (req.method === "HEAD") return res.end();
  createReadStream(file).pipe(res);
});

await new Promise((r) => server.listen(0, "127.0.0.1", r));
const { port } = server.address();
const inputProps = { ...props, baseUrl: `http://127.0.0.1:${port}/` };

try {
  const composition = await selectComposition({ serveUrl, id: "KinovaCut", inputProps, browserExecutable, logLevel: "error" });
  let last = -1;
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    crf: 18,
    pixelFormat: "yuv420p",
    muted: true,
    outputLocation: path.resolve(args.out),
    inputProps,
    concurrency,
    browserExecutable,
    logLevel: "error",
    onProgress: ({ progress }) => {
      const pct = Math.floor(progress * 100);
      if (pct >= last + 10) {
        last = pct;
        console.log(`progress ${pct}`);
      }
    },
  });
  console.log("done");
} finally {
  server.close();
}
