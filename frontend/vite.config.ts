/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import ofuscador from "vite-plugin-javascript-obfuscator";

// Ofuscación liviana. Las opciones pesadas quedan apagadas a propósito: agrandan el bundle, lo
// vuelven más lento y algunas usan eval, que la CSP de nginx bloquea. El string array usa base64
// (atob), que no necesita eval ni new Function; rc4 queda fuera.
export const opcionesOfuscacion = {
  identifierNamesGenerator: "hexadecimal",
  stringArray: true,
  stringArrayEncoding: ["base64"],
  stringArrayThreshold: 0.75,
  selfDefending: false,
  debugProtection: false,
  controlFlowFlattening: false,
  deadCodeInjection: false,
  sourceMap: false,
  // Sin esto el string array esconde las rutas de import() y Rollup no genera los chunks.
  ignoreImports: true,
} as const satisfies Record<string, unknown>;

export default defineConfig(({ command }) => ({
  plugins: [
    react(),
    tailwindcss(),
    // Solo en `vite build`, y solo el código de la app: nunca node_modules.
    ...(command === "build"
      ? [
          ofuscador({
            include: [/\/src\/.*\.[jt]sx?$/],
            exclude: [/node_modules/],
            options: {
              ...opcionesOfuscacion,
              stringArrayEncoding: [...opcionesOfuscacion.stringArrayEncoding],
            },
            apply: "build",
          }),
        ]
      : []),
  ],
  server: { port: 5173 },
  build: {
    // Sin source maps en producción: no se publica el código original.
    sourcemap: false,
    // Las imágenes salen como archivos con hash: una de 4 kB incrustada en el JS no se cachea aparte.
    assetsInlineLimit: (archivo) => (archivo.endsWith(".webp") ? false : undefined),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/**/*.d.ts", "src/**/*.test.{ts,tsx}", "src/setupTests.ts"],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
}));
