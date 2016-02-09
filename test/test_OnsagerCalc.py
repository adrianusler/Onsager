"""
Unit tests for Onsager calculator for vacancy-mediated diffusion.
"""

__author__ = 'Dallas R. Trinkle'

# TODO: additional tests using the 14 frequency model for FCC?

import unittest
import textwrap
import numpy as np
import onsager.OnsagerCalc as OnsagerCalc
import onsager.crystal as crystal


def fivefreq(w0, w1, w2, w3, w4):
    """The solute/solute diffusion coefficient in the 5-freq. model"""
    b = w4/w0
    # 7(1-F) = (10 b^4 + 180.3 b^3 + 924.3 b^2 + 1338.1 b)/ (2 b^4 + 40.1 b^3 + 253/3 b^2 + 596 b + 435.3)
    F7 = 7. - b*(1338.1 + b*(924.3 + b*(180.3 + b*10.)))/\
              (435.3 + b*(596. + b*(253.3 + b*(40.1 + b*2.))))
    p = w4/w3
    return p*w2*(2.*w1 + w3*F7)/(2.*w2 + 2.*w1 + w3*F7)


class CrystalOnsagerTestsSC(unittest.TestCase):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 1.
        self.crys = crystal.Crystal(self.a0*np.eye(3), [np.zeros(3)])
        self.chem = 0
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 1.01*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'Simple Cubic a0={}'.format(self.a0)
        self.correl = 0.653109 # 0.653

    def testtracer(self):
        """Test that arbitrary tracer works as expected"""
        # Make a calculator with one neighbor shell
        print('Crystal: ' + self.crystalname)
        kT = 1.
        Diffusivity = OnsagerCalc.VacancyMediated(self.crys, self.chem, self.sitelist, self.jumpnetwork, 1)
        print('Interaction list:')
        for PS in Diffusivity.interactlist(): print(PS)
        print('omega1 list:')
        for (PS1, PS2) in Diffusivity.omegalist(1)[0]: print(PS1, "->", PS2)
        print('omega2 list:')
        for (PS1, PS2) in Diffusivity.omegalist(2)[0]: print(PS1, "->", PS2)
        thermaldef = {'preV': np.array([1.]), 'eneV': np.array([0.]),
                      'preT0': np.array([1.]), 'eneT0': np.array([0.])}
        thermaldef.update(Diffusivity.maketracerpreene(**thermaldef))
        print('Thermaldef:\n', thermaldef)
        L0vv = np.zeros((3,3))
        om0 = thermaldef['preT0'][0]/thermaldef['preV'][0] * \
              np.exp((thermaldef['eneV'][0]-thermaldef['eneT0'][0])/kT)
        for (i,j), dx in self.jumpnetwork[0]:
            L0vv += 0.5*np.outer(dx,dx) * om0
        L0vv /= len(self.crys.basis[self.chem])
        Lvv, Lss, Lsv, L1vv = Diffusivity.Lij(*Diffusivity.preene2betafree(kT, **thermaldef))
        print('Lvv:\n', Lvv), print('Lss:\n', Lss), print('Lsv:\n', Lsv), print('L1vv:\n', L1vv)
        for L in [Lvv, Lss, Lsv, L1vv]:
            self.assertTrue(np.allclose(L, L[0,0]*np.eye(3)), msg='Diffusivity not isotropic?')
        # No solute drag, so Lsv = -Lvv; Lvv = normal vacancy diffusion
        # all correlation is in that geometric prefactor of Lss.
        self.assertTrue(np.allclose(Lvv, L0vv))
        self.assertTrue(np.allclose(-Lsv, L0vv))
        self.assertTrue(np.allclose(L1vv, 0.))
        self.assertTrue(np.allclose(-Lss, self.correl*Lsv, rtol=1e-6),
                        msg='Failure to match correlation ({}), got {}'.format(
                            self.correl, -Lss[0,0]/Lsv[0,0]))

class CrystalOnsagerTestsFCC(CrystalOnsagerTestsSC):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 1.
        self.crys = crystal.Crystal.FCC(self.a0)
        self.chem = 0
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 0.8*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'Face-Centered Cubic a0={}'.format(self.a0)
        self.correl = 0.78145142

    def testFiveFreq(self):
        """Test whether we can reproduce the five frequency model"""
        print('Five-frequency model, Crystal: ' + self.crystalname)
        kT = 1.
        w0 = 1.0  # bare rate
        w1 = 0.8 * w0  # "swing" rate (vacancy jump around solute)
        w2 = 1.25 * w0  # "exchange" rate (vacancy-solute exchange)
        w3 = 0.5 * w0  # dissociation jump (vacancy away from solute)
        w4 = 1.5 * w0  # association jump (vacancy jump into solute)
        SVprob = w4/w3  # enhanced probability of solute-vacancy complex
        print(textwrap.dedent("""
                               w0={}
                               w1={}
                               w2={}
                               w3={}
                               w4={}
                               prob={}""".format(w0,w1,w2,w3,w4,SVprob)))
        Diffusivity = OnsagerCalc.VacancyMediated(self.crys, self.chem, self.sitelist, self.jumpnetwork, 1)
        print('Interaction list:')
        for PS in Diffusivity.interactlist(): print(PS)
        print('omega1 list:')
        for (PS1, PS2) in Diffusivity.omegalist(1)[0]: print(PS1, "-", PS2)
        print('omega2 list:')
        for (PS1, PS2) in Diffusivity.omegalist(2)[0]: print(PS1, "-", PS2)
        # input the solute/vacancy binding (w4/w3), and use LIMB to take a first stab at the rates
        thermaldef = {'preV': np.array([1.]), 'eneV': np.array([0.]),
                      'preS': np.array([1.]), 'eneS': np.array([0.]),
                      'preT0': np.array([w0]), 'eneT0': np.array([0.]),
                      'preSV': np.array([SVprob]), 'eneSV': np.array([0.])}
        thermaldef.update(Diffusivity.makeLIMBpreene(**thermaldef))
        print('Thermaldef (LIMB):\n', thermaldef)
        # now, we need to get w1, w3, and w4 in there. w3 = dissociation, w4 = association, so:
        # the transition state for the association/dissociation jump is w4 as the outer prob = 1,
        # and the bound probability = w4/w3. The transition state for the "swing" jumps is
        # w1*(w4/w3), where the w4/w3 takes care of the probability factor. Finally, the
        # exchange jump is also w2*(w4/w3).
        thermaldef['preT2'][0] = w2*SVprob
        for j, (PS1, PS2) in enumerate(Diffusivity.omegalist(1)[0]):
            # check to see if the two endpoints of the transition have the solute-vacancy at same distance:
            if np.isclose(np.dot(PS1.dx, PS1.dx), np.dot(PS2.dx, PS2.dx)):
                thermaldef['preT1'][j] = w1*SVprob
            else:
                thermaldef['preT1'][j] = w4
        print('Thermaldef (5-frequency):\n', thermaldef)
        L0vv = np.zeros((3,3))
        om0 = thermaldef['preT0'][0]/thermaldef['preV'][0] * \
              np.exp((thermaldef['eneV'][0]-thermaldef['eneT0'][0])/kT)
        for (i,j), dx in self.jumpnetwork[0]:
            L0vv += 0.5*np.outer(dx,dx) * om0
        L0vv /= self.crys.N
        Lvv, Lss, Lsv, L1vv = Diffusivity.Lij(*Diffusivity.preene2betafree(kT, **thermaldef))
        print('Lvv:\n', Lvv), print('Lss:\n', Lss), print('Lsv:\n', Lsv), print('L1vv:\n', L1vv)
        for L in [Lvv, Lss, Lsv, L1vv]:
            self.assertTrue(np.allclose(L, L[0,0]*np.eye(3)), msg='Diffusivity not isotropic?')
        self.assertTrue(np.allclose(Lvv, L0vv))
        Ds5freq = self.a0**2 * fivefreq(w0, w1, w2, w3, w4)
        self.assertAlmostEqual(Lss[0, 0], Ds5freq, delta=1e-3,
                               msg=textwrap.dedent("""
                               Did not match the 5-freq. model for
                               w0={}
                               w1={}
                               w2={}
                               w3={}
                               w4={}
                               Lss={}
                               Ds5={}""".format(w0,w1,w2,w3,w4,Lss[0,0],Ds5freq)))


class CrystalOnsagerTestsBCC(CrystalOnsagerTestsSC):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 1.
        self.crys = crystal.Crystal.BCC(self.a0)
        self.chem = 0
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 0.87*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'Body-Centered Cubic a0={}'.format(self.a0)
        self.correl = 0.727194 # 0.727

class CrystalOnsagerTestsDiamond(CrystalOnsagerTestsSC):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 2.
        self.crys = crystal.Crystal(self.a0*np.array([[0,0.5,0.5],[0.5,0,0.5],[0.5,0.5,0]]),
                                    [np.array([-0.125,-0.125,-0.125]),
                                     np.array([0.125,0.125,0.125])])
        self.chem = 0
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 0.45*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'Diamond Cubic a0={}'.format(self.a0)
        self.correl = 0.5

class CrystalOnsagerTestsNbO(CrystalOnsagerTestsSC):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 1.
        self.crys = crystal.Crystal(self.a0*np.eye(3),
                                    [[np.array([0,0.5,0.5]),np.array([0.5,0,0.5]),np.array([0.5,0.5,0])],
                                     [np.array([0.5,0,0]), np.array([0,0.5,0]), np.array([0,0,0.5])]],
                                    ['Nb', 'O'])
        self.chem = 1 # do on the oxygen sublattice, though it works on Nb too
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 0.80*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'NbO (oxygen sublattice) a0={}'.format(self.a0)
        self.correl = 0.688916  # doi://10.1080/01418618308234882  (Koiwa & Ishioka paper)

class CrystalOnsagerTestsHCP(unittest.TestCase):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 1.
        self.crys = crystal.Crystal.HCP(1.)
        self.chem = 0
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 1.01*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'Hexagonal Closed-Packed a0={} c0=sqrt(8/3)'.format(self.a0)
        # Correlation factors from doi://10.1080/01418617808239187
        # S. Ishioka and M. Koiwa, Phil. Mag. A 37, 517-533 (1978)
        # which they say matches older results in K. Compaan and C. Haven,
        # Trans. Faraday Soc. 52, 786 (1958) and ibid. 54, 1498
        self.correlx = 0.78120489
        self.correlz = 0.78145142

    def testtracer(self):
        """Test that HCP tracer works as expected"""
        # Make a calculator with one neighbor shell
        print('Crystal: ' + self.crystalname)
        kT = 1.
        Diffusivity = OnsagerCalc.VacancyMediated(self.crys, self.chem, self.sitelist, self.jumpnetwork, 1)
        print('kpt mesh: ', Diffusivity.GFcalc.kptgrid)
        print('Interaction list:')
        for PS in Diffusivity.interactlist(): print(PS)
        print('omega1 list:')
        for (PS1, PS2) in Diffusivity.omegalist(1)[0]: print(PS1, "-", PS2)
        print('omega2 list:')
        for (PS1, PS2) in Diffusivity.omegalist(2)[0]: print(PS1, "-", PS2)
        thermaldef = {'preV': np.array([1.]), 'eneV': np.array([0.]),
                      'preT0': np.array([1.,1.]), 'eneT0': np.array([0.,0.])}
        thermaldef.update(Diffusivity.maketracerpreene(**thermaldef))
        print('Thermaldef:\n', thermaldef)
        L0vv = np.zeros((3,3))
        om0 = thermaldef['preT0'][0]/thermaldef['preV'][0] * \
              np.exp((thermaldef['eneV'][0]-thermaldef['eneT0'][0])/kT)
        for jumplist in self.jumpnetwork:
            for (i,j), dx in jumplist:
                L0vv += 0.5*np.outer(dx,dx) * om0
        L0vv /= self.crys.N
        Lvv, Lss, Lsv, L1vv = Diffusivity.Lij(*Diffusivity.preene2betafree(kT, **thermaldef))
        print('Lvv:\n', Lvv), print('Lss:\n', Lss), print('Lsv:\n', Lsv), print('L1vv:\n', L1vv)
        # we leave out Lss since it is not, in fact, isotropic!
        for L in [Lvv, Lsv, L1vv]:
            self.assertTrue(np.allclose(L, L[0,0]*np.eye(3), atol=1e-8),
                            msg='Diffusivity not isotropic?')
        # No solute drag, so Lsv = -Lvv; Lvv = normal vacancy diffusion
        # all correlation is in that geometric prefactor of Lss.
        self.assertTrue(np.allclose(Lvv, L0vv))
        self.assertTrue(np.allclose(-Lsv, L0vv))
        self.assertTrue(np.allclose(L1vv, 0.))
        correlmat = np.array([[self.correlx, 0, 0], [0, self.correlx, 0], [0, 0, self.correlz]])
        self.assertTrue(np.allclose(-Lss, np.dot(correlmat, Lsv), rtol=1e-7),
                        msg='Failure to match correlation ({}, {}), got {}, {}'.format(
                            self.correlx, self.correlz, -Lss[0,0]/Lsv[0,0], -Lss[2,2]/Lsv[2,2]))

class CrystalOnsagerTestsB2(unittest.TestCase):
    """Test our new crystal-based vacancy-mediated diffusion calculator"""

    longMessage = False
    def setUp(self):
        self.a0 = 1.
        self.crys = crystal.Crystal.BCC(self.a0)
        self.chem = 0
        self.jumpnetwork = self.crys.jumpnetwork(self.chem, 0.87*self.a0)
        self.sitelist = self.crys.sitelist(self.chem)
        self.crystalname = 'Body-Centered Cubic a0={}'.format(self.a0)

        self.crys2 = crystal.Crystal(self.a0*np.eye(3), [np.zeros(3), np.array([0.45, 0.45, 0.45])], NOSYM=True)
        self.jumpnetwork2 = self.crys2.jumpnetwork(self.chem, 0.99*self.a0)
        self.sitelist2 = self.crys2.sitelist(self.chem)
        self.crystalname2 = 'B2 a0={}'.format(self.a0)

        # self.crys2 = crystal.Crystal(self.crys.lattice, self.crys.basis, NOSYM=True)
        # self.jumpnetwork2 = self.crys2.jumpnetwork(self.chem, 0.87*self.a0)
        # self.sitelist2 = self.crys2.sitelist(self.chem)
        # self.crystalname2 = 'BCC (unsymmetric) a0={}'.format(self.a0)

    def testtracer(self):
        """Test that BCC mapped onto B2 match exactly"""
        # Make a calculator with one neighbor shell
        print('Crystal: ' + self.crystalname)
        print('Crystal2: ' + self.crystalname2)
        kT = 1.
        Diffusivity = OnsagerCalc.VacancyMediated(self.crys, self.chem, self.sitelist, self.jumpnetwork, 1)
        Diffusivity2 = OnsagerCalc.VacancyMediated(self.crys2, self.chem, self.sitelist2, self.jumpnetwork2, 1)
        for tag in ('solute-vacancy', 'omega0', 'omega1', 'omega2'):
            print(tag + ' list:')
            for str, mult in ((taglist[0], len(taglist)) for taglist in Diffusivity.tags[tag]):
                print(str, 'x', mult)
            print(tag + ' list2:')
            for str, mult in ((taglist[0], len(taglist)) for taglist in Diffusivity2.tags[tag]):
                print(str, 'x', mult)
        thermaldef = {'preV': np.array([1.]), 'eneV': np.array([0.]),
                      'preT0': np.array([1.]), 'eneT0': np.array([0.])}
        thermaldef.update(Diffusivity.maketracerpreene(**thermaldef))
        print('Thermaldef:\n', thermaldef)
        thermaldef2 = {'preV': np.ones(len(self.sitelist2)), 'eneV': np.zeros(len(self.sitelist2)),
                      'preT0': np.ones(len(self.jumpnetwork2)), 'eneT0': np.zeros(len(self.jumpnetwork2))}
        thermaldef2.update(Diffusivity2.maketracerpreene(**thermaldef2))
        print('Thermaldef2:\n', thermaldef2)

        Lvv, Lss, Lsv, L1vv = Diffusivity.Lij(*Diffusivity.preene2betafree(kT, **thermaldef))
        Lvv2, Lss2, Lsv2, L1vv2 = Diffusivity2.Lij(*Diffusivity.preene2betafree(kT, **thermaldef2))
        for Lname in ('Lvv', 'Lss', 'Lsv', 'L1vv', 'Lvv2', 'Lss2', 'Lsv2', 'L1vv2'):
            print(Lname)
            print(locals()[Lname])
        for L, Lp in zip([Lvv, Lss, Lsv, L1vv], [Lvv2, Lss2, Lsv2, L1vv2]):
            self.assertTrue(np.allclose(L, Lp), msg="Diffusivity doesn't match?")


class InterstitialTests(unittest.TestCase):
    """Tests for our interstitial diffusion calculator"""

    def setUp(self):
        # Both HCP and FCC diffusion networks with octahedral and tetrahedral sites
        self.a0 = 3
        self.c_a = np.sqrt(8./3.)
        self.fcclatt = self.a0*np.array([[0, 0.5, 0.5],
                                         [0.5, 0, 0.5],
                                         [0.5, 0.5, 0]])
        self.fccbasis = [[np.zeros(3)], [np.array([0.5,0.5,-0.5]),
                                         np.array([0.25,0.25,0.25]),
                                         np.array([0.75,0.75,0.75])]]
        self.hexlatt = self.a0*np.array([[0.5, 0.5, 0],
                                         [-np.sqrt(0.75), np.sqrt(0.75), 0],
                                         [0, 0, self.c_a]])
        self.hcpbasis = [[np.array([1./3.,2./3.,0.25]),np.array([2./3.,1./3.,0.75])],
                         [np.array([0.,0.,0.]), np.array([0.,0.,0.5]),
                          np.array([1./3.,2./3.,0.625]), np.array([1./3.,2./3.,0.875]),
                          np.array([2./3.,1./3.,0.125]), np.array([2./3.,1./3.,0.375])]]
        self.HCP_intercrys = crystal.Crystal(self.hexlatt, self.hcpbasis)
        self.HCP_jumpnetwork = self.HCP_intercrys.jumpnetwork(1, self.a0*0.7) # tuned to avoid t->t in basal plane
        self.HCP_sitelist = self.HCP_intercrys.sitelist(1)
        self.Dhcp = OnsagerCalc.Interstitial(self.HCP_intercrys, 1, self.HCP_sitelist, self.HCP_jumpnetwork)
        self.FCC_intercrys = crystal.Crystal(self.fcclatt, self.fccbasis)
        self.FCC_jumpnetwork = self.FCC_intercrys.jumpnetwork(1, self.a0*0.48)
        self.FCC_sitelist = self.FCC_intercrys.sitelist(1)
        self.Dfcc = OnsagerCalc.Interstitial(self.FCC_intercrys, 1, self.FCC_sitelist, self.FCC_jumpnetwork)

    def testVectorBasis(self):
        """Do we correctly analyze our crystals regarding their symmetry?"""
        self.assertEqual(self.Dhcp.NV, 1)
        self.assertTrue(self.Dhcp.omega_invertible)
        self.assertTrue(np.allclose(self.Dhcp.VV[:,:,0,0], np.array([[0,0,0],[0,0,0],[0,0,1]])))
        self.assertEqual(self.Dfcc.NV, 0)
        self.assertTrue(self.Dfcc.omega_invertible)

    def testInverseMap(self):
        """Do we correctly construct the inverse map?"""
        for D in [self.Dhcp, self.Dfcc]:
            for i,w in enumerate(D.invmap):
                self.assertTrue(any(i==j for j in D.sitelist[w]))
        self.assertEqual(len(self.HCP_sitelist), 2)
        self.assertEqual(len(self.FCC_sitelist), 2)
        self.assertEqual(len(self.HCP_jumpnetwork), 2)
        self.assertEqual(len(self.FCC_jumpnetwork), 1)

    def testGroupOps(self):
        """Do we have reasonable group op. lists?"""
        center = np.zeros(3, dtype=int)
        for D in [self.Dfcc, self.Dhcp]:
            for sites, groups in zip(D.sitelist, D.sitegroupops):
                i0 = sites[0]
                for site, g in zip(sites, groups):
                    # group operation g transforms the site (c, i0) into (c, i)
                    R, (c,i) = D.crys.g_pos(g, center, (D.chem, i0))
                    self.assertEqual(site, i)
            for jumps, groups in zip(D.jumpnetwork, D.jumpgroupops):
                (i0, j0), dx0 = jumps[0]
                for ((i, j), dx), g in zip(jumps, groups):
                    R, (c,inew) = D.crys.g_pos(g, center, (D.chem, i0))
                    R, (c,jnew) = D.crys.g_pos(g, center, (D.chem, j0))
                    dxnew = D.crys.g_direc(g, dx0)
                    if inew==i:
                        failmsg = "({},{}), {} != ({},{}), {}".format(inew,jnew,dxnew, i, j, dx)
                        self.assertEqual(inew, i, msg=failmsg)
                        self.assertEqual(jnew, j, msg=failmsg)
                        self.assertTrue(np.allclose(dxnew, dx), msg=failmsg)
                    else:
                        # reverse transition
                        failmsg = "({},{}), {} != ({},{}), {}".format(inew,jnew,dxnew, j, i, -dx)
                        self.assertEqual(inew, j, msg=failmsg)
                        self.assertEqual(jnew, i, msg=failmsg)
                        self.assertTrue(np.allclose(dxnew, -dx), msg=failmsg)

    def testSymmBasis(self):
        """Do we have a reasonable symmetric tensor basis?"""
        for basis in self.Dfcc.siteSymmTensorBasis:
            self.assertEqual(len(basis), 1)
        for basis in self.Dfcc.jumpSymmTensorBasis:
            self.assertEqual(len(basis), 2)
        for basis in self.Dhcp.siteSymmTensorBasis:
            self.assertEqual(len(basis), 2)
        for basis, jumps in zip(self.Dhcp.jumpSymmTensorBasis, self.Dhcp.jumpnetwork):
            if len(jumps) == 4:
                self.assertEqual(len(basis), 2)
            else:
                self.assertEqual(len(basis), 4)

    def testSiteProb(self):
        """Do we correctly construct our site probabilities?"""
        # HCP first
        preoct = 1
        pretet = 2
        BEoct = 0
        BEtet = np.log(2) # so exp(-beta*E) = 1/2
        pre = np.zeros(len(self.HCP_sitelist))
        BE = np.zeros(len(self.HCP_sitelist))
        pre[self.Dhcp.invmap[0]] = preoct
        pre[self.Dhcp.invmap[2]] = pretet
        BE[self.Dhcp.invmap[0]] = BEoct
        BE[self.Dhcp.invmap[2]] = BEtet
        # With this, we have 6 sites total, and they should all have equal probability: so 1/6 is the answer.
        self.assertTrue(np.allclose(np.ones(self.Dhcp.N)/self.Dhcp.N, self.Dhcp.siteprob(pre, BE)))
        # FCC
        pre = np.zeros(len(self.FCC_sitelist))
        BE = np.zeros(len(self.FCC_sitelist))
        pre[self.Dfcc.invmap[0]] = preoct
        pre[self.Dfcc.invmap[1]] = pretet
        BE[self.Dfcc.invmap[0]] = BEoct
        BE[self.Dfcc.invmap[1]] = BEtet
        # With this, we have 3 sites total, and they should all have equal probability: so 1/3 is the answer.
        self.assertTrue(np.allclose(np.ones(self.Dfcc.N)/self.Dfcc.N, self.Dfcc.siteprob(pre, BE)))

    def testRatelist(self):
        """Do we correctly construct our rates?"""
        # FCC first
        preoct = 1
        pretet = 2
        BEoct = 0
        BEtet = np.log(2) # so exp(-beta*E) = 1/2
        preTrans = 10
        BETrans = np.log(10) # so that our rate should be 10*exp(-BET) / (1*exp(0)) = 1
        pre = np.zeros(len(self.FCC_sitelist))
        BE = np.zeros(len(self.FCC_sitelist))
        pre[self.Dfcc.invmap[0]] = preoct
        pre[self.Dfcc.invmap[1]] = pretet
        BE[self.Dfcc.invmap[0]] = BEoct
        BE[self.Dfcc.invmap[1]] = BEtet
        preT = np.array([preTrans])
        BET = np.array([BETrans])
        self.assertTrue(all( np.isclose(rate, 1)
                             for ratelist in self.Dfcc.ratelist(pre, BE, preT, BET)
                             for rate in ratelist))
        # try changing the prefactor for tetrahedral...
        pre[self.Dfcc.invmap[1]] = 1
        ratelist = self.Dfcc.ratelist(pre, BE, preT, BET)
        for ((i, j), dx), rate in zip(self.Dfcc.jumpnetwork[0], ratelist[0]):
            if i==0: self.assertAlmostEqual(rate, 1) # oct->tet
            else:    self.assertAlmostEqual(rate, 2) # tet->oct

        # HCP
        pre = np.zeros(len(self.HCP_sitelist))
        BE = np.zeros(len(self.HCP_sitelist))
        pre[self.Dhcp.invmap[0]] = preoct
        pre[self.Dhcp.invmap[2]] = pretet
        BE[self.Dhcp.invmap[0]] = BEoct
        BE[self.Dhcp.invmap[2]] = BEtet
        preTransOT = 10.
        preTransTT = 100.
        BETransOT = np.log(10.)
        BETransTT = np.log(10.)
        preT = np.zeros(len(self.Dhcp.jumpnetwork))
        BET = np.zeros(len(self.Dhcp.jumpnetwork))
        for i, jump in enumerate(self.Dhcp.jumpnetwork):
            if len(jump) == 4:
                preT[i] = preTransTT
                BET[i] = BETransTT
            else:
                preT[i] = preTransOT
                BET[i] = BETransOT
        # oct->tet jumps have rate 1, tet->tet jumps have rate 10.
        ratelist = self.Dhcp.ratelist(pre, BE, preT, BET)
        for jumps, rates in zip(self.Dhcp.jumpnetwork, ratelist):
            for ((i, j), dx), rate in zip(jumps, rates):
                if i<2 or j<2: self.assertAlmostEqual(rate, 1) # oct->tet
                else:          self.assertAlmostEqual(rate, 10) # tet->oct

    def testDiffusivity(self):
        """Diffusivity"""
        # What we all came for...
        preoct = 1.
        pretet = 2.
        BEoct = 0.
        BEtet = np.log(2) # so exp(-beta*E) = 1/2
        preTrans = 10.
        BETrans = np.log(10) # so that our rate should be 10*exp(-BET) / (1*exp(0)) = 1
        pre = np.zeros(len(self.FCC_sitelist))
        BE = np.zeros(len(self.FCC_sitelist))
        pre[self.Dfcc.invmap[0]] = preoct
        pre[self.Dfcc.invmap[1]] = pretet
        BE[self.Dfcc.invmap[0]] = BEoct
        BE[self.Dfcc.invmap[1]] = BEtet
        preT = np.array([preTrans])
        BET = np.array([BETrans])

        Dfcc_anal = 0.5*self.a0**2 *preTrans*np.exp(-BETrans)/(preoct*np.exp(-BEoct) + 2*pretet*np.exp(-BEtet))
        self.assertTrue(np.allclose(Dfcc_anal*np.eye(3), self.Dfcc.diffusivity(pre, BE, preT, BET)))

        # HCP
        pre = np.zeros(len(self.HCP_sitelist))
        BE = np.zeros(len(self.HCP_sitelist))
        pre[self.Dhcp.invmap[0]] = preoct
        pre[self.Dhcp.invmap[2]] = pretet
        BE[self.Dhcp.invmap[0]] = BEoct
        BE[self.Dhcp.invmap[2]] = BEtet
        preTransOT = 10.
        preTransTT = 100.
        BETransOT = np.log(10.)
        BETransTT = np.log(10.)
        preT = np.zeros(len(self.Dhcp.jumpnetwork))
        BET = np.zeros(len(self.Dhcp.jumpnetwork))
        for i, jump in enumerate(self.Dhcp.jumpnetwork):
            if len(jump) == 4:
                preT[i] = preTransTT
                BET[i] = BETransTT
            else:
                preT[i] = preTransOT
                BET[i] = BETransOT
        Dhcp_basal = self.a0**2 * preTransOT*np.exp(-BETransOT)/(preoct*np.exp(-BEoct) + 2*pretet*np.exp(-BEtet))
        Dhcp_c = 0.75*self.c_a**2 * Dhcp_basal/ (3*preTransOT/preTransTT * np.exp(-BETransOT+BETransTT) + 2)
        D = self.Dhcp.diffusivity(pre, BE, preT, BET)
        self.assertTrue(np.allclose(np.array([[Dhcp_basal,0,0],[0,Dhcp_basal,0],[0,0,Dhcp_c]]), D),
                        msg="Diffusivity doesn't match:\n{}\nnot {} and {}".format(D, Dhcp_basal,Dhcp_c))

    def testDiffusivityBarrier(self):
        """Diffusivity barriers"""
        # What we all came for...
        preoct = 1.
        pretet = 2.
        BEoct = 0.
        BEtet = np.log(2) # so exp(-beta*E) = 1/2
        preTrans = 10.
        BETrans = np.log(10) # so that our rate should be 10*exp(-BET) / (1*exp(0)) = 1
        pre = np.zeros(len(self.FCC_sitelist))
        BE = np.zeros(len(self.FCC_sitelist))
        pre[self.Dfcc.invmap[0]] = preoct
        pre[self.Dfcc.invmap[1]] = pretet
        BE[self.Dfcc.invmap[0]] = BEoct
        BE[self.Dfcc.invmap[1]] = BEtet
        preT = np.array([preTrans])
        BET = np.array([BETrans])

        Eave = (preoct*np.exp(-BEoct)*BEoct + 2*pretet*np.exp(-BEtet)*BEtet)/\
               (preoct*np.exp(-BEoct) + 2*pretet*np.exp(-BEtet))
        Dfcc, DfccE = self.Dfcc.diffusivity(pre, BE, preT, BET, CalcDeriv=True)
        # rather than use inv and dot, we use solve; NOTE: we compute the derivative and NOT the
        # logarithmic derivative in case Dfcc is, e.g., 2D so has no diffusivity in a particular direction
        Eb = np.linalg.solve(Dfcc, DfccE)
        failmsg = """
Energy barrier tensor:
{}
BETrans: {}  BEoct: {}  BEtet: {}  Eave: {}
""".format(Eb, BETrans, BEoct, BEtet, Eave)
        self.assertTrue(np.allclose((BETrans-Eave)*np.eye(3), Eb), msg=failmsg)

        # HCP
        pre = np.zeros(len(self.HCP_sitelist))
        BE = np.zeros(len(self.HCP_sitelist))
        pre[self.Dhcp.invmap[0]] = preoct
        pre[self.Dhcp.invmap[2]] = pretet
        BE[self.Dhcp.invmap[0]] = BEoct
        BE[self.Dhcp.invmap[2]] = BEtet
        preTransOT = 10.
        preTransTT = 100.
        BETransOT = np.log(10.)
        BETransTT = np.log(10.)
        preT = np.zeros(len(self.Dhcp.jumpnetwork))
        BET = np.zeros(len(self.Dhcp.jumpnetwork))
        for i, jump in enumerate(self.Dhcp.jumpnetwork):
            if len(jump) == 4:
                preT[i] = preTransTT
                BET[i] = BETransTT
            else:
                preT[i] = preTransOT
                BET[i] = BETransOT
        Eave = (preoct*np.exp(-BEoct)*BEoct + 2*pretet*np.exp(-BEtet)*BEtet)/\
               (preoct*np.exp(-BEoct) + 2*pretet*np.exp(-BEtet))
        Dhcp, DhcpE = self.Dhcp.diffusivity(pre, BE, preT, BET, CalcDeriv=True)
        # rather than use inv and dot, we use solve; NOTE: we compute the derivative and NOT the
        # logarithmic derivative in case Dfcc is, e.g., 2D so has no diffusivity in a particular direction
        Eb = np.linalg.solve(Dhcp, DhcpE)
        Eb_anal = np.eye(3)
        Eb_anal[0,0] = BETransOT - Eave
        Eb_anal[1,1] = BETransOT - Eave
        lambdaTO = preTransOT/pretet * np.exp(BETransOT - BEtet)
        lambdaTT = preTransTT/pretet * np.exp(BETransTT - BEtet)
        Eb_anal[2,2] = (3*lambdaTO*BETransTT + 2*lambdaTT*BETransOT)/(3*lambdaTO + 2*lambdaTT) - Eave
        failmsg = """
Energy barrier tensor:
{}
Analytic:
{}
BETrans: {}  BEoct: {}  BEtet: {}  Eave: {}
""".format(Eb, Eb_anal, BETrans, BEoct, BEtet, Eave)
        self.assertTrue(np.allclose(Eb_anal, Eb), msg=failmsg)

    def testBias(self):
        """Quick check that the bias and correction are computed correctly"""
        rumpledcrys = crystal.Crystal(np.array([[2.,0.,0.],[0.,1.,0.],[0.,0.,10.]]),
                                      [np.array([0.,0.,0.]), np.array([0.5,0,0.1])])
        sitelist = rumpledcrys.sitelist(0)
        jumpnetwork = rumpledcrys.jumpnetwork(0, 1.5)
        diffuser = OnsagerCalc.Interstitial(rumpledcrys, 0, sitelist, jumpnetwork)
        pre = np.array([1,]*len(sitelist))
        BE = np.array([0,]*len(sitelist))
        preT = np.array([1,]*len(jumpnetwork))
        BET = np.array([0,]*len(jumpnetwork))
        D0 = diffuser.diffusivity(pre, BE, preT, BET)
        # despite the fact that there are jumps that go +z and -z, the diffusivity for this
        # rumpled 2D crystal should be exactly 0 in any z component
        self.assertTrue(np.allclose(D0[:,2], 0))

    def testSymmTensorMapping(self):
        """Do we correctly map our elastic dipoles onto sites and transitions?"""
        # put a little "error" in from our calculation... shouldn't really be present
        dipole = [np.array([[1.,1e-4, -2e-4],[1e-4,1.,3e-4],[-2e-4, 3e-4, 1.]]),
                  np.array([[1.,1e-4, -2e-4],[1e-4,1.,3e-4],[-2e-4, 3e-4, 1.]])]
        (i,j), dx = self.Dfcc.jumpnetwork[0][0] # our representative jump
        dipoleT = [ -0.5*np.eye(3) + 2.*np.outer(dx, dx)] # this should remain unchanged
        sitedipoles = self.Dfcc.siteDipoles(dipole)
        jumpdipoles = self.Dfcc.jumpDipoles(dipoleT)
        for dip in sitedipoles:
            self.assertTrue(np.allclose(dip, np.eye(3)))
        self.assertTrue(np.allclose(dipoleT[0], jumpdipoles[0][0]))
        self.assertTrue(np.allclose(np.trace(dipoleT[0])*np.eye(3)/3., sum(jumpdipoles[0])/len(jumpdipoles[0])))
        for ((i,j), dx), dipole in zip(self.Dfcc.jumpnetwork[0], jumpdipoles[0]):
            self.assertTrue(np.allclose(-0.5*np.eye(3) + 2.*np.outer(dx, dx), dipole))

    def testFCCElastodiffusion(self):
        """Elastodiffusion tensor without correlation; compare with finite difference"""
        # FCC first:
        preoct = 1.
        pretet = 0.5
        BEoct = 0.
        BEtet = np.log(2) # so exp(-beta*E) = 1/2
        preTrans = 10.
        BETrans = np.log(10) # so that our rate should be 10*exp(-BET) / (1*exp(0)) = 1
        pre = np.zeros(len(self.FCC_sitelist))
        BE = np.zeros(len(self.FCC_sitelist))
        pre[self.Dfcc.invmap[0]] = preoct
        pre[self.Dfcc.invmap[1]] = pretet
        BE[self.Dfcc.invmap[0]] = BEoct
        BE[self.Dfcc.invmap[1]] = BEtet
        preT = np.array([preTrans])
        BET = np.array([BETrans])

        octP = 1.
        tetP = -1.
        transPpara = 0.5
        transPperp = -0.5
        dipole = [0, 0]
        dipole[self.Dfcc.invmap[0]] = octP*np.eye(3)
        dipole[self.Dfcc.invmap[1]] = tetP*np.eye(3)
        (i,j), dx = self.Dfcc.jumpnetwork[0][0] # our representative jump
        dipoleT = [ transPperp*np.eye(3) + (transPpara-transPperp)*np.outer(dx, dx)/np.dot(dx, dx)]
        sitedipoles = self.Dfcc.siteDipoles(dipole)
        jumpdipoles = self.Dfcc.jumpDipoles(dipoleT)

        # strain
        D0, Dp = self.Dfcc.elastodiffusion(pre, BE, dipole, preT, BET, dipoleT)
        # test for correct symmetry of our tensors:
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(D0[i,j], D0[j,i], msg="{}\nnot symmetric".format(D0))
                for k in range(3):
                    for l in range(3):
                        self.assertAlmostEqual(Dp[i,j,k,l], Dp[j,i,k,l],
                                               msg="{}{}{}{} != {}{}{}{}\n{}\nnot symmetric".format(i,j,k,l, j,i,k,l, Dp))
                        self.assertAlmostEqual(Dp[i,j,k,l], Dp[i,j,l,k],
                                               msg="{}{}{}{} != {}{}{}{}\n{}\nnot symmetric".format(i,j,k,l, i,j,l,k, Dp))
                        self.assertAlmostEqual(Dp[i,j,k,l], Dp[j,i,l,k],
                                               msg="{}{}{}{} != {}{}{}{}\n{}\nnot symmetric".format(i,j,k,l, j,i,l,k, Dp))
        eps = 1e-4
        # use Voigtstrain to run through the 6 strains; np.eye(6) generates 6 unit vectors
        for straintype in [ crystal.Voigtstrain(*s) for s in np.eye(6) ]:
            strainmat = eps*straintype
            strainedFCCpos = self.FCC_intercrys.strain(strainmat)
            strainedFCCpos_jumpnetwork = strainedFCCpos.jumpnetwork(1, self.a0*0.48)
            strainedFCCpos_sitelist = strainedFCCpos.sitelist(1)
            strainedDfccpos = OnsagerCalc.Interstitial(strainedFCCpos, 1,
                                                       strainedFCCpos_sitelist,
                                                       strainedFCCpos_jumpnetwork)
            self.assertTrue(strainedDfccpos.omega_invertible)

            strainedpospre = np.zeros(len(strainedFCCpos_sitelist))
            strainedposBE = np.zeros(len(strainedFCCpos_sitelist))
            # apply dipoles to site energies:
            for octind in range(1):
                strainedpospre[strainedDfccpos.invmap[octind]] = preoct
                strainedposBE[strainedDfccpos.invmap[octind]] = BEoct - np.sum(sitedipoles[octind] * strainmat)
            for tetind in range(1,3):
                strainedpospre[strainedDfccpos.invmap[tetind]] = pretet
                strainedposBE[strainedDfccpos.invmap[tetind]] = BEtet - np.sum(sitedipoles[tetind] * strainmat)
            strainedposBET = np.zeros(len(strainedFCCpos_jumpnetwork))
            strainedpospreT = np.zeros(len(strainedFCCpos_jumpnetwork))
            # this gets more complicated...
            for ind, jumps in enumerate(strainedFCCpos_jumpnetwork):
                (i,j), dx = jumps[0]
                dx0 = np.linalg.solve(np.eye(3) + strainmat, dx)
                dip = transPperp*np.eye(3) +(transPpara-transPperp)*np.outer(dx0, dx0)/np.dot(dx0, dx0)
                strainedpospreT[ind] = preTrans
                strainedposBET[ind] = BETrans - np.sum(dip*strainmat)

            strainedFCCneg = self.FCC_intercrys.strain(-strainmat)
            strainedFCCneg_jumpnetwork = strainedFCCneg.jumpnetwork(1, self.a0*0.48)
            strainedFCCneg_sitelist = strainedFCCneg.sitelist(1)
            strainedDfccneg = OnsagerCalc.Interstitial(strainedFCCneg, 1,
                                                       strainedFCCneg_sitelist,
                                                       strainedFCCneg_jumpnetwork)
            self.assertTrue(strainedDfccneg.omega_invertible)

            strainednegpre = np.zeros(len(strainedFCCneg_sitelist))
            strainednegBE = np.zeros(len(strainedFCCneg_sitelist))
            # apply dipoles to site energies:
            for octind in range(1):
                strainednegpre[strainedDfccneg.invmap[octind]] = preoct
                strainednegBE[strainedDfccneg.invmap[octind]] = BEoct + np.sum(sitedipoles[octind] * strainmat)
            for tetind in range(1,3):
                strainednegpre[strainedDfccneg.invmap[tetind]] = pretet
                strainednegBE[strainedDfccneg.invmap[tetind]] = BEtet + np.sum(sitedipoles[tetind] * strainmat)
            strainednegBET = np.zeros(len(strainedFCCneg_jumpnetwork))
            strainednegpreT = np.zeros(len(strainedFCCneg_jumpnetwork))
            # this gets more complicated...
            for ind, jumps in enumerate(strainedFCCneg_jumpnetwork):
                (i,j), dx = jumps[0]
                dx0 = np.linalg.solve(np.eye(3) - strainmat, dx)
                dip = transPperp*np.eye(3) +(transPpara-transPperp)*np.outer(dx0, dx0)/np.dot(dx0, dx0)
                strainednegpreT[ind] = preTrans
                strainednegBET[ind] = BETrans + np.sum(dip*strainmat)
            Deps = strainedDfccpos.diffusivity(strainedpospre, strainedposBE, strainedpospreT, strainedposBET) -\
                   strainedDfccneg.diffusivity(strainednegpre, strainednegBE, strainednegpreT, strainednegBET)

            Deps /= 2*eps
            Deps0 = np.tensordot(Dp, strainmat, axes=((2,3), (0,1)))/eps
            failmsg = """
strainmatrix:
{}
D0:
{}
finite difference:
{}
elastodiffusion:
{}""".format(strainmat, D0, Deps, Deps0)
            self.assertTrue(np.allclose(Deps, Deps0, rtol=2*eps, atol=2*eps), msg=failmsg)

    def testHCPElastodiffusion(self):
        """Elastodiffusion tensor with correlation; compare with finite difference"""
        # HCP; note: *uncorrelated* requires lambda(t->t) = 1.5*lambda(t->o)
        preoct = 1.
        pretet = 0.5
        BEoct = 0.
        BEtet = np.log(2) # so exp(-beta*E) = 1/2
        preTransOT = 10.
        preTransTT = 10.
        BETransOT = np.log(10.)
        BETransTT = np.log(10.)

        pre = np.zeros(len(self.HCP_sitelist))
        BE = np.zeros(len(self.HCP_sitelist))
        pre[self.Dhcp.invmap[0]] = preoct
        pre[self.Dhcp.invmap[2]] = pretet
        BE[self.Dhcp.invmap[0]] = BEoct
        BE[self.Dhcp.invmap[2]] = BEtet
        preT = np.zeros(len(self.Dhcp.jumpnetwork))
        BET = np.zeros(len(self.Dhcp.jumpnetwork))
        for i, jump in enumerate(self.Dhcp.jumpnetwork):
            if len(jump) == 4:
                preT[i] = preTransTT
                BET[i] = BETransTT
            else:
                preT[i] = preTransOT
                BET[i] = BETransOT

        octPb = 1.
        octPc = 2.
        tetPb = -1.
        tetPc = -2.
        transPpara = 0.5
        transPperp = -0.5
        dipole = [0, 0]
        dipole[self.Dhcp.invmap[0]] = np.array([[octPb,0,0],[0,octPb,0],[0,0,octPc]])
        dipole[self.Dhcp.invmap[2]] = np.array([[tetPb,0,0],[0,tetPb,0],[0,0,tetPc]])
        dipoleT = []
        # use the same dipole expression for all jumps:
        for jumps in self.Dhcp.jumpnetwork:
            (i,j), dx = jumps[0] # our representative jump
            dipoleT.append(transPperp*np.eye(3) + (transPpara-transPperp)*np.outer(dx, dx)/np.dot(dx, dx))
        sitedipoles = self.Dhcp.siteDipoles(dipole)
        jumpdipoles = self.Dhcp.jumpDipoles(dipoleT)
        # test that site dipoles are created correctly
        for i, d in enumerate(sitedipoles):
            if i<2:
                self.assertTrue(np.allclose(d, np.array([[octPb,0,0],[0,octPb,0],[0,0,octPc]])))
            else:
                self.assertTrue(np.allclose(d, np.array([[tetPb,0,0],[0,tetPb,0],[0,0,tetPc]])))
        # test that jump dipoles are created correctly
        for jumps, dipoles in zip(self.Dhcp.jumpnetwork, jumpdipoles):
            for (ij, dx), d in zip(jumps, dipoles):
                dip = transPperp*np.eye(3) + (transPpara-transPperp)*np.outer(dx, dx)/np.dot(dx, dx)
                self.assertTrue(np.allclose(dip, d))

        # strain
        eps = 1e-4
        D0, Dp = self.Dhcp.elastodiffusion(pre, BE, dipole, preT, BET, dipoleT)
        # test for correct symmetry of our tensors:
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(D0[i,j], D0[j,i], msg="{}\nnot symmetric".format(D0))
                for k in range(3):
                    for l in range(3):
                        self.assertAlmostEqual(Dp[i,j,k,l], Dp[j,i,k,l],
                                               msg="{}{}{}{} != {}{}{}{}\n{}\nnot symmetric".format(i,j,k,l, j,i,k,l, Dp))
                        self.assertAlmostEqual(Dp[i,j,k,l], Dp[i,j,l,k],
                                               msg="{}{}{}{} != {}{}{}{}\n{}\nnot symmetric".format(i,j,k,l, i,j,l,k, Dp))
                        self.assertAlmostEqual(Dp[i,j,k,l], Dp[j,i,l,k],
                                               msg="{}{}{}{} != {}{}{}{}\n{}\nnot symmetric".format(i,j,k,l, j,i,l,k, Dp))
        # use Voigtstrain to run through the 6 strains; np.eye(6) generates 6 unit vectors
        for straintype in [ crystal.Voigtstrain(*s) for s in np.eye(6) ]:
            # now doing +- finite difference for a more accurate comparison:
            strainmat = eps*straintype
            strainedHCPpos = self.HCP_intercrys.strain(strainmat)
            strainedHCPpos_jumpnetwork = strainedHCPpos.jumpnetwork(1, self.a0*0.7)
            strainedHCPpos_sitelist = strainedHCPpos.sitelist(1)
            strainedDhcppos = OnsagerCalc.Interstitial(strainedHCPpos, 1,
                                                       strainedHCPpos_sitelist,
                                                       strainedHCPpos_jumpnetwork)
            self.assertTrue(strainedDhcppos.omega_invertible)

            strainedpospre = np.zeros(len(strainedHCPpos_sitelist))
            strainedposBE = np.zeros(len(strainedHCPpos_sitelist))
            # apply dipoles to site energies:
            for octind in range(2):
                strainedpospre[strainedDhcppos.invmap[octind]] = preoct
                strainedposBE[strainedDhcppos.invmap[octind]] = BEoct - np.sum(sitedipoles[octind] * strainmat)
            for tetind in range(2,6):
                strainedpospre[strainedDhcppos.invmap[tetind]] = pretet
                strainedposBE[strainedDhcppos.invmap[tetind]] = BEtet - np.sum(sitedipoles[tetind] * strainmat)
            strainedposBET = np.zeros(len(strainedHCPpos_jumpnetwork))
            strainedpospreT = np.zeros(len(strainedHCPpos_jumpnetwork))
            # this gets more complicated...
            for ind, jumps in enumerate(strainedHCPpos_jumpnetwork):
                (i,j), dx = jumps[0]
                dx0 = np.linalg.solve(np.eye(3) + strainmat, dx)
                dip = transPperp*np.eye(3) +(transPpara-transPperp)*np.outer(dx0, dx0)/np.dot(dx0, dx0)
                if i>=2 and j>=2:
                    strainedpospreT[ind] = preTransTT
                    strainedposBET[ind] = BETransTT - np.sum(dip*strainmat)
                else:
                    strainedpospreT[ind] = preTransOT
                    strainedposBET[ind] = BETransOT - np.sum(dip*strainmat)

            strainedHCPneg = self.HCP_intercrys.strain(-strainmat)
            strainedHCPneg_jumpnetwork = strainedHCPneg.jumpnetwork(1, self.a0*0.7)
            strainedHCPneg_sitelist = strainedHCPneg.sitelist(1)
            strainedDhcpneg = OnsagerCalc.Interstitial(strainedHCPneg, 1,
                                                       strainedHCPneg_sitelist,
                                                       strainedHCPneg_jumpnetwork)
            self.assertTrue(strainedDhcpneg.omega_invertible)

            strainednegpre = np.zeros(len(strainedHCPneg_sitelist))
            strainednegBE = np.zeros(len(strainedHCPneg_sitelist))
            # apply dipoles to site energies:
            for octind in range(2):
                strainednegpre[strainedDhcpneg.invmap[octind]] = preoct
                strainednegBE[strainedDhcpneg.invmap[octind]] = BEoct + np.sum(sitedipoles[octind] * strainmat)
            for tetind in range(2,6):
                strainednegpre[strainedDhcpneg.invmap[tetind]] = pretet
                strainednegBE[strainedDhcpneg.invmap[tetind]] = BEtet + np.sum(sitedipoles[tetind] * strainmat)
            strainednegBET = np.zeros(len(strainedHCPneg_jumpnetwork))
            strainednegpreT = np.zeros(len(strainedHCPneg_jumpnetwork))
            # this gets more complicated...
            for ind, jumps in enumerate(strainedHCPneg_jumpnetwork):
                (i,j), dx = jumps[0]
                dx0 = np.linalg.solve(np.eye(3) - strainmat, dx)
                dip = transPperp*np.eye(3) +(transPpara-transPperp)*np.outer(dx0, dx0)/np.dot(dx0, dx0)
                if i>=2 and j>=2:
                    strainednegpreT[ind] = preTransTT
                    strainednegBET[ind] = BETransTT + np.sum(dip*strainmat)
                else:
                    strainednegpreT[ind] = preTransOT
                    strainednegBET[ind] = BETransOT + np.sum(dip*strainmat)
            Deps = strainedDhcppos.diffusivity(strainedpospre, strainedposBE, strainedpospreT, strainedposBET) -\
                   strainedDhcpneg.diffusivity(strainednegpre, strainednegBE, strainednegpreT, strainednegBET)
            Deps /= 2.*eps
            Deps0 = np.tensordot(Dp, strainmat, axes=((2,3), (0,1)))/eps
            failmsg = """
strainmatrix:
{}
D0:
{}
finite difference:
{}
elastodiffusion:
{}""".format(strainmat, D0, Deps, Deps0)
            self.assertTrue(np.allclose(Deps, Deps0, rtol=2*eps, atol=2*eps), msg=failmsg)
