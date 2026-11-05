"""Package and scope guards for the separately selected Pi userspace comparison."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import labwc_pi_userspace_verify as verify


class PiUserspaceTests(unittest.TestCase):
    def packages(self):
        return '\n'.join(f'{name}\t{version}\t' + ('all' if name in ('kodi-data', 'libdrm-common') else 'arm64')
                         for name, version in verify.EXPECTED.items())

    def test_exact_pi_runtime_and_ffmpeg_pins(self):
        evidence = verify.package_evidence(self.packages())
        self.assertEqual(evidence['labwc'][0], '0.20.2-1~bpo13+1')
        self.assertEqual(evidence['libwlroots-0.20'][0], '0.20.2-1+rpt4')
        self.assertEqual(evidence['libavcodec61'][0], '8:7.1.5-0+deb13u1+rpt2')

    def test_old_runtime_or_wrong_architecture_is_rejected(self):
        for original, replacement in [('0.20.2-1~bpo13+1', '0.8.3-1'),
                                     (verify.MESA_VERSION, '25.0.7-2+deb13u1'), ('arm64', 'amd64')]:
            with self.assertRaises(ValueError):
                verify.package_evidence(self.packages().replace(original, replacement))

    def test_userspace_only_plan_accepted(self):
        self.assertEqual(verify.validate_plan('Inst labwc (0.20.2)\nInst libsfdo0 (0.1.3)\nInst mesa-libgallium (26.2.2)'),
                         ['labwc', 'libsfdo0', 'mesa-libgallium'])

    def test_kernel_firmware_and_device_services_rejected(self):
        for package in ('linux-image-rpi-2712', 'raspberrypi-kernel', 'raspberrypi-bootloader', 'raspi-firmware',
                        'firmware-brcm80211', 'udev', 'systemd', 'seatd', 'pipewire', 'raspi-config'):
            with self.assertRaises(ValueError):
                verify.validate_plan(f'Inst labwc (0.20.2)\nInst {package} (1)')

    def test_removals_and_empty_simulation_rejected(self):
        for plan in ('Remv libfoo [1]\nInst labwc (0.20.2)', 'Purg linux-image (1)', '', 'Inst libsfdo0 (0.1.3)'):
            with self.assertRaises(ValueError):
                verify.validate_plan(plan)

    def test_installer_simulates_and_checks_before_install(self):
        source = (Path(verify.__file__).parent / 'install_labwc_pi_userspace_ci.sh').read_text()
        self.assertLess(source.index('apt-get --simulate'), source.index('validate_plan('))
        self.assertLess(source.index('validate_plan('), source.index('apt-get --yes --no-remove'))
        self.assertIn('exact-2026-11-05', source)
        self.assertIn('install_labwc_rpt3_ci.sh', source)
        self.assertNotIn('allow-unauthenticated', source)
        self.assertNotIn('dist-upgrade', source)

    def test_wrapper_uses_identical_churn_driver(self):
        root = Path(verify.__file__).parents[1]
        source = (root / 'tools/ci_labwc_pi_userspace.sh').read_text()
        self.assertIn('ci_labwc_relaunch.sh', source)
        self.assertIn('output-size-churn', source)
        workflow = (root / '.github/workflows/labwc-pi-userspace-churn.yml').read_text()
        self.assertIn('branches: [test/labwc-output-size-churn]', workflow)
        self.assertIn('APERTURE_PI_USERSPACE_COMPARISON: exact-2026-11-05', workflow)


if __name__ == '__main__':
    unittest.main()
