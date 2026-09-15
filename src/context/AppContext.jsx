import { createContext, useContext, useReducer, useEffect, useRef } from 'react';
import { appReducer, initialState } from './appReducer';
import { getAllConflicts, getAllCountries } from '../db/queries';
import { initSeed } from '../db/seed';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const playRef = useRef(null);
  const yearRef = useRef(state.timelineYear);
  yearRef.current = state.timelineYear;

  async function loadData() {
    await initSeed();
    const [conflicts, countries] = await Promise.all([getAllConflicts(), getAllCountries()]);
    dispatch({ type: 'SET_CONFLICTS', payload: conflicts });
    dispatch({ type: 'SET_COUNTRIES', payload: countries });
    dispatch({ type: 'SET_LOADING', payload: false });
  }

  useEffect(() => {
    loadData();
  }, []);

  // Timeline play mode
  useEffect(() => {
    if (state.isPlaying) {
      playRef.current = setInterval(() => {
        const next = yearRef.current + 1;
        if (next > 2026) {
          clearInterval(playRef.current);
          dispatch({ type: 'SET_PLAYING', payload: false });
        } else {
          dispatch({ type: 'SET_TIMELINE_YEAR', payload: next });
        }
      }, 150);
    } else {
      clearInterval(playRef.current);
    }
    return () => clearInterval(playRef.current);
  }, [state.isPlaying]);

  const value = {
    state,
    dispatch,
    reloadData: loadData,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside AppProvider');
  return ctx;
}
