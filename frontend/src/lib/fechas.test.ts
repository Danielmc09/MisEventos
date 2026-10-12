import { diaMesBogota, etiquetaDia } from "./fechas";

describe("diaMesBogota", () => {
  test("da el día y el mes abreviado de Bogotá, no los de UTC", () => {
    expect(diaMesBogota("2026-10-11T01:30:00Z")).toEqual({ dia: "10", mes: "Oct" });
  });

  test("un día de un solo dígito va sin cero a la izquierda", () => {
    expect(diaMesBogota("2026-11-02T15:00:00Z")).toEqual({ dia: "2", mes: "Nov" });
  });
});

describe("etiquetaDia", () => {
  test("solo la primera letra va en mayúscula", () => {
    expect(etiquetaDia("2026-11-02T15:00:00Z")).toBe("Lunes, 2 de noviembre de 2026");
  });

  test("usa el día de Bogotá y no el de UTC", () => {
    expect(etiquetaDia("2026-11-03T02:00:00Z")).toBe("Lunes, 2 de noviembre de 2026");
  });
});
