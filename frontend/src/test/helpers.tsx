import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation, type Location } from "react-router-dom";
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
  const { pathname, search, state } = useLocation();
  return (
    <>
      <output aria-label="ubicación">{pathname + search}</output>
      <output aria-label="estado">{JSON.stringify(state)}</output>
    </>
  );
}

/** Monta las rutas dadas (`[path, elemento]`) en un MemoryRouter y muestra la ubicación actual. */
export function montar(inicial: string | Partial<Location>, rutas: [string, ReactNode][]) {
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

export const evento: components["schemas"]["EventoSalida"] = {
  id: "0b8f3c52-6a1e-4c1d-9d57-3f2a1b7c9e10",
  name: "PyCon Bogotá",
  description: null,
  location: "Ágora Bogotá",
  start_at: "2026-10-11T01:30:00Z",
  end_at: "2026-10-11T09:30:00Z",
  capacity: 100,
  status: "PUBLISHED",
  organizer_id: "5d1c7a3e-9b2f-4e8a-8c46-1a2b3c4d5e6f",
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
  registered_count: 0,
  available_spots: 100,
  is_finished: false,
};
