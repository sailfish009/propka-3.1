"""Tests for PROPKA 3.1"""
import logging
import os
import re
from pathlib import Path
import pytest
import pandas as pd
import propka.lib
import propka.molecular_container


_LOGGER = logging.getLogger(__name__)


# Maximum error set by number of decimal places in pKa output as well as need
# to make unmodified code work on WSL Ubuntu 18.04
MAX_ERR = 0.01


# This directory
TEST_DIR = Path("tests")
# Location for test PDBs
PDB_DIR = Path("pdb")
# Location for results for comparing output (allow running from tests/ and ../tests/)
RESULTS_DIR = Path("tests/results")
if not RESULTS_DIR.is_dir():
    _LOGGER.warning("Switching to sub-directory")
    RESULTS_DIR = Path("results")
# Arguments to add to all tests
DEFAULT_ARGS = []


def get_test_dirs():
    """Get locations of test files.

    Returns:
        dictionary with test file locations.
    """
    path_dict = {}
    for key, path in [("pdbs", PDB_DIR), ("results", RESULTS_DIR)]:
        test_path = TEST_DIR / path
        if test_path.is_dir():
            path_dict[key] = test_path
        else:
            test_path = path
            if test_path.is_dir():
                path_dict[key] = test_path
            else:
                errstr = "Can't find %s test files in %s" % (key, [TEST_DIR / path, path])
                raise FileNotFoundError(errstr)
    return path_dict


def run_propka(options, pdb_path, tmp_path):
    """Run PROPKA software.

    Args:
        options:  list of PROPKA options
        pdb_path:  path to PDB file
        tmp_path:  path for working directory
    """
    options += [str(pdb_path)]
    args = propka.lib.loadOptions(options)
    try:
        _LOGGER.warning("Working in tmpdir %s because of PROPKA file output; need to fix this.",
                        tmp_path)
        cwd = Path.cwd()
        os.chdir(tmp_path)
        molecule = propka.molecular_container.Molecular_container(str(pdb_path), args)
        molecule.calculate_pka()
        molecule.write_pka()
    except Exception as err:
        raise err
    finally:
        os.chdir(cwd)


def compare_output(pdb, tmp_path, ref_path):
    """Compare results of test with reference.

    Args:
        pdb:  PDB filename stem
        tmp_path:  temporary directory
        ref_path:  path with reference results
    Raises:
        ValueError if results disagree.
    """
    ref_data = []
    with open(ref_path, "rt") as ref_file:
        for line in ref_file:
            ref_data.append(float(line))

    test_data = []
    pka_path = Path(tmp_path) / ("%s.pka" % pdb)
    with open(pka_path, "rt") as pka_file:
        at_pka = False
        for line in pka_file:
            if not at_pka:
                if "model-pKa" in line:
                    at_pka = True
            elif line.startswith("---"):
                at_pka = False
            else:
                m = re.search(r'([0-9]+\.[0-9]+)', line)
                value = float(m.group(0))
                test_data.append(value)

    df = pd.DataFrame({"reference": ref_data, "test": test_data})
    df["difference"] = df["reference"] - df["test"]
    max_err = df["difference"].abs().max()
    if max_err > MAX_ERR:
        errstr = "Error in test (%g) exceeds maximum (%g)" % (max_err, MAX_ERR)
        raise ValueError(errstr)


@pytest.mark.parametrize("pdb, options", [
    pytest.param("1FTJ-Chain-A", [], id="1FTJ-Chain-A: no options"),
    pytest.param('1HPX', [], id="1HPX: no options"),
    pytest.param('4DFR', [], id="4DFR: no options"),
    pytest.param('3SGB', [], id="3SGB: no options"),
    pytest.param('3SGB-subset', ["--titrate_only", 
        "E:17,E:18,E:19,E:29,E:44,E:45,E:46,E:118,E:119,E:120,E:139"], 
        id="3SGB: --titrate_only"),
    pytest.param('1HPX-warn', ['--quiet'], id="1HPX-warn: --quiet")])
def test_regression(pdb, options, tmp_path):
    """Basic regression test of PROPKA functionality."""
    path_dict = get_test_dirs()
    ref_path = path_dict["results"] / ("%s.dat" % pdb)
    if ref_path.is_file():
        ref_path = ref_path.resolve()
    else:
        _LOGGER.warning("Missing results file for comparison: %s", ref_path)
        ref_path = None
    pdb_path = path_dict["pdbs"] / ("%s.pdb" % pdb)
    if pdb_path.is_file():
        pdb_path = pdb_path.resolve()
    else:
        errstr = "Missing PDB file: %s" % pdb_path
        raise FileNotFoundError(errstr)
    tmp_path = Path(tmp_path).resolve()

    run_propka(options, pdb_path, tmp_path)
    if ref_path is not None:
        compare_output(pdb, tmp_path, ref_path)
