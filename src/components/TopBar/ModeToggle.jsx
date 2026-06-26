import { useApp } from '../../context/AppContext';
import styles from './ModeToggle.module.css';

export default function ModeToggle() {
  const { state, dispatch } = useApp();
  const isEdit = state.mode === 'edit';

  return (
    <div className={styles.toggle}>
      <button
        className={`${styles.btn} ${!isEdit ? styles.active : ''}`}
        onClick={() => dispatch({ type: 'SET_MODE', payload: 'view' })}
      >
        View
      </button>
      <button
        className={`${styles.btn} ${isEdit ? styles.activeEdit : ''}`}
        onClick={() => dispatch({ type: 'SET_MODE', payload: 'edit' })}
      >
        Edit
      </button>
    </div>
  );
}
