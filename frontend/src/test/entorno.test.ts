import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const nvmrc = readFileSync(resolve(process.cwd(), ".nvmrc"), "utf8").trim();
const nodeEsperado = nvmrc.replace(/^v/, "").split(".")[0];

describe("entorno de los tests", () => {
  it("corre en jsdom", () => {
    expect(
      typeof window !== "undefined" && window.navigator.userAgent.includes("jsdom"),
      "el entorno de Vitest tiene que ser jsdom (environment: 'jsdom')",
    ).toBe(true);
  });

  it("usa el localStorage de jsdom, el mismo en window y en el global", () => {
    expect(
      typeof window !== "undefined" && window.localStorage === globalThis.localStorage,
      "window.localStorage y el localStorage global tienen que ser el mismo objeto; en Node 25 el global propio de Node pisa al de jsdom",
    ).toBe(true);
    expect(globalThis.localStorage).toBeInstanceOf(window.Storage);
  });

  it("el localStorage escribe, lee y borra", () => {
    const s = globalThis.localStorage;
    s.setItem("entorno", "ok");
    expect(s.getItem("entorno")).toBe("ok");
    s.removeItem("entorno");
    expect(s.getItem("entorno")).toBeNull();
    s.setItem("entorno", "ok");
    s.clear();
    expect(s.length).toBe(0);
  });

  it("corre con la versión mayor de Node del .nvmrc", () => {
    expect(
      process.versions.node.split(".")[0],
      `los tests de este proyecto se corren con Node ${nodeEsperado} (.nvmrc); estás en ${process.versions.node}`,
    ).toBe(nodeEsperado);
  });
});
