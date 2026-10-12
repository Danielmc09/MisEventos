import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { registrarRouter } from "./api/navegacion";
import { Encabezado } from "./components/Encabezado";
import { RutaProtegida } from "./components/RutaProtegida";
import { ProveedorAvisos } from "./components/ui/Avisos";
import { Spinner } from "./components/ui/Spinner";
import { useRefrescarSesion } from "./lib/useRefrescarSesion";

const Inicio = lazy(() => import("./pages/Inicio/Inicio"));
const Login = lazy(() => import("./pages/Login/Login"));
const Registro = lazy(() => import("./pages/Registro/Registro"));
const EventoDetalle = lazy(() => import("./pages/EventoDetalle/EventoDetalle"));
const EventoNuevo = lazy(() => import("./pages/EventoNuevo/EventoNuevo"));
const EventoEditar = lazy(() => import("./pages/EventoEditar/EventoEditar"));
const Perfil = lazy(() => import("./pages/Perfil/Perfil"));
const AdminUsuarios = lazy(() => import("./pages/AdminUsuarios/AdminUsuarios"));
const NoEncontrada = lazy(() => import("./pages/NoEncontrada/NoEncontrada"));
const CambiarContrasena = lazy(() => import("./pages/CambiarContrasena/CambiarContrasena"));

export default function App() {
  useRefrescarSesion();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  useEffect(
    () => registrarRouter({ navigate, actual: pathname + search }),
    [navigate, pathname, search],
  );

  return (
    <ProveedorAvisos>
      <Encabezado />
      <Suspense
        fallback={
          <div className="flex justify-center p-10">
            <Spinner />
          </div>
        }
      >
        <Routes>
          <Route path="/" element={<Inicio />} />
          <Route path="/login" element={<Login />} />
          <Route path="/registro" element={<Registro />} />
          <Route path="/eventos/:id" element={<EventoDetalle />} />
          <Route element={<RutaProtegida />}>
            <Route path="/eventos/nuevo" element={<EventoNuevo />} />
            <Route path="/eventos/:id/editar" element={<EventoEditar />} />
            <Route path="/perfil" element={<Perfil />} />
            <Route path="/admin/usuarios" element={<AdminUsuarios />} />
            <Route path="/cambiar-contrasena" element={<CambiarContrasena />} />
          </Route>
          <Route path="*" element={<NoEncontrada />} />
        </Routes>
      </Suspense>
    </ProveedorAvisos>
  );
}
