#!/usr/bin/env python3
"""Control-verification experiment.

Question: are the two disclosed dataset-hosting bypass paths still usable on the
library versions installed today?

Background
----------
In the July 2026 Hugging Face incident, the attacker reached Hugging Face's data
pipeline through two paths described in the public technical timeline. Both bypassed
the URL allowlist by going through **local filesystem paths**:

  (A) HDF5 external storage / external reference --- file disclosure
  (B) Jinja2 template injection in dataset configuration --- code execution on a worker

This experiment does two things:

  1. Checks whether those two classes of behaviour are refused on the currently
     installed library versions (control verification, not exploitation).
  2. Ships a **metadata-only** HDF5 external-storage scanner that does not load data,
     usable as item 2 of the report's six-item control matrix.

This is NOT a penetration test. Hard safety boundaries, enforced in the code:
  1. Files are only ever constructed inside a temporary directory; no real system
     path is touched (the T1b cross-directory case uses a second temp directory too).
  2. The canary is a random benign string. It contains no credentials, keys or tokens.
  3. NO NETWORK REQUESTS of any kind (no egress, no callback, no C2).
  4. No weaponisable payload is generated.
  5. Results are recorded honestly whether the control holds or not. Where the test
     design cannot settle the question it is recorded as `unclear` rather than
     presented as a finding.

Usage
-----
    python3 verify_bypass_paths.py                    # run all vectors
    python3 verify_bypass_paths.py --json out.json    # also export JSON
    python3 verify_bypass_paths.py --scan FILE.h5     # scan only (metadata only)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shutil
import sys
import tempfile

CANARY = "HERMES_CANARY_" + secrets.token_hex(8)
RESULTS: list[dict] = []


def record(test: str, vector: str, verdict: str, evidence: str, note: str = ""):
    """verdict: 'rejected' control holds | 'not_rejected' control does not hold
                | 'unclear' undecidable from this test
    """
    RESULTS.append({"test": test, "vector": vector, "verdict": verdict,
                    "evidence": evidence[:600], "note": note})
    flag = {"rejected": "control HOLDS     [ok]",
            "not_rejected": "control does NOT hold [!]",
            "unclear": "undecidable       [-] "}[verdict]
    print(f"  [{flag}] {test} / {vector}")
    print(f"          evidence: {evidence[:240]}")
    if note:
        print(f"          note:     {note}")


def env_info() -> dict:
    info = {"python": sys.version.split()[0], "platform": platform.platform()}
    for mod in ("h5py", "datasets", "jinja2", "pyarrow"):
        try:
            m = __import__(mod)
            info[mod] = getattr(m, "__version__", "unknown")
        except Exception:
            info[mod] = "NOT INSTALLED"
    return info


# ============================================================================
# Reusable tool: HDF5 external-storage scanner (metadata only, loads no data)
# ============================================================================
def scan_hdf5_for_external(path: str) -> dict:
    """Scan one HDF5 file and report whether it declares external data storage or
    external links pointing outside itself.

    **No data content is read** --- only bookkeeping metadata. That is what makes it
    safe to run as a first-pass check against an untrusted file.

    Returns {'file', 'external_datasets': [...], 'external_links': [...], 'error'}
    """
    import h5py

    out = {"file": path, "external_datasets": [], "external_links": [], "error": None}

    def visit(name, obj):
        try:
            if isinstance(obj, h5py.Dataset):
                ext = getattr(obj, "external", None)
                if ext:
                    out["external_datasets"].append({
                        "path": name,
                        "targets": [{"file": str(e[0]), "offset": int(e[1]), "size": int(e[2])}
                                    for e in ext],
                    })
            elif obj.__class__.__name__ == "ExternalLink":
                out["external_links"].append(
                    {"path": name, "target": str(getattr(obj, "path", "?"))})
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"

    try:
        with h5py.File(path, "r") as f:
            f.visititems(visit)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def scan_command(target: str):
    targets = []
    if os.path.isdir(target):
        for root, _, files in os.walk(target):
            for fn in files:
                if fn.lower().endswith((".h5", ".hdf5", ".hdf")):
                    targets.append(os.path.join(root, fn))
    else:
        targets.append(target)

    print("=" * 72)
    print(f"HDF5 external-storage scan (metadata only, no data loaded) --- "
          f"{len(targets)} file(s)")
    print("=" * 72)
    flagged = 0
    for p in targets:
        r = scan_hdf5_for_external(p)
        n = len(r["external_datasets"]) + len(r["external_links"])
        status = "[!] declares external storage" if n else "[ok] no external storage"
        print(f"\n{status}  {p}")
        if r["error"]:
            print(f"   error: {r['error']}")
        for d in r["external_datasets"]:
            flagged += 1
            print(f"   dataset {d['path']} stores its bytes in an external file:")
            for t in d["targets"]:
                print(f"     -> {t['file']}  offset={t['offset']} size={t['size']}")
        for l in r["external_links"]:
            flagged += 1
            print(f"   external link {l['path']} -> {l['target']}")
    print(f"\nsummary: {flagged} external reference(s) across {len(targets)} file(s)")
    # exit code 2 signals "something was flagged", for use in CI / a control check
    return 0 if flagged == 0 else 2


# ============================================================================
# T1 - HDF5 external storage (file disclosure)
# ============================================================================
def test_hdf5_external(workdir: str):
    """HDF5 external storage: a dataset's bytes live not in the .h5 but in an
    external file. Reading the dataset reads that file."""
    import h5py

    payload = CANARY.encode()

    # --- T1a: same directory, relative path.
    # Note: HDF5 resolves a relative external path against the CURRENT WORKING
    # DIRECTORY, not against the .h5 file's directory. That is a trap in itself.
    same_file = os.path.join(workdir, "marker_canary.bin")
    with open(same_file, "wb") as f:
        f.write(payload)
    h5a = os.path.join(workdir, "benign_samedir.h5")
    with h5py.File(h5a, "w") as f:
        f.create_dataset("data", data=[1, 2, 3])
        f.create_dataset("ext", shape=(len(payload),), dtype="S1",
                         external=[(os.path.basename(same_file), 0, len(payload))])

    cwd = os.getcwd()
    leaked_a, err_a = False, ""
    try:
        os.chdir(workdir)                 # so the relative path resolves as intended
        with h5py.File(os.path.basename(h5a), "r") as f:
            leaked_a = payload in b"".join(f["ext"][...])
    except Exception as e:
        err_a = f"{type(e).__name__}: {e}"
    finally:
        os.chdir(cwd)

    record("T1a HDF5 external storage", "external file, same-directory relative path",
           "not_rejected" if leaked_a else ("rejected" if err_a else "unclear"),
           ("canary was read back: external storage works, so reading the dataset "
            "reads bytes outside the .h5" if leaked_a else f"not read back. {err_a}"),
           "HDF5 resolves relative external paths against the process working "
           "directory, not the .h5 location -- a trap in itself")

    # --- T1b: absolute path pointing outside the dataset directory (the real escape)
    outside = tempfile.mkdtemp(prefix="outside_")
    escape_file = os.path.join(outside, "outside_marker.bin")
    with open(escape_file, "wb") as f:
        f.write(payload)
    h5b = os.path.join(workdir, "benign_escape.h5")
    with h5py.File(h5b, "w") as f:
        f.create_dataset("ext", shape=(len(payload),), dtype="S1",
                         external=[(escape_file, 0, len(payload))])

    leaked_b, err_b = False, ""
    try:
        with h5py.File(h5b, "r") as f:
            leaked_b = payload in b"".join(f["ext"][...])
    except Exception as e:
        err_b = f"{type(e).__name__}: {e}"

    record("T1b HDF5 external storage",
           "absolute path to an arbitrary file outside the dataset directory",
           "not_rejected" if leaked_b else ("rejected" if err_b else "unclear"),
           ("canary was read back: external storage can point at an absolute path "
            "outside the directory, so reading the dataset reads that file's bytes"
            if leaked_b else f"not read back. {err_b}"),
           "Core finding of this experiment: the HDF5 layer places no restriction on "
           "where external storage points; that responsibility sits in the loader above")

    # --- T1c: can the scanner detect it? (verifies the defence is deployable)
    r = scan_hdf5_for_external(h5b)
    detected = len(r["external_datasets"]) + len(r["external_links"]) > 0
    record("T1c scanner detection capability",
           "can a metadata-only read find the external-storage declaration",
           "rejected" if detected else "not_rejected",
           f"scan result: {json.dumps(r, ensure_ascii=False)[:300]}",
           "if detectable, 'scan metadata before reading' is a deployable defence")

    shutil.rmtree(outside, ignore_errors=True)


# ============================================================================
# T2 - config template evaluation (Jinja2)
# ============================================================================
def test_config_template(workdir: str):
    import json as _json

    cfg_text = '{"description": "{{ 7*7 }}", "path": "data.parquet"}'

    parsed = _json.loads(cfg_text)
    evaluated = parsed.get("description") != "{{ 7*7 }}"
    record("T2a JSON parsing layer", "config field is template-evaluated",
           "rejected" if not evaluated else "not_rejected",
           f"parse result description={parsed.get('description')!r}",
           "control group: a plain JSON parser does not template-evaluate")

    try:
        from jinja2 import Template
        rendered = Template(cfg_text).render()
        hit = '"49"' in rendered
        record("T2b if a pipeline Jinja-renders config",
               "config field is template-evaluated",
               "not_rejected" if hit else "unclear",
               f"render result: {rendered[:160]}",
               "existence claim: wherever a pipeline renders config through Jinja2, "
               "expressions inside config are executed -- the mechanism exists")
    except Exception as e:
        record("T2b if a pipeline Jinja-renders config",
               "config field is template-evaluated", "unclear",
               f"{type(e).__name__}: {e}")

    try:
        import datasets
        val = datasets.DatasetInfo(description="{{ 7*7 }}").description
        record("T2c datasets config layer", "config field is template-evaluated",
               "rejected" if val == "{{ 7*7 }}" else "not_rejected",
               f"DatasetInfo.description={val!r}",
               f"datasets {datasets.__version__}: this layer does not template-evaluate")
    except Exception as e:
        record("T2c datasets config layer", "config field is template-evaluated",
               "unclear", f"{type(e).__name__}: {e}", "datasets not installed")


# ============================================================================
# T3 - declared-path escape: undecidable locally, recorded as such
# ============================================================================
def test_declared_path_escape(workdir: str):
    """Whether a local filesystem path in a dataset **declaration** is stopped by an
    allowlist.

    Honest conclusion: undecidable from a local machine.
    Reason: the `data_files=` argument accepts arbitrary local paths by design (it is
    the operator's own machine). The real risk case is a **remote** dataset whose
    declaration references a local path, and testing that needs a hosting endpoint.
    We record it as undecidable and carry it into the report's limitations section
    rather than making a claim we cannot support.
    """
    try:
        import datasets
        ds_dir = os.path.join(workdir, "ds_repo")
        os.makedirs(ds_dir, exist_ok=True)
        outside = tempfile.mkdtemp(prefix="outside_")
        parq = os.path.join(outside, "outside.parquet")
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            pq.write_table(pa.table({"a": [1, 2, 3]}), parq)
            accepted, msg = True, "constructed successfully"
        except Exception as e:
            accepted, msg = False, f"{type(e).__name__}: {e}"

        record("T3 declared-path escape",
               "a remote dataset declaration referencing a local file path",
               "unclear",
               "undecidable locally: data_files= accepts arbitrary local paths by "
               "design (the operator's own machine). The real risk case needs a "
               f"hosting endpoint to test. Construction attempt: {msg}",
               "carried into the report's limitations: a gap this experiment does not "
               "close, and a direction for future work")
        shutil.rmtree(outside, ignore_errors=True)
    except Exception as e:
        record("T3 declared-path escape",
               "a remote dataset declaration referencing a local file path",
               "unclear", f"{type(e).__name__}: {e}")


# ============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--scan", default=None,
                    help="scan only: HDF5 external storage (file or directory)")
    ap.add_argument("--keep", action="store_true",
                    help="keep the temporary working directory")
    args = ap.parse_args()

    if args.scan:
        return scan_command(args.scan)

    print("=" * 72)
    print("Control-verification experiment: are the disclosed bypass paths still "
          "usable on current versions?")
    print("=" * 72)
    info = env_info()
    for k, v in info.items():
        print(f"  {k:10s} {v}")
    print(f"  canary     {CANARY}")
    print("-" * 72)

    workdir = tempfile.mkdtemp(prefix="ctrlverify_")
    print(f"working directory (local temp dir, deleted after the run): {workdir}\n")
    try:
        print("T1 - HDF5 external storage (file disclosure)")
        test_hdf5_external(workdir)
        print("\nT2 - config template evaluation (Jinja2)")
        test_config_template(workdir)
        print("\nT3 - declared-path escape")
        test_declared_path_escape(workdir)
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)

    r = [x for x in RESULTS if x["verdict"] == "rejected"]
    n = [x for x in RESULTS if x["verdict"] == "not_rejected"]
    u = [x for x in RESULTS if x["verdict"] == "unclear"]
    print("\n" + "=" * 72)
    print(f"summary: control holds {len(r)} | control does not hold {len(n)} | "
          f"undecidable {len(u)}")
    print("=" * 72)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"env": info, "canary": CANARY, "results": RESULTS},
                      f, ensure_ascii=False, indent=2)
        print(f"exported: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
