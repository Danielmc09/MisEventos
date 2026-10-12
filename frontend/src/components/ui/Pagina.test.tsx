import { render, screen } from "@testing-library/react";
import { Pagina, TituloPagina } from "./Pagina";

test("la página es la región principal y contiene su título", () => {
  render(
    <Pagina>
      <TituloPagina>Perfil</TituloPagina>
    </Pagina>,
  );

  expect(screen.getByRole("main")).toContainElement(
    screen.getByRole("heading", { level: 1, name: "Perfil" }),
  );
});
