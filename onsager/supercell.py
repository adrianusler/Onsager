"""
Supercell class

Class to store supercells of crystals: along with some analysis
1. add/remove/substitute atoms
2. output POSCAR format (possibly other formats?)
3. find the transformation map between two different representations of the same supercell
4. construct an NEB pathway between two supercells
5. possibly input from CONTCAR? extract displacements?
"""

__author__ = 'Dallas R. Trinkle'

import numpy as np
import collections, copy, warnings
from . import crystal
from functools import reduce


# YAML tags:
# interfaces are either at the bottom, or staticmethods in the corresponding object
# NDARRAY_YAMLTAG = '!numpy.ndarray'
# GROUPOP_YAMLTAG = '!GroupOp'

class Supercell(object):
    """
    A class that defines a Supercell of a crystal
    """

    def __init__(self, crys, super, interstitial=(), Nchem=-1, empty=False):
        """
        Initialize our supercell

        :param crys: crystal object
        :param super: 3x3 integer matrix
        :param interstitial: (optional) list/tuple of indices that correspond to interstitial sites
        :param Nchem: (optional) number of distinct chemical elements to consider; default = crys.Nchem+1
        :param empty: optional; designed to allow "copy" to work
        """
        if empty: return
        self.crys = crys
        self.super = super.copy()
        self.interstitial = copy.deepcopy(interstitial)
        self.Nchem = crys.Nchem + 1 if Nchem < crys.Nchem else Nchem
        self.N = self.crys.N
        self.chemistry = [crys.chemistry[n] if n < crys.Nchem else '' for n in range(self.Nchem+1)]
        self.chemistry[-1] = 'v'
        self.Wyckofflist, self.Wyckoffchem = [], []
        for n,(c,i) in enumerate(self.crys.atomindices):
            for wset in self.Wyckofflist:
                if n in wset: break
            if len(self.Wyckofflist)==0 or n not in wset:
                # grab the set of (c,i) of Wyckoff sets:
                indexset = next((iset for iset in self.crys.Wyckoff if (c,i) in iset),None)
                self.Wyckofflist.append(frozenset([self.crys.atomindices.index(ci) for ci in indexset]))
                self.Wyckoffchem.append(self.crys.chemistry[c])
        self.size, self.invsuper, self.translist = self.maketrans(self.super)
        self.transdict = {tuple(t):n for n,t in enumerate(self.translist)}
        self.pos, self.occ = self.makesites(), -1*np.ones(self.N*self.size, dtype=int)
        self.G = self.gengroup()

    __copyattr__ = ('chemistry', 'N', 'size', 'invsuper',
                    'Wyckofflist', 'Wyckoffchem',
                    'translist', 'transdict', 'pos', 'occ', 'G')

    def copy(self):
        """
        Make a copy of the supercell; initializes, then copies over copyattr's.
        :return: new supercell object, copy of the original
        """
        supercopy = Supercell(self.crys, self.super, self.interstitial, self.Nchem)
        for attr in self.__copyattr__: setattr(supercopy, attr, copy.deepcopy(getattr(self, attr)))
        return supercopy

    def __eq__(self, other):
        """
        Return True if two supercells are equal; this means they should have the same occupancy
        *and* the same ordering
        :param other: supercell for comparison
        :return: True if same crystal, supercell, occupancy, and ordering; False otherwise
        """
        ### Will need more....
        return isinstance(other, self.__class__) and np.all(self.super == other.super) and \
               self.interstitial == other.interstitial and np.allclose(self.pos, other.pos)

    def __ne__(self, other):
        """Inequality == not __eq__"""
        return not self.__eq__(other)

    def __str__(self):
        """Human readable version of supercell"""
        str = "Supercell of crystal:\n{crys}\n".format(crys=self.crys)
        # if self.interstitial != (): str = str + "Interstitial sites: {}\n".format(self.interstitial)
        str = str + "Supercell vectors:\n{}\nChemistry: ".format(self.super.T)
        str = str + ','.join([c + '_i' if n in self.interstitial else c for n, c in enumerate(self.chemistry[:-1])])
        str = str + '\nPositions:\n'
        str = str + '\n'.join([u.__str__() + ': ' + self.chemistry[o] for u,o in zip(self.pos, self.occ)])
        return str

    @staticmethod
    def maketrans(super):
        """
        Takes in a supercell matrix, and returns a list of all translations of the unit cell that
        remain inside the supercell
        :param super: 3x3 integer matrix
        :return size: integer, corresponding to number of unit cells
        :return invsuper: integer matrix inverse of supercell (needs to be divided by size)
        :return trans: list of integer vectors (to be divided by `size`) corresponding to unit cell positions
        """
        size = abs(int(np.round(np.linalg.det(super))))
        invsuper = np.round(np.linalg.inv(super) * size).astype(int)
        maxN = abs(super).max()
        transset = set()
        trans = []
        for nvect in [np.array((n0, n1, n2))
                      for n0 in range(-maxN, maxN + 1)
                      for n1 in range(-maxN, maxN + 1)
                      for n2 in range(-maxN, maxN + 1)]:
            tv = np.dot(invsuper, nvect) % size
            ttup = tuple(tv)
            # if np.all(tv>=0) and np.all(tv<N): trans.append(tv)
            if ttup not in transset:
                trans.append(tv)
                transset.add(ttup)
        if len(trans) != size:
            raise ArithmeticError(
                'Somehow did not generate the correct number of translations? {}!={}'.format(size, len(trans)))
        return size, invsuper, trans

    def makesites(self):
        """
        Generate the array corresponding to the sites; the indexing is based on the translations
        and the atomindices in crys. These may not all be filled when the supercell is finished.
        :return pos: array [N*size, 3] of (supercell) unit cell positions.
        """
        invsize = 1/self.size
        basislist = [np.dot(self.invsuper, self.crys.basis[c][i]) for (c, i) in self.crys.atomindices]
        return np.array([crystal.incell((t+u)*invsize) for t in self.translist for u in basislist])

    def gengroup(self):
        """
        Generate the group operations internal to the supercell
        :return Gset: set of GroupOps
        """
        Glist = []
        invsize = 1/self.size
        for g0 in self.crys.G:
            Rnew = np.dot(self.invsuper, np.dot(g0.rot, self.super))
            if not np.all(Rnew % self.size == 0):
                warnings.warn('Broken symmetry? GroupOp:\n{}\nnot a symmetry operation?'.format(g0),
                              RuntimeWarning, stacklevel=2)
                continue
            coordtrans = []
            for t in self.translist:
                tnew = (np.dot(self.invsuper, g0.trans) + t)*invsize

        return frozenset([crystal.GroupOp.ident([[i for i in range(self.N * self.size)]])])
