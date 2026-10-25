// Pure helpers for the per-account workspace state.

// A business that only existed on this device was just created on the server and got a new id.
// Replace the old business with the server one and move the data kept per business id.
// Recommendation ticks (state.recs) are dropped because they referred to the old demo list.
export function migrateBusinessId(state, oldId, newBusiness) {
  const move = (map) => {
    if (!map || !(oldId in map)) return map;
    const { [oldId]: value, ...rest } = map;
    return { ...rest, [newBusiness.id]: value };
  };
  const { [oldId]: _dropped, ...recs } = state.recs || {};
  return {
    ...state,
    businesses: state.businesses.map((b) => (b.id === oldId ? newBusiness : b)),
    selected: state.selected === oldId ? newBusiness.id : state.selected,
    profiles: move(state.profiles),
    uploads: move(state.uploads),
    recs,
  };
}
