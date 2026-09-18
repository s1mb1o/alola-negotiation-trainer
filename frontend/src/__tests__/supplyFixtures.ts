import type { JsonRecord, PendingOfferPublication, PreliminaryProposal } from '../types'

export const supplyTerms: JsonRecord = {
  base_price: { currency: 'EUR', minor_units: 10_950_000 },
  delivery_lots: [
    { lot_id: 'early', quantity: 10, window_start: '2026-11-05', window_end: '2026-11-07' },
    { lot_id: 'remaining', quantity: 90, window_start: '2026-11-20', window_end: '2026-11-20' },
  ],
  payment_schedule: [
    { lot_id: 'early', advance_bps: 10_000, balance_days: 0 },
    { lot_id: 'remaining', advance_bps: 5_000, balance_days: 30 },
  ],
  delivery_basis: { basis: 'DDP', destination_id: 'vector_site' },
  reserve_policy: {
    mode: 'contingent', quantity: 3, delivery_lot_id: 'remaining', use_cutoff: '2026-12-01',
    unused_payable_on: '2026-12-02', unit_price_rule: 'base_unit_ceil', diagnosis_policy_id: 'hardware-replacement-v1',
  },
}

export const supplyProposal: PreliminaryProposal = {
  proposal_id: 'proposal_example', proposal_revision: 7, proposer_participant_id: 'participant_buyer',
  proposer_role: 'buyer', status: 'active', terms: supplyTerms,
  source_event_ids: ['evt_split', 'evt_reserve'], unresolved_required_terms: [],
}

export const supplyPublication: PendingOfferPublication = {
  proposal_id: supplyProposal.proposal_id, proposal_revision: supplyProposal.proposal_revision,
  terms: supplyTerms, snapshot_digest: 'sha256:exact-snapshot', unresolved_required_terms: [],
}
