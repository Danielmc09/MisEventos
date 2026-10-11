import { rutaSegura } from "./next";

test.each([
  "https://otro-sitio.com",
  "//otro-sitio.com",
  "javascript:alert(1)",
  "/\\otro-sitio.com",
])("rechaza %s y va a la raíz", (next) => {
  expect(rutaSegura(next)).toBe("/");
});

test.each([null, undefined, ""])("sin next (%s) va a la raíz", (next) => {
  expect(rutaSegura(next)).toBe("/");
});

test("respeta una ruta interna con su query", () => {
  expect(rutaSegura("/eventos/abc?x=1")).toBe("/eventos/abc?x=1");
});
