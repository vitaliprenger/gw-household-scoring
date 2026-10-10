import { GridColDef, GridValidRowModel } from '@mui/x-data-grid';

/**
 * Spalten einer DataGrid-Tabelle für das Handy: Die Felder aus `front` stehen
 * in dieser Reihenfolge vorn, alle übrigen folgen in ihrer bisherigen
 * Reihenfolge und bleiben durch seitliches Wischen erreichbar. `overrides`
 * passt einzelne Spalten an (z. B. schmalere Breite, kürzere Überschrift).
 */
export function mobileColumns<R extends GridValidRowModel>(
  columns: GridColDef<R>[],
  front: string[],
  overrides: Record<string, Partial<GridColDef<R>>> = {},
): GridColDef<R>[] {
  const adjusted = columns.map(
    (column) => ({ ...column, ...overrides[column.field] }) as GridColDef<R>,
  );
  return [
    ...front.flatMap((field) => adjusted.filter((column) => column.field === field)),
    ...adjusted.filter((column) => !front.includes(column.field)),
  ];
}

/** Zentriert den Zelleninhalt auch dann senkrecht, wenn die Zeile mit ihrem Inhalt wächst. */
export const flexCell = <R extends GridValidRowModel>(column: GridColDef<R>): GridColDef<R> =>
  ({ ...column, display: 'flex' });

/**
 * DataGrid-Eigenschaften für das Handy: Das Menü-Symbol kostet in jedem
 * Spaltenkopf Platz; Sortieren durch Tippen auf den Kopf bleibt.
 */
export const mobileGridProps = { disableColumnMenu: true } as const;

/** Wie `mobileGridProps`; zusätzlich wachsen die Zeilen mit umbrechendem Inhalt. */
export const mobileWrappingGridProps = {
  ...mobileGridProps,
  getRowHeight: () => 'auto' as const,
};
