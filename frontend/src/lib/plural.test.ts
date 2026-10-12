import { palabra, plural, quedan } from "./plural";

describe("plural", () => {
  test.each([
    [0, "0 lugares"],
    [1, "1 lugar"],
    [2, "2 lugares"],
  ])("con %i da %s", (n, esperado) => {
    expect(plural(n, "lugar", "lugares")).toBe(esperado);
  });
});

describe("palabra", () => {
  test.each([
    [0, "Inscritos"],
    [1, "Inscrito"],
    [2, "Inscritos"],
  ])("con %i da %s", (n, esperado) => {
    expect(palabra(n, "Inscrito", "Inscritos")).toBe(esperado);
  });
});

describe("quedan", () => {
  test.each([
    [0, "Quedan 0 lugares"],
    [1, "Queda 1 lugar"],
    [2, "Quedan 2 lugares"],
  ])("con %i da %s", (n, esperado) => {
    expect(quedan(n, "lugar", "lugares")).toBe(esperado);
  });
});
