import { useState, useRef } from 'react';
import { useApp } from '../../context/AppContext';
import styles from './SearchBar.module.css';

export default function SearchBar() {
  const { state, dispatch } = useApp();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);

  const results = query.length >= 1
    ? state.countries
        .filter((c) =>
          c.name.toLowerCase().includes(query.toLowerCase()) ||
          (c.aliases || []).some((a) => a.toLowerCase().includes(query.toLowerCase()))
        )
        .slice(0, 8)
    : [];

  function selectCountry(id) {
    dispatch({ type: 'SELECT_COUNTRY', payload: id });
    setQuery('');
    setOpen(false);
  }

  return (
    <div className={styles.wrapper}>
      <input
        ref={inputRef}
        className={styles.input}
        placeholder="Search country…"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && results.length > 0 && (
        <ul className={styles.dropdown}>
          {results.map((c) => (
            <li key={c.id} className={styles.option} onMouseDown={() => selectCountry(c.id)}>
              <span className={styles.name}>{c.name}</span>
              <span className={styles.region}>{c.region}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
