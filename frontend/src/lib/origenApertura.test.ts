import userEvent from "@testing-library/user-event";
import { origenDeApertura } from "./origenApertura";

function rect(left: number, top: number, width: number, height: number) {
  return { left, top, width, height, right: left + width, bottom: top + height } as DOMRect;
}

test("el panel crece desde el centro del elemento que lo abrió", async () => {
  const abrir = document.createElement("button");
  document.body.append(abrir);
  vi.spyOn(abrir, "getBoundingClientRect").mockReturnValue(rect(300, 200, 100, 40));
  const panel = document.createElement("div");
  vi.spyOn(panel, "getBoundingClientRect").mockReturnValue(rect(100, 50, 500, 400));

  await userEvent.click(abrir);

  // Centro del botón: (350, 220). Relativo al panel: (250, 170).
  expect(origenDeApertura(panel)).toBe("250px 170px");
});

test("si lo abrió el teclado, también sale del elemento que lo abrió", async () => {
  const abrir = document.createElement("button");
  document.body.append(abrir);
  vi.spyOn(abrir, "getBoundingClientRect").mockReturnValue(rect(0, 0, 20, 20));
  const panel = document.createElement("div");
  vi.spyOn(panel, "getBoundingClientRect").mockReturnValue(rect(0, 0, 500, 400));
  abrir.focus();

  await userEvent.keyboard("{Enter}");

  expect(origenDeApertura(panel)).toBe("10px 10px");
});
