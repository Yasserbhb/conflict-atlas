// Single source of truth for the definitions behind the atlas.
// The colors live in conflictColors.js; the *meaning* lives here.
// Referenced by the Help / Methodology page (and available to Edit forms).

// Severity measures INTENSITY, not category — a war and a genocide can both be a 5.
// The figures are rough guides for consistency, not strict legal thresholds.
export const SEVERITY_LEVELS = [
  { level: 1, label: 'Low tension',    definition: 'Political friction, a standoff, or a frozen dispute — no sustained fighting.' },
  { level: 2, label: 'Serious',        definition: 'Recurrent clashes, a militarised standoff, or state repression; casualties contained (up to the low hundreds).' },
  { level: 3, label: 'Armed conflict', definition: 'Active, organised warfare between forces — on the order of 1,000+ battle-related deaths.' },
  { level: 4, label: 'Mass atrocity',  definition: 'Deliberate large-scale killing of civilians, or war with a very heavy civilian toll — tens of thousands or more.' },
  { level: 5, label: 'Catastrophic',   definition: 'Genocide, or death and displacement on a national / existential scale — hundreds of thousands to millions.' },
];

export const TYPE_DEFINITIONS = {
  war: 'Armed conflict between the organised forces of two or more states.',
  civil_war: 'Sustained armed conflict between a state and one or more organised groups inside its own borders.',
  genocide: 'Acts committed with intent to destroy, in whole or in part, a national, ethnic, racial, or religious group (1948 Genocide Convention).',
  occupation: 'One state exercising effective control over territory outside its recognised borders, against the will of the population.',
  proxy_war: 'A conflict in which outside powers fight through local or third-party forces rather than confronting each other directly.',
  sanctions: 'Coercive economic or diplomatic measures imposed to pressure another state, short of armed force.',
  disputed_territory: 'A standing territorial claim contested by two or more states, whether or not it is currently violent.',
};

export const ROLE_DEFINITIONS = {
  aggressor: 'Initiated the use of force.',
  defender: 'Fought back against an attack on itself or an ally.',
  victim: 'Bore the harm — the population or state targeted — without being the primary combatant.',
  funder: 'Paid for, armed, or materially supplied one side.',
  proxy: 'Did the fighting on behalf of a sponsoring power.',
  occupier: 'Holds territory outside its borders by force.',
  mediator: 'Worked to negotiate, broker, or enforce a settlement.',
  sanctioner: 'Imposed economic or diplomatic pressure.',
  sanctioned: 'The target of economic or diplomatic pressure.',
};

// A conflict is made of EVENTS — the discrete moments in its timeline (shown as pins on
// the map and the sparkline/timeline in the detail panel). These are the kinds of event.
export const KIND_DEFINITIONS = {
  attack: 'A discrete strike or assault — an airstrike, raid, bombing, or terror attack.',
  battle: 'A pitched engagement between armed forces.',
  offensive: 'A broader campaign or invasion pushing into territory.',
  atrocity: 'Mass killing or grave abuse of civilians — a massacre, ethnic cleansing, chemical attack.',
  displacement: 'Mass flight, expulsion, or famine driving people from their homes.',
  ceasefire: 'A truce or pause in the fighting — reversible, not a settlement.',
  treaty: 'A formal agreement that ends or governs the conflict.',
  settlement: 'A negotiated resolution of the underlying dispute.',
  escalation: 'A step that widens or intensifies the conflict.',
  intervention: 'An outside power entering the conflict militarily.',
  sanction: 'An economic or diplomatic measure imposed as pressure.',
  annexation: 'One state formally absorbing territory it holds by force.',
  milestone: 'A turning point — a capital falling, a leader killed, independence, a war’s end.',
};

// A conflict's lifecycle phase, set by the ai-updater pipeline as it tracks a conflict over
// time (see ai-updater/config/lifecycle.yml). Most conflicts predate this field and have none —
// that's expected, not an error (see statusMeta.js's graceful-absence handling).
export const STATUS_DEFINITIONS = {
  active: 'Ongoing now — ties directly to a recent event, not just an unresolved status.',
  easing: 'De-escalating, but still happening.',
  suspended: 'An explicit, reversible pause — a ceasefire or truce, not a resolution.',
  dormant: 'Frozen and unresolved — quiet, but can flare back up at any time.',
  ended: 'Acts have ceased and there is nothing left to settle.',
  resolved: 'A positive terminal event occurred — a treaty, a withdrawal, sanctions lifted. Quiet alone is never enough to call something resolved.',
};

