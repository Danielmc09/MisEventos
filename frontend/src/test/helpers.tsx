import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { components } from "../api/schema";

export const API = "http://localhost:8000";

export const usuario: components["schemas"]["UsuarioSalida"] = {
  id: "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  email: "ana@mail.com",
  full_name: "Ana",
  role: "ATTENDEE",
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-11T15:30:00Z",
};

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="ubicación">{pathname + search}</output>;
}

/** Monta las rutas dadas (`[path, elemento]`) en un MemoryRouter y muestra la ubicación actual. */
export function montar(inicial: string, rutas: [string, ReactNode][]) {
  return render(
    <MemoryRouter initialEntries={[inicial]}>
      <Routes>
        {rutas.map(([path, element]) => (
          <Route key={path} path={path} element={element} />
        ))}
      </Routes>
      <Ubicacion />
    </MemoryRouter>,
  );
}
