import { X } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import ConflictForm from './ConflictForm';
import NoteForm from './NoteForm';
import styles from './EditModal.module.css';

export default function EditModal() {
  const { state, dispatch } = useApp();
  const { editTarget } = state;

  if (!editTarget) return null;

  function close() {
    dispatch({ type: 'CLOSE_EDIT' });
  }

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h2 className={styles.title}>
            {editTarget.kind === 'conflict'
              ? (editTarget.data ? 'Edit Conflict' : 'New Conflict')
              : (editTarget.data?.id ? 'Edit Note' : 'New Note')}
          </h2>
          <button className={styles.closeBtn} aria-label="Close" onClick={close}><X size={16} strokeWidth={2.2} aria-hidden="true" /></button>
        </div>
        <div className={styles.body}>
          {editTarget.kind === 'conflict'
            ? <ConflictForm initial={editTarget.data} onClose={close} />
            : <NoteForm initial={editTarget.data} onClose={close} />}
        </div>
      </div>
    </div>
  );
}
