from collections import Counter

from math import sqrt

import ase
from ase.visualize import view
import numpy as np
import pytest
from pytest import approx
from scipy.spatial.transform import Rotation as R

from mofun import find_pattern_in_structure, replace_pattern_in_structure, Atoms, get_types_ss_map_limited_near_uc, AtomsShouldNotBeDeletedTwice
from mofun.helpers import assert_positions_are_unchanged, assert_structure_positions_are_unchanged, PositionsNotEquivalent

from tests.fixtures import *


def test_find_pattern_in_structure__octane_has_8_carbons(octane):
    pattern = Atoms(elements='C', positions=[(0, 0, 0)])
    match_indices = find_pattern_in_structure(octane, pattern)
    assert len(match_indices) == 8
    for indices in match_indices:
        assert octane[indices].elements == ["C"]

def test_find_pattern_in_structure__octane_has_2_CH3(octane):
    pattern = Atoms(elements='CHHH', positions=[(0, 0, 0), (-0.538, -0.635,  0.672), (-0.397,  0.993,  0.052), (-0.099, -0.371, -0.998)])
    match_indices = find_pattern_in_structure(octane, pattern)
    assert len(match_indices) == 2
    for indices in match_indices:
        pattern_found = octane[indices]
        assert pattern_found.elements == ["C", "H", "H", "H"]
        cpos = pattern_found.positions[0]
        assert ((pattern_found.positions[1] - cpos) ** 2).sum() == approx(1.18704299, 5e-2)
        assert ((pattern_found.positions[2] - cpos) ** 2).sum() == approx(1.18704299, 5e-2)
        assert ((pattern_found.positions[3] - cpos) ** 2).sum() == approx(1.18704299, 5e-2)

def test_find_pattern_in_structure__match_indices_returned_in_order_of_pattern():
    structure = Atoms(elements='HOH', positions=[(4., 0, 0), (5., 0., 0), (6., 0., 0.),], cell=15*np.identity(3))
    search_pattern = Atoms(elements='HO', positions=[(-1., 0, 0), (0., 0., 0.)])
    match_indices = find_pattern_in_structure(structure, search_pattern)
    assert set(match_indices) == {(0, 1), (2, 1)}

def test_find_pattern_in_structure__octane_has_12_CH2(octane):
    # there are technically 12 matches, since each CH3 makes 3 variations of CH2
    pattern = Atoms(elements='CHH', positions=[(0, 0, 0),(-0.1  , -0.379, -1.017), (-0.547, -0.647,  0.685)])
    match_indices = find_pattern_in_structure(octane, pattern)

    assert len(match_indices) == 12
    for indices in match_indices:
        pattern_found = octane[indices]
        assert pattern_found.elements == ["C", "H", "H"]
        cpos = pattern_found.positions[0]
        assert ((pattern_found.positions[1] - cpos) ** 2).sum() == approx(1.18704299, 5e-2)
        assert ((pattern_found.positions[2] - cpos) ** 2).sum() == approx(1.18704299, 5e-2)

def test_find_pattern_in_structure__all_atoms_are_within_tolerance():
    # tolerances should be absolute in the sense that even if an atom is very far away from another atom, the location
    # of that atom should be within the tolerance. E.g, here, we have a molecule that looks like this:
    #.  HC.....................................................B and if the distance between C and B was 100 angstrom
    # then 5% error in the distance could lead to a 5 angstrom difference in position of the B atom. This is not what
    # we want when replacing portions of crystalline structures. If there is a use-case for relative tolerances, we can
    # easily add it back in.
    longstructure = Atoms(elements='HCB', positions=[(1, 0, 0), (2, 0, 0), (103, 0, 0)], cell=1000*np.identity(3))
    longpattern = Atoms(elements='HCB', positions=[(1, 0, 0), (2, 0, 0), (108., 0, 0)])
    assert len(find_pattern_in_structure(longstructure, longpattern, abstol=0.05)) == 0

    longpattern.positions[2] = (104., 0, 0)
    assert len(find_pattern_in_structure(longstructure, longpattern, abstol=0.05)) == 0

    longpattern.positions[2] = (103.1, 0, 0)
    assert len(find_pattern_in_structure(longstructure, longpattern, abstol=0.05)) == 0

    longpattern.positions[2] = (103.04, 0, 0)
    assert len(find_pattern_in_structure(longstructure, longpattern, abstol=0.05)) == 1

def test_find_pattern_in_structure__cnnc_over_x_pbc_has_positions_across_x_pbc(linear_cnnc):
    linear_cnnc.positions = (linear_cnnc.positions + (-0.5, 0.0, 0.0)) % 15
    linear_cnnc.pop(-1) #don't match final NC
    search_pattern = Atoms(elements='CN', positions=[(0.0, 0., 0), (1.0, 0., 0.)])
    match_indices, match_positions = find_pattern_in_structure(linear_cnnc, search_pattern, return_positions=True)
    assert (linear_cnnc[match_indices[0]].positions == [(14.5, 0., 0.), (0.5, 0., 0.)]).all()
    assert (match_positions[0] == np.array([(14.5, 0., 0.), (15.5, 0., 0.)])).all()

def test_find_pattern_in_structure__cnnc_over_xy_pbc_has_positions_across_xy_pbc(linear_cnnc):
    v2_2 = sqrt(2.0) / 2
    linear_cnnc = Atoms(elements='CNNC', positions=[(0., 0., 0), (v2_2, v2_2, 0.), (2.*v2_2, 2.*v2_2, 0.), (3.*v2_2, 3.*v2_2, 0.)], cell=15*np.identity(3))
    linear_cnnc.positions = (linear_cnnc.positions + (-0.5, -0.5, 0.0)) % 15
    linear_cnnc.pop() #don't match final NC
    print(linear_cnnc.positions)
    search_pattern = Atoms(elements='CN', positions=[(0.0, 0., 0), (1.0, 0., 0.)])
    match_indices, match_positions = find_pattern_in_structure(linear_cnnc, search_pattern, return_positions=True)
    assert np.isclose(linear_cnnc[match_indices[0]].positions, np.array([(14.5, 14.5, 0.), (sqrt2_2 - 0.5, sqrt2_2 - 0.5, 0.)])).all()
    assert (match_positions[0] == np.array([(14.5, 14.5, 0.), (14.5 + sqrt2_2, 14.5 + sqrt2_2, 0.)])).all()

def test_find_pattern_in_structure__octane_over_pbc_has_2_CH3(octane):
    # CH3 CH2 CH2 CH2 CH2 CH2 CH2 CH3 #
    # move atoms across corner boundary
    octane.positions += -1.8
    # move coordinates into main 15 Å unit cell
    octane.positions %= 15
    octane.cell = (15 * np.identity(3))

    pattern = Atoms(elements='CHHH', positions=[(0, 0, 0), (-0.538, -0.635,  0.672), (-0.397,  0.993,  0.052), (-0.099, -0.371, -0.998)])
    match_indices = find_pattern_in_structure(octane, pattern)
    assert len(match_indices) == 2
    for indices in match_indices:
        assert octane[indices].elements == ["C", "H", "H", "H"]

@pytest.mark.slow
def test_find_pattern_in_structure__hkust1_unit_cell_has_32_benzene_rings(hkust1_cif, benzene):
    match_indices = find_pattern_in_structure(hkust1_cif, benzene)

    assert len(match_indices) == 32
    for indices in match_indices:
        pattern_found = hkust1_cif[indices]
        assert list(pattern_found.elements) == ['C','C','C','C','C','C','H','H','H']
        assert_benzene(pattern_found.positions)

@pytest.mark.slow
def test_find_pattern_in_structure__hkust1_unit_cell_offset_has_32_benzene_rings(hkust1_cif, benzene):
    hkust1_cif.translate((-4,-4,-4))
    hkust1_cif.positions = hkust1_cif.positions % np.diag(hkust1_cif.cell)
    match_indices, coords = find_pattern_in_structure(hkust1_cif, benzene, return_positions=True)
    for i, indices in enumerate(match_indices):
        assert list(hkust1_cif[indices].elements) == ['C','C','C','C','C','C','H','H','H']
        assert_benzene(coords[i])
    assert len(match_indices) == 32

@pytest.mark.slow
def test_find_pattern_in_structure__hkust1_unit_cell_has_48_Cu_metal_nodes(hkust1_cif):
    pattern = Atoms(elements='Cu', positions=[(0, 0, 0)])
    match_indices = find_pattern_in_structure(hkust1_cif, pattern)

    assert len(match_indices) == 48
    for indices in match_indices:
        pattern_found = hkust1_cif[indices]
        assert list(pattern_found.elements) == ['Cu']

@pytest.mark.slow
def test_find_pattern_in_structure__hkust1_cif_2x2x2_supercell_has_256_benzene_rings(hkust1_cif, benzene):
    hkust1_2x2x2 = hkust1_cif.replicate(repldims=(2,2,2))
    match_indices = find_pattern_in_structure(hkust1_2x2x2, benzene)

    assert len(match_indices) == 256
    for indices in match_indices:
        pattern_found = hkust1_2x2x2[indices]
        assert list(pattern_found.elements) == ['C','C','C','C','C','C','H','H','H']
        assert_benzene(pattern_found.positions)

@pytest.mark.slow
def test_find_pattern_in_structure__hkust1_cif_3x3x3_supercell_has_1296_Cu_metal_nodes(hkust1_cif):
    hkust1_3x3x3 = hkust1_cif.replicate(repldims=(3,3,3))
    pattern = Atoms(elements='Cu', positions=[(0, 0, 0)])
    match_indices = find_pattern_in_structure(hkust1_3x3x3, pattern)

    assert len(match_indices) == 1296
    for indices in match_indices:
        pattern_found = hkust1_3x3x3[indices]
        assert list(pattern_found.elements) == ['Cu']

@pytest.mark.slow
def test_find_pattern_in_structure__hkust1_xyz_3x3x3_supercell_has_1296_Cu_metal_nodes(hkust1_3x3x3_xyz):
    pattern = Atoms(elements='Cu', positions=[(0, 0, 0)])
    match_indices = find_pattern_in_structure(hkust1_3x3x3_xyz, pattern)

    assert len(match_indices) == 1296
    for indices in match_indices:
        pattern_found = hkust1_3x3x3_xyz[indices]
        assert list(pattern_found.elements) == ['Cu']

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_nothing(octane):
    # CH3 CH2 CH2 CH2 CH2 CH2 CH2 CH3 #
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    replace_pattern = Atoms()

    final_structure = replace_pattern_in_structure(octane, search_pattern, replace_pattern)
    assert list(final_structure.elements) == ["C"] * 8

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_nothing_half_the_time(octane):
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    final_structure = replace_pattern_in_structure(octane, search_pattern, Atoms(), replace_fraction=0.5)
    assert Counter(final_structure.elements) == {"H": 9, "C": 8}

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_nothing_never(octane):
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    final_structure = replace_pattern_in_structure(octane, search_pattern, Atoms(), replace_fraction=0.0)
    assert Counter(final_structure.elements) == {"H": 18, "C": 8}

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_nothing_quarter_time(octane):
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    final_structure = replace_pattern_in_structure(octane, search_pattern, Atoms(), replace_fraction=0.25)
    assert Counter(final_structure.elements) == {"H": 14, "C": 8}

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_hydrogens(octane):
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    replace_pattern = search_pattern
    final_structure = replace_pattern_in_structure(octane, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"H": 18, "C": 8}
    assert_structure_positions_are_unchanged(octane, final_structure)

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_fluorines(octane):
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    replace_pattern = Atoms(elements='F', positions=[(0, 0, 0)])
    match_indices = find_pattern_in_structure(octane, search_pattern)
    final_structure = replace_pattern_in_structure(octane, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"F": 18, "C": 8}
    assert_structure_positions_are_unchanged(octane, final_structure)

def test_replace_pattern_in_structure__replace_hydrogens_in_octane_with_fluorines_half_the_time(octane):
    search_pattern = Atoms(elements='H', positions=[(0, 0, 0)])
    replace_pattern = Atoms(elements='F', positions=[(0, 0, 0)])
    match_indices = find_pattern_in_structure(octane, search_pattern)
    final_structure = replace_pattern_in_structure(octane, search_pattern, replace_pattern, replace_fraction=0.5)
    assert Counter(final_structure.elements) == {"H":9, "F": 9, "C": 8}
    assert_structure_positions_are_unchanged(octane, final_structure)

def test_replace_pattern_in_structure__replace_CH3_in_octane_with_fluorines(octane):
    search_pattern = Atoms(elements='CHHH', positions=[(0, 0, 0), (-0.538, -0.635,  0.672), (-0.397,  0.993,  0.052), (-0.099, -0.371, -0.998)])
    replace_pattern = Atoms(elements='FFFF', positions=search_pattern.positions)
    final_structure = replace_pattern_in_structure(octane, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"F": 8, "C": 6, "H": 12}
    # note the positions are not EXACTLY the same because the original structure has slightly
    # different coordinates for the two CH3 groups!
    assert_structure_positions_are_unchanged(octane, final_structure, max_delta=0.1)

def test_replace_pattern_in_structure__replace_CH3_in_octane_with_CH3(octane):
    search_pattern = Atoms(elements='CHHH', positions=[(0, 0, 0), (-0.538, -0.635,  0.672), (-0.397,  0.993,  0.052), (-0.099, -0.371, -0.998)])
    replace_pattern = Atoms(elements='CHHH', positions=search_pattern.positions)
    final_structure = replace_pattern_in_structure(octane, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"C": 8, "H": 18}
    # note the positions are not EXACTLY the same because the original structure has slightly
    # different coordinates for the two CH3 groups!
    assert_structure_positions_are_unchanged(octane, final_structure, max_delta=0.1)

def test_replace_pattern_in_structure__two_points_on_x_axis_positions_are_unchanged():
    structure = Atoms(elements='CNNC', positions=[(0., 0., 0), (1.0, 0., 0.), (2.0, 0., 0.), (3.0, 0., 0.)], cell=100*np.identity(3))
    search_pattern = Atoms(elements='NN', positions=[(0.0, 0., 0), (1.0, 0., 0.)])
    replace_pattern = Atoms(elements='FF', positions=[(0., 0., 0), (1.0, 0., 0.)])

    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"C":2, "F": 2}
    assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__three_points_on_x_axis_positions_are_unchanged():
    # this test exists to verify that for a search pattern with more than 2 atoms where all atoms lie on the same axis
    # there are no errors, since there is an extra unnecessary quaternion calcuation to orient the replacement pattern
    # into the final position
    structure = Atoms(elements='CNNNC', positions=[(0., 0., 0), (1., 0., 0.), (2., 0., 0.), (3., 0., 0.), (4., 0., 0.)], cell=100*np.identity(3))
    search_pattern = Atoms(elements='NNN', positions=[(0., 0., 0), (1.0, 0., 0.), (2.0, 0., 0.)])
    replace_pattern = Atoms(elements='FFF', positions=[(0., 0., 0), (1.0, 0., 0.), (2.0, 0., 0.)])

    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"C":2, "F": 3}
    assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__overlapping_match_patterns_errors():
    structure = Atoms(elements='CNNC', positions=[(0., 0., 0), (1.0, 0., 0.), (2.0, 0., 0.), (3.0, 0., 0.)], cell=100*np.identity(3))
    search_pattern = Atoms(elements='NNC', positions=[(0., 0., 0), (1.0, 0., 0.), (2.0, 0., 0.)])
    replace_pattern = Atoms(elements='FFC', positions=[(0., 0., 0), (1.0, 0., 0.), (2.0, 0., 0.)])

    with pytest.raises(AtomsShouldNotBeDeletedTwice):
        final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)

def test_replace_pattern_in_structure__pattern_and_reverse_pattern_on_x_axis_positions_are_unchanged():
    structure = Atoms(elements='HHCCCHH', positions=[(-1., 1, 0), (-1., -1, 0), (0., 0., 0), (1., 0., 0.), (3., 0., 0.), (4., 1, 0), (4., -1, 0)], cell=7*np.identity(3))
    structure.translate([2, 2, 0.1])
    search_pattern = Atoms(elements='HHC', positions=[(0., 1, 0), (0., -1, 0), (1., 0., 0.)])
    replace_pattern = Atoms(elements='HHC', positions=[(0., 1, 0), (0., -1, 0), (1., 0., 0.)])

    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)

    assert Counter(final_structure.elements) == {"C":3, "H": 4}
    assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__replacement_pattern_across_pbc_gets_coordinates_within_unit_cell():
    structure = Atoms(elements='CNNF', positions=[(9.1, 0., 0), (0.1, 0., 0), (1.1, 0., 0.), (2.1, 0., 0.)], cell=10*np.identity(3))
    search_pattern = Atoms(elements='CN', positions=[(0., 0., 0), (1.0, 0., 0.)])
    replace_pattern = search_pattern
    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == Counter(structure.elements)
    assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__3way_symmetrical_structure_raises_position_exception():
    structure = Atoms(elements='CCHH', positions=[(0., 0., 0.), (1., 0., 0.),(0., 1., 0.), (0., 0., 1.)])
    structure.translate((3,3,3))
    structure.cell = 15 * np.identity(3)

    search_pattern = structure.copy()

    replace_pattern = Atoms(elements='FFHeHe', positions=search_pattern.positions)

    with pytest.raises(PositionsNotEquivalent):
        final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern, verbose=True)

def test_replace_pattern_in_structure__100_randomly_rotated_patterns_replaced_with_itself_does_not_change_positions():
    search_pattern = Atoms(elements='CCH', positions=[(0., 0., 0.), (4., 0., 0.),(0., 1., 0.)])
    replace_pattern = Atoms(elements='FFHe', positions=search_pattern.positions)
    structure = search_pattern.copy()
    structure.cell = 15 * np.identity(3)
    for _ in range(100):
        r = R.random(1)
        print("quat: ", r.as_quat())
        structure.positions = r.apply(structure.positions)
        dp = np.random.random(3) * 15
        print(dp)
        structure.translate(dp)
        structure.positions = structure.positions % 15
        final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern, axis1a_idx=0, axis1b_idx=1)
        assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__special_rotated_pattern_replaced_with_itself_does_not_change_positions():
    search_pattern = Atoms(elements='CCH', positions=[(0., 0., 0.), (4., 0., 0.),(0., 1., 0.)])
    replace_pattern = Atoms(elements='FFHe', positions=search_pattern.positions)
    structure = search_pattern.copy()
    structure.cell = [15] * np.identity(3)
    r = R.from_quat([-0.4480244,  -0.50992783,  0.03212454, -0.7336319 ])
    structure.positions = r.apply(structure.positions)
    structure.positions = structure.positions % 15
    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern, axis1a_idx=0, axis1b_idx=1)
    assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__special2_rotated_pattern_replaced_with_itself_does_not_change_positions():
    search_pattern = Atoms(elements='CCH', positions=[(0., 0., 0.), (4., 0., 0.),(0., 1., 0.)])
    replace_pattern = Atoms(elements='FFHe', positions=search_pattern.positions)
    structure = search_pattern.copy()
    structure.cell = 15 * np.identity(3)
    r = R.from_quat([ 0.02814096,  0.99766676,  0.03984918, -0.04776152])
    structure.positions = r.apply(structure.positions)
    structure.positions = structure.positions % 15
    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern, axis1a_idx=0, axis1b_idx=1)
    assert_structure_positions_are_unchanged(structure, final_structure)

def test_replace_pattern_in_structure__two_points_at_angle_are_unchanged():
    structure = Atoms(elements='CNNC', positions=[(0., 0., 0), (1.0, 0., 0.),
                                        (1+ sqrt(2)/2, sqrt(2)/2, 0.),
                                        (2 + sqrt(2)/2, sqrt(2)/2, 0.)], cell=100*np.identity(3))
    search_pattern = Atoms(elements='NN', positions=[(0.0, 0., 0), (1.0, 0., 0.)])
    replace_pattern = Atoms(elements='FF', positions=[(0., 0., 0), (1.0, 0., 0.)])

    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {"C":2, "F": 2}
    assert_structure_positions_are_unchanged(structure, final_structure)

@pytest.mark.slow
def test_replace_pattern_in_structure__in_hkust1_replacing_benzene_with_benzene_does_not_change_positions(hkust1_cif, benzene):
    final_structure = replace_pattern_in_structure(hkust1_cif, benzene, benzene, axis1a_idx=0, axis1b_idx=7)
    assert Counter(final_structure.elements) == Counter(hkust1_cif.elements)
    assert_structure_positions_are_unchanged(hkust1_cif, final_structure, max_delta=0.1)

@pytest.mark.slow
def test_replace_pattern_in_structure__in_hkust1_offset_replacing_benzene_with_benzene_does_not_change_positions(hkust1_cif, benzene):
    hkust1_cif.translate((-4,-4,-4))
    hkust1_cif.positions = hkust1_cif.positions % np.diag(hkust1_cif.cell)
    final_structure = replace_pattern_in_structure(hkust1_cif, benzene, benzene, axis1a_idx=0, axis1b_idx=7)
    assert Counter(final_structure.elements) == Counter(hkust1_cif.elements)
    assert_structure_positions_are_unchanged(hkust1_cif, final_structure, max_delta=0.1)

@pytest.mark.slow
def test_replace_pattern_in_structure__in_uio66_replacing_linker_with_linker_does_not_change_positions():
    with Path("tests/uio66/uio66.cif") as path:
        structure = Atoms.load_cif(path)
    with Path("tests/uio66/uio66-linker.cif") as path:
        search_pattern = Atoms.load_cif(path)
    with Path("tests/uio66/uio66-linker-fluorinated.cif") as path:
        replace_pattern = Atoms.load_cif(path)

    final_structure = replace_pattern_in_structure(structure, search_pattern, replace_pattern)
    assert Counter(final_structure.elements) == {'C': 192, 'O': 120, 'F': 96, 'Zr': 24}
    # assert_structure_positions_are_unchanged(structure, final_structure, max_delta=0.25, verbose=True)

def test_replace_pattern_in_structure__replace_no_bonds_linker_with_linker_with_bonds_angles_has_bonds_angles(uio66_linker_no_bonds, uio66_linker_some_bonds):
    structure = uio66_linker_no_bonds.copy()
    structure.cell = 100*np.identity(3)
    final_structure = replace_pattern_in_structure(structure, uio66_linker_no_bonds, uio66_linker_some_bonds, axis1a_idx=0, axis1b_idx=15)

    assert Counter(final_structure.elements) == {'C': 8, 'O': 4, 'H': 4}
    assert_structure_positions_are_unchanged(structure, final_structure, max_delta=0.1)
    assert_topo(final_structure.dihedrals, uio66_linker_some_bonds.dihedrals,
                final_structure.dihedral_types, uio66_linker_some_bonds.dihedral_types,
                final_structure.dihedral_type_coeffs, uio66_linker_some_bonds.dihedral_type_coeffs)

def test_get_types_ss_map_limited_near_uc__triclinic_cell_zero_length_gives_original_atoms():
    one_axis_points = np.linspace(0.01,0.99,2)
    cell = np.array([[10, 0, 0], [10, 10, 0], [0, 0, 10]])
    relv = np.array(np.meshgrid(one_axis_points, one_axis_points, one_axis_points)).T.reshape(-1,3)
    absv = np.dot(cell.T, relv.T).T
    structure = Atoms(elements=["H"]*len(absv), positions=absv, cell=cell)

    s_types_view, index_mapper, s_pos_view, s_positions = get_types_ss_map_limited_near_uc(structure, 0)
    assert len(s_positions) == 27 * len(absv)
    assert len(s_types_view) == len(absv)
    assert len(index_mapper) == len(absv)
    assert len(s_pos_view) == len(absv)
    assert_positions_are_unchanged(np.array(s_pos_view), absv, verbose=True)
