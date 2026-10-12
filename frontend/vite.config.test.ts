import type { PluginOption, UserConfig, UserConfigFnObject } from "vite";
import ofuscador from "vite-plugin-javascript-obfuscator";
import { beforeEach, describe, expect, it, vi } from "vitest";
import configuracion from "./vite.config";

vi.mock("vite-plugin-javascript-obfuscator", () => ({
  default: vi.fn(() => ({ name: "plugin-de-ofuscacion" })),
}));

type ArgumentosDelPlugin = {
  include: RegExp[];
  exclude: RegExp[];
  apply?: unknown;
  options: Record<string, unknown>;
};

function resolver(command: "build" | "serve"): UserConfig {
  return (configuracion as UserConfigFnObject)({ command, mode: "production" });
}

function nombresDePlugins(config: UserConfig): string[] {
  return (config.plugins ?? [])
    .flat(Infinity as 1)
    .map((plugin: PluginOption) =>
      plugin && typeof plugin === "object" && "name" in plugin ? plugin.name : "",
    );
}

function argumentosEnElBuild(): ArgumentosDelPlugin {
  resolver("build");
  return vi.mocked(ofuscador).mock.calls[0][0] as unknown as ArgumentosDelPlugin;
}

describe("configuración de Vite", () => {
  beforeEach(() => {
    vi.mocked(ofuscador).mockClear();
  });

  it("en el build incluye el plugin de ofuscación", () => {
    expect(nombresDePlugins(resolver("build"))).toContain("plugin-de-ofuscacion");
  });

  it("en desarrollo no incluye ni crea el plugin de ofuscación", () => {
    expect(nombresDePlugins(resolver("serve"))).not.toContain("plugin-de-ofuscacion");
    expect(ofuscador).not.toHaveBeenCalled();
  });

  it("no publica source maps", () => {
    expect(resolver("build").build?.sourcemap).toBe(false);
  });

  it("ofusca solo el código de la app y deja afuera node_modules", () => {
    const { include, exclude } = argumentosEnElBuild();
    expect(include.some((patron) => patron.test("/app/src/pages/Login/Login.tsx"))).toBe(true);
    expect(include.some((patron) => patron.test("/app/node_modules/react/index.js"))).toBe(false);
    expect(exclude.some((patron) => patron.test("/app/node_modules/react/index.js"))).toBe(true);
  });

  it("le pasa al plugin las opciones pesadas apagadas", () => {
    expect(argumentosEnElBuild().options).toMatchObject({
      selfDefending: false,
      debugProtection: false,
      controlFlowFlattening: false,
      deadCodeInjection: false,
    });
  });

  it("le pasa al plugin nombres hexadecimales y string array en base64, sin rc4", () => {
    const { options } = argumentosEnElBuild();
    expect(options.identifierNamesGenerator).toBe("hexadecimal");
    expect(options.stringArray).toBe(true);
    expect(options.stringArrayEncoding).toEqual(["base64"]);
  });

  it("le pasa al plugin ignoreImports, para que las pantallas con carga diferida carguen", () => {
    expect(argumentosEnElBuild().options.ignoreImports).toBe(true);
  });

  it("deja la decisión de build o serve en la config y no en el plugin", () => {
    expect(argumentosEnElBuild().apply).toBeUndefined();
  });
});
