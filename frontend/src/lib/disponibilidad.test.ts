import { disponibilidad } from "./disponibilidad";

describe("disponibilidad", () => {
  test.each([
    [100, 11, null],
    [100, 10, "ultimos"],
    [100, 1, "ultimos"],
    [100, 0, "agotado"],
    [5, 1, "ultimos"],
    [5, 2, null],
    [3, 1, "ultimos"],
  ])("capacidad %i con %i libres da %s", (capacidad, libres, esperado) => {
    expect(disponibilidad(capacidad, libres)).toBe(esperado);
  });
});
