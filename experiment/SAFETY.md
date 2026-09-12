# Safety boundary statement

**This repository is a defensive instrument. It is written so that it can be used by
a defender and not usefully by an attacker. That constraint shaped what is here and,
more importantly, what is deliberately absent.**

## What the experiment does

`verify_bypass_paths.py` runs three vectors against **libraries on the operator's own
machine**, in a temporary directory, using a canary string as the payload:

| Vector | Question |
|---|---|
| T1 | Does an HDF5 file's external-storage declaration let a *reader* of that file reach bytes outside the file? |
| T2 | Does a config layer template-evaluate its inputs? |
| T3 | Can a remote dataset declaration resolve to a local path? |

The payload is a canary token, never a real file read, never a credential, never
anything from a third party. The purpose is to establish whether a *box* holds or does
not hold — control verification, not exploitation.

## What is deliberately NOT in this repository

1. **No exploit chain and no PoC against any live system.** Nothing here targets a
   real host, service, account, or dataset. There is no network code path in the
   experiment beyond what a library itself does locally.
2. **No weaponisation of any vendor's specific deployment.** The report and the code
   discuss the *class* of mechanism (a loader trusting a third-party file's metadata;
   a pipeline rendering config as a template). They do not reconstruct how the July
   2026 intrusion actually chained eight zero-days, and no artefacts from that incident
   are reproduced.
3. **No target list.** The six-item control matrix in the report names *checks a
   defender can run against their own estate*, with pass conditions. It is not a map
   of entry points — it contains no hostnames, no service fingerprints, no ordering
   that would shorten an attack.
4. **No data exfiltration tooling.** The scanner is metadata-only by construction.

## Why the scanner is metadata-only

`scan_hdf5_for_external()` inspects the HDF5 *bookkeeping structures* — the dataset
creation properties that declare external storage — and prints what it finds. It
never dereferences the declaration, so running it against an untrusted file does not
cause the file's declared target to be read. A detector that has to execute the risky
path in order to detect it is not a detector a defender can run at scale.

This asymmetry is intentional. Publishing *how to detect* raises the cost of the
attack; publishing *how to exploit* lowers it. Only the first is here.

## Use this on your own systems, or with written authorisation

Running the experiment against infrastructure you do not own or administer is
unauthorised access in most jurisdictions, regardless of whether the payload is a
canary. The vectors in T1/T2 are unremarkable library behaviours that any loader
exhibits; that is precisely why they are easy to misread as harmless. Do not test on
someone else's estate.

The experiment was designed as **refusal testing inside a sandbox the author
controls**. If you adapt it, keep it that way.

## On reading the results

`not_rejected` means a check did not hold. It does **not** mean a platform was
compromised, a product is vulnerable, or an exploit is available. The report states
this explicitly for vector T1b, and the same caution applies to every row of
`results_final.json`.

Two corrections made during the experiment are recorded rather than quietly fixed,
because they are the kind of error this method invites:

- an earlier version used HDF5 `ExternalLink` rather than external storage and drew a
  conclusion from the wrong mechanism;
- a run that failed on an API-parameter error would have been recorded as "declined"
  — a **false positive**. It is recorded as `inconclusive`.

Both are surfacing in `results_final.json` and the report's limitations section.

## Reporting

If you use this tooling and find that a widely deployed loader is affected, the
defensive move is coordinated disclosure to the maintainer, not publication of a
working chain. The detector is already the useful half.
