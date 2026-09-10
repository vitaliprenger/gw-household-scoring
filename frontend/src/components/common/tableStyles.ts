import { SxProps, Theme } from '@mui/material';

/** Klasse für jede zweite Zeile einer DataGrid-Tabelle (Zebrastreifen). */
export const ZEBRA_ROW_CLASS = 'zebra-row';

/**
 * Vergibt die Zebra-Klasse anhand der Position innerhalb der aktuellen Seite,
 * damit die Streifen auch nach Sortieren, Filtern und Blättern stimmen.
 */
export const zebraRowClassName = (params: { indexRelativeToCurrentPage: number }): string =>
  params.indexRelativeToCurrentPage % 2 === 1 ? ZEBRA_ROW_CLASS : '';

/**
 * Zebrastreifen für DataGrid. Der Hover-Zustand bleibt auf gestreiften Zeilen
 * sichtbar, weil er dort mit höherer Spezifität kräftiger gesetzt wird.
 */
export const zebraGridSx = {
  [`& .MuiDataGrid-row.${ZEBRA_ROW_CLASS}`]: {
    backgroundColor: 'action.hover',
  },
  [`& .MuiDataGrid-row.${ZEBRA_ROW_CLASS}:hover`]: {
    backgroundColor: 'action.selected',
  },
} satisfies SxProps<Theme>;

/** Klasse für Zeilen einer `<Table>`, die von den Streifen ausgenommen bleiben (z. B. Summenzeilen). */
export const NO_ZEBRA_ROW_CLASS = 'no-zebra-row';

/** Zebrastreifen für einfache MUI-Tabellen (`<Table>`). */
export const zebraTableSx = {
  [`& tbody tr:nth-of-type(odd):not(.${NO_ZEBRA_ROW_CLASS})`]: {
    backgroundColor: 'action.hover',
  },
} satisfies SxProps<Theme>;
