import type { PluginOption, UserConfig, UserConfigFnObject } from "vite";
import { describe, expect, it } from "vitest";
import configuracion, { opcionesOfuscacion } from "./vite.config";

const NOMBRE_PLUGIN = "vite-plugin-javascript-obfuscator";

function resolver(command: "build" | "serve"): UserConfig {
  return typeof configuracion === "function"
    ? (configuracion as UserConfigFnObject)({ command, mode: "production" })
    : (configuracion as UserConfig);
}

function nombresDePlugins(config: UserConfig): string[] {
  return (config.plugins ?? [])
    .flat(Infinity as 1)
    .map((plugin: PluginOption) =>
      plugin && typeof plugin === "object" && "name" in plugin ? plugin.name : "",
    );
}

describe("configuración de Vite", () => {
  it("en el build incluye el plugin de ofuscación", () => {
    expect(nombresDePlugins(resolver("build"))).toContain(NOMBRE_PLUGIN);
  });

  it("en desarrollo no incluye el plugin de ofuscación", () => {
    expect(nombresDePlugins(resolver("serve"))).not.toContain(NOMBRE_PLUGIN);
  });

  it("no publica source maps", () => {
    expect(resolver("build").build?.sourcemap).toBe(false);
  });

  it("deja en false las opciones pesadas, que agrandan el bundle o necesitan eval", () => {
    expect(opcionesOfuscacion ?? {}).toMatchObject({
      selfDefending: false,
      debugProtection: false,
      controlFlowFlattening: false,
      deadCodeInjection: false,
    });
  });

  it("renombra en hexadecimal y usa string array sin codificaciones que necesiten eval", () => {
    expect(opcionesOfuscacion?.identifierNamesGenerator).toBe("hexadecimal");
    expect(opcionesOfuscacion?.stringArray).toBe(true);
    expect(opcionesOfuscacion?.stringArrayEncoding ?? []).not.toContain("rc4");
  });

  it("no ofusca los import(): si no, Rollup no ve las rutas y se rompe la carga perezosa", () => {
    expect(opcionesOfuscacion?.ignoreImports).toBe(true);
  });
});
