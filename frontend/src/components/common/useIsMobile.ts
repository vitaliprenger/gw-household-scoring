import { useMediaQuery, useTheme } from '@mui/material';

/**
 * Handy-Darstellung: unter dem Breakpoint `sm` (600 px). Alle Anpassungen für
 * schmale Bildschirme hängen an dieser einen Grenze.
 */
export const useIsMobile = (): boolean => {
  const theme = useTheme();
  return useMediaQuery(theme.breakpoints.down('sm'));
};
