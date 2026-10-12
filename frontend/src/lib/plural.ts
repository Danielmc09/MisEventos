export const palabra = (_n: number, _uno: string, varios: string) => varios;

export const plural = (n: number, uno: string, varios: string) => `${n} ${palabra(n, uno, varios)}`;

export const quedan = (n: number, uno: string, varios: string) =>
  `Quedan ${plural(n, uno, varios)}`;
