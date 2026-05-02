import { defineConfig } from "vite";

export default defineConfig({
  build: {
    cssMinify: true,
    minify: "esbuild",
    modulePreload: {
      polyfill: false,
    },
    reportCompressedSize: false,
    sourcemap: false,
    target: "es2022",
  },
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
    legalComments: "none",
  },
});
