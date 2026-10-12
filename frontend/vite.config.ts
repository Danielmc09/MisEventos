/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import ofuscador from "vite-plugin-javascript-obfuscator";

// Ofuscación liviana. Las opciones pesadas quedan apagadas a propósito: agrandan el bundle y lo
// vuelven más lento, y debugProtection construye código con el constructor de Function, que la CSP
// de nginx bloquea (sin 'unsafe-eval'). El string array usa base64 con un decodificador propio;
// rc4 queda fuera por tamaño y velocidad, no por la CSP.
const opcionesOfuscacion = {
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
