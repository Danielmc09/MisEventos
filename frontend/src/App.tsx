import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { Spinner } from "./components/ui/Spinner";

const Inicio = lazy(() => import("./pages/Inicio/Inicio"));

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center p-10">
          <Spinner />
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<Inicio />} />
      </Routes>
    </Suspense>
  );
}
