# TODO

## Cycle 2026-07-08 — CLOSED

- [x] A-001 GSS Trust Plane (mock GSS + HIL)
- [x] A-002 Sustainability + community + personal uplift
- [x] Integrity manifests (deliverables / top-level / related)
- [x] Hash gap audit rewrite for legacy checksums
- [x] A-003 RAARA provenance seal + project cycle archive

## Next cycle (when resumed)

### Primary victory target (2026-07-09 ranking + voice-memo lock)
- [ ] **IHEP** (`ihep/`): ship community-useful MVP aftercare app
  - Domain fit (memo): right-resource routing, community-based support, reduce wrong-channel emergencies / unnecessary institutionalization
  - Build method (memo): **promotion gate** — objects only enter house/production after sandbox validation; closed registries; no open append-only ledger chaos with AI agents
  - Evidence: largest patient/community-facing surface; auth/UI built; GCP deploy path; gap is mock→real + promotion discipline, not greenfield
  - Gateway: `Jarmacz.com`
  - **Feasibility (IHEP-FEAS-001):** full vision FAIL as one ship (F≈3.2); memo-aligned MVP Conditional GO (F_joint≈6.65).
  - **In progress 2026-07-09:** K007 canonize done; promote bus + seed + resource hub wired under `ihep-application/`
- [x] Wire IHEP resource write path to **earn-promotion** pattern (sandbox → verify → promote); public API reads promoted only

### Secondary / not primary for community-abroad goal
- [ ] king (ClarityAir demo): complete as commercial IAQ demo — not primary community abroad vehicle
- [ ] pitchfork (Sounion): production-advanced institutional finance — low community-abroad fit
- [ ] knockout-eda-website: specs complete; implementation still open

### Platform residuals (sovereign stack; not the community-app gap)
- [ ] Real GSSAPI / Apple GSS.framework adapter
- [ ] NASN firmware join → trust plane
- [ ] Pixel 9 SIP lab under trust gate
- [ ] operator.toml personal uplift weights
- [ ] Optional RAARA v2 supersession (new provenance cycle)

### Voice note
- [ ] Export/transcribe `20260708 215001.m4a` (TCC blocked agent read; user export or FDA for Terminal/Grok)

## Commands (reference)

```bash
cd provenance-archive
python3 scripts/seal_provenance.py
python3 scripts/seal_provenance.py --verify

cd integrity-manifest
python3 scripts/generate_hashes.py --scope deliverables
python3 scripts/generate_hashes.py --verify ../MANIFEST_DELIVERABLES.json
python3 scripts/hash_gap_audit.py -v
```
