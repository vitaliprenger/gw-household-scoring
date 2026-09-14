import React from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, Box, Link,
  Table, TableHead, TableBody, TableRow, TableCell, TableContainer, Paper, Divider,
} from '@mui/material';
import Markdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
// Einzige Quelle des Handbuchs: dieselbe Datei, die im Repository unter docs/ liegt.
import manual from '../../../../docs/Benutzerhandbuch.md?raw';

/** Text eines React-Knotens, z. B. einer Überschrift mit Hervorhebungen. */
function textOf(node: React.ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  if (React.isValidElement<{ children?: React.ReactNode }>(node)) return textOf(node.props.children);
  return '';
}

/**
 * Anker einer Überschrift. Die Nummerierung („4. “) zählt nicht mit, damit ein
 * Verweis auf einen Abschnitt das Umsortieren des Handbuchs übersteht.
 */
export function helpSectionId(heading: string): string {
  const slug = heading
    .replace(/^\s*\d+\.\s*/, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-|-$/g, '');
  return `hilfe-${slug}`;
}

const heading = (variant: 'h5' | 'h6' | 'subtitle1', mt: number): Components['h1'] =>
  ({ children }) => (
    <Typography id={helpSectionId(textOf(children))} variant={variant} sx={{ mt, mb: 1, fontWeight: 600, scrollMarginTop: 8 }}>
      {children}
    </Typography>
  );

const components: Components = {
  h1: heading('h5', 0),
  h2: heading('h6', 3),
  h3: heading('subtitle1', 2),
  p: ({ children }) => <Typography variant="body2" sx={{ mb: 1.5 }}>{children}</Typography>,
  li: ({ children }) => <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>{children}</Typography>,
  hr: () => <Divider sx={{ my: 2 }} />,
  a: ({ href, children }) => {
    if (href?.startsWith('#')) {
      return (
        <Link href={href} onClick={(e) => {
          e.preventDefault();
          document.getElementById(helpSectionId(decodeURIComponent(href.slice(1))))?.scrollIntoView({ behavior: 'smooth' });
        }}>{children}</Link>
      );
    }
    return <Link href={href} target="_blank" rel="noopener noreferrer">{children}</Link>;
  },
  table: ({ children }) => (
    <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
      <Table size="small">{children}</Table>
    </TableContainer>
  ),
  thead: ({ children }) => <TableHead>{children}</TableHead>,
  tbody: ({ children }) => <TableBody>{children}</TableBody>,
  tr: ({ children }) => <TableRow>{children}</TableRow>,
  th: ({ children }) => <TableCell sx={{ fontWeight: 600 }}>{children}</TableCell>,
  td: ({ children }) => <TableCell sx={{ verticalAlign: 'top' }}>{children}</TableCell>,
};

interface Props {
  open: boolean;
  onClose: () => void;
  /** Überschrift (ohne Nummer), bei der das Handbuch geöffnet wird; sonst oben. */
  section?: string;
}

export default function HelpDialog({ open, onClose, section }: Props) {
  const scrollToSection = () => {
    if (section) document.getElementById(helpSectionId(section))?.scrollIntoView();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth scroll="paper"
      slotProps={{ transition: { onEntered: scrollToSection } }}>
      <DialogTitle>Hilfe</DialogTitle>
      <DialogContent dividers>
        <Box>
          <Markdown remarkPlugins={[remarkGfm]} components={components}>{manual}</Markdown>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Schließen</Button>
      </DialogActions>
    </Dialog>
  );
}
