import { claseGradiente } from "./gradiente";

test("el mismo nombre da siempre el mismo gradiente", () => {
  expect(claseGradiente("PyCon Bogotá")).not.toBe("");
  expect(claseGradiente("PyCon Bogotá")).toBe(claseGradiente("PyCon Bogotá"));
});

test("nombres distintos cubren más de un gradiente", () => {
  const nombres = [
    "PyCon Bogotá",
    "Feria del libro",
    "Taller de Pytest",
    "Noche de museos",
    "Hackatón",
    "Cumbre de datos",
  ];
  expect(new Set(nombres.map(claseGradiente)).size).toBeGreaterThan(1);
});

test("el gradiente se arma solo con colores del tema", () => {
  expect(claseGradiente("Hackatón")).toMatch(/^bg-linear-to-br from-[a-z-]+ to-[a-z-]+$/);
});
