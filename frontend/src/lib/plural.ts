/** La palabra que corresponde a la cantidad: singular solo con 1. */
export const palabra = (n: number, uno: string, varios: string) => (n === 1 ? uno : varios);

/** "1 lugar", "0 lugares", "2 lugares". */
export const plural = (n: number, uno: string, varios: string) => `${n} ${palabra(n, uno, varios)}`;

/** "Queda 1 lugar", "Quedan 2 lugares": el verbo concuerda con la cantidad. */
export const quedan = (n: number, uno: string, varios: string) =>
  `${n === 1 ? "Queda" : "Quedan"} ${plural(n, uno, varios)}`;
