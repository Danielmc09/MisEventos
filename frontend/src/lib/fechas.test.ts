import { etiquetaDia } from "./fechas";

describe("etiquetaDia", () => {
  test("solo la primera letra va en mayúscula", () => {
    expect(etiquetaDia("2026-11-02T15:00:00Z")).toBe("Lunes, 2 de noviembre de 2026");
  });

  test("usa el día de Bogotá y no el de UTC", () => {
    expect(etiquetaDia("2026-11-03T02:00:00Z")).toBe("Lunes, 2 de noviembre de 2026");
  });
});
