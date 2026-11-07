# Published constraint sets of prior work

`ni2024_rules/<dataset>/` — the integrity constraints distributed with the
benchmark of W. Ni et al., "Automatic Data Repair: Are We Ready to Deploy?",
PVLDB 17(10), 2024 (artifacts: github.com/WelkinNi/Automatic-Data-Repair,
folder `data_with_rules/`), copied verbatim:

* `dc_rules_holoclean.txt` — denial constraints in HoloClean syntax
  (`t1&t2&EQ(t1.A,t2.A)&IQ(t1.B,t2.B)` is the FD A -> B);
* `dc_rules-validate-fd-horizon.txt` — the same rules as FDs.

The Tax rules apply to the BigDaMa/raha tax file used in `tax_dirty`
(their split files are prefixes of it).  The Hospital rules coincide with
HoloClean's `testdata/hospital_constraints.txt`.

Not used by the experiments yet; see the discussion of benchmark choices in
the session notes / docs before switching the CQA pairs to these rules.
