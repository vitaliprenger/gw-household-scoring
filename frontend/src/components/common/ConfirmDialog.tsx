import {
    Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button,
} from '@mui/material';

interface ConfirmDialogProps {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    confirmColor?: 'primary' | 'warning' | 'error';
    busy?: boolean;
    onConfirm: () => void;
    onClose: () => void;
}

export default function ConfirmDialog({
    open, title, message, confirmLabel = 'Bestätigen', confirmColor = 'primary',
    busy = false, onConfirm, onClose,
}: ConfirmDialogProps) {
    return (
        <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                <DialogContentText>{message}</DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Abbrechen</Button>
                <Button variant="contained" color={confirmColor} onClick={onConfirm} disabled={busy}>
                    {busy ? 'Bitte warten...' : confirmLabel}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
