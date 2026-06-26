export const initialState = {
  view: 'map',
  mode: 'view',
  mapFilters: { type: 'all', minSeverity: 1, ongoingOnly: false },
  timelineYear: 2026,
  isPlaying: false,
  selectedCountryId: null,
  focusedConflictId: null,
  activePanel: null,
  editTarget: null,
  conflicts: [],
  countries: [],
  searchQuery: '',
  isLoading: true,
  showGraphView: false,
  showDataPanel: false,
};

export function appReducer(state, action) {
  switch (action.type) {
    case 'SET_VIEW':
      return { ...state, view: action.payload };
    case 'SET_MAP_FILTERS':
      return { ...state, mapFilters: { ...state.mapFilters, ...action.payload } };
    case 'RESET_MAP_FILTERS':
      return { ...state, mapFilters: { type: 'all', minSeverity: 1, ongoingOnly: false } };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_CONFLICTS':
      return { ...state, conflicts: action.payload };
    case 'SET_COUNTRIES':
      return { ...state, countries: action.payload };
    case 'SET_MODE':
      return { ...state, mode: action.payload };
    case 'SET_TIMELINE_YEAR':
      return { ...state, timelineYear: action.payload };
    case 'SET_PLAYING':
      return { ...state, isPlaying: action.payload };
    case 'SELECT_COUNTRY': {
      const newId = action.payload;
      // If a conflict is focused and the newly selected country is a party in it,
      // KEEP the focus — let the user read the same event from that country's eyes.
      // Otherwise reset to full country exploration.
      let keepFocus = null;
      if (state.focusedConflictId && newId) {
        const fc = state.conflicts.find((c) => c.id === state.focusedConflictId);
        if (fc && (fc.involvedCountries || []).includes(newId)) {
          keepFocus = state.focusedConflictId;
        }
      }
      return {
        ...state,
        selectedCountryId: newId,
        focusedConflictId: keepFocus,
        activePanel: newId ? 'side' : null,
        showGraphView: false,
      };
    }
    case 'CLEAR_SELECTION':
      return { ...state, selectedCountryId: null, focusedConflictId: null, activePanel: null, showGraphView: false };
    case 'FOCUS_CONFLICT':
      return { ...state, focusedConflictId: action.payload };
    case 'CLEAR_FOCUSED_CONFLICT':
      return { ...state, focusedConflictId: null };
    case 'OPEN_EDIT':
      return { ...state, editTarget: action.payload };
    case 'CLOSE_EDIT':
      return { ...state, editTarget: null };
    case 'SET_SEARCH':
      return { ...state, searchQuery: action.payload };
    case 'SHOW_GRAPH':
      return { ...state, showGraphView: true };
    case 'HIDE_GRAPH':
      return { ...state, showGraphView: false };
    case 'SHOW_DATA_PANEL':
      return { ...state, showDataPanel: true };
    case 'HIDE_DATA_PANEL':
      return { ...state, showDataPanel: false };
    default:
      return state;
  }
}
