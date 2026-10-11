import { Route, Routes } from "react-router-dom";

function Inicio() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Mis Eventos</h1>
      <p className="mt-2 text-gray-600">Gestión de eventos, sesiones, ponentes e inscripciones.</p>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
    </Routes>
  );
}
