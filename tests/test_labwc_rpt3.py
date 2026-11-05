"""The downstream comparison must never silently fall back to another runtime."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('labwc_rpt3_verify', ROOT / 'tools/labwc_rpt3_verify.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DownstreamRuntimeTests(unittest.TestCase):
    def packages(self):
        return '\n'.join(['kodi\t3:21.3+dfsg-1+rpt3\tarm64', 'kodi-bin\t3:21.3+dfsg-1+rpt3\tarm64',
            'kodi-data\t3:21.3+dfsg-1+rpt3\tall', 'labwc\t0.8.3-1\tarm64',
            'libegl-mesa0\t25.0.7-2+deb13u1\tarm64', 'libgl1-mesa-dri\t25.0.7-2+deb13u1\tarm64'])

    def test_exact_downstream_arm64_packages(self):
        self.assertEqual(module.package_evidence(self.packages())['kodi-bin'], ['3:21.3+dfsg-1+rpt3', 'arm64'])

    def test_debian_kodi_or_wrong_arch_rejected(self):
        for changed in (self.packages().replace('3:21.3+dfsg-1+rpt3', '2:21.3+dfsg-2'), self.packages().replace('arm64', 'amd64')):
            with self.assertRaises(ValueError):
                module.package_evidence(changed)

    def test_graphics_version_substitution_rejected(self):
        with self.assertRaises(ValueError):
            module.package_evidence(self.packages().replace('25.0.7-2+deb13u1', '26.1.6-1'))

    def test_actual_gles_llvmpipe_native_wayland(self):
        log = 'EGL_VERSION = 1.5\nGL_RENDERER = llvmpipe (LLVM 19)\nGL_VERSION = OpenGL ES 3.2 Mesa 25.0.7\nBinding Wayland protocol wl_shm version 1\n'
        self.assertTrue(module.gles_evidence(log)['native_wayland'])
        for changed in (log.replace('OpenGL ES 3.2', '4.6 (Core Profile)'), log.replace('llvmpipe', 'V3D'), log.replace('Binding Wayland protocol', 'X11')):
            with self.assertRaises(ValueError):
                module.gles_evidence(changed)

    def test_original_lifecycle_harness_is_reused(self):
        wrapper = (ROOT / 'tools/ci_labwc_rpt3.sh').read_text()
        self.assertIn('bash "$ROOT/tools/ci_labwc_relaunch.sh"', wrapper)
        self.assertIn('labwc_rpt3_verify.py', wrapper)

    def test_signed_repository_and_pinned_versions_required(self):
        installer = (ROOT / 'tools/install_labwc_rpt3_ci.sh').read_text()
        for token in ('signed-by=', 'CF8A1AF502A2AA2D763BAE7E82B129927FA3303E', 'APT::Update::Error-Mode=any', '3:21.3+dfsg-1+rpt3', '8:7.1.5-0+deb13u1+rpt2', 'raspberrypi-archive-keyring_2025.1+rpt1_all.deb', 'sha256sum --check'):
            self.assertIn(token, installer)
        for forbidden in ('trusted=yes', 'allow-unauthenticated', 'AllowInsecureRepositories', 'allow-insecure-repositories'):
            self.assertNotIn(forbidden, installer)


if __name__ == '__main__':
    unittest.main()
