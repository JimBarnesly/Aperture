"""Source-level guardrails only, not PowerShell or hardware execution tests."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'installer'
SCRIPT = (ROOT / 'Prepare-Aperture.ps1').read_text()


class InstallerContractTests(unittest.TestCase):
    def test_no_destructive_or_policy_bypass_commands(self):
        for forbidden in ('Clear-Disk', 'Initialize-Disk', 'Format-Volume',
                          'Remove-Partition', 'Set-ExecutionPolicy', 'diskpart',
                          'PhysicalDrive', 'Invoke-WebRequest', 'Invoke-Expression',
                          '-Verb RunAs', 'DownloadFile'):
            self.assertNotIn(forbidden.lower(), SCRIPT.lower())

    def test_no_embedded_secrets_or_unattended_boot_hook(self):
        self.assertNotRegex(SCRIPT, r'(?i)(password|api_key|autostart\.sh)\s*=')
        self.assertNotIn('addons.unknownsources', SCRIPT)

    def test_manifest_is_allowlisted_and_verified(self):
        for token in ('plugin.games.apeture', 'script.apeture.music', 'skin.apeture',
                      '$entries.Count -ne 3', '$entry.file -cne', '$item.Length -ne $entry.bytes',
                      'Get-FileHash', 'ReparsePoint'):
            self.assertIn(token, SCRIPT)
        self.assertLess(SCRIPT.index('Checksum/size mismatch'), SCRIPT.index('Copy-VerifiedFile $file'))

    def test_media_is_explicit_and_revalidated(self):
        for token in ('$disk.IsBoot', '$disk.IsSystem', '$disk.IsOffline', '$disk.IsReadOnly',
                      "@('USB', 'SD', 'MMC')", '$partitions.Count -ne 1', '$disks.Count -ne 1',
                      'Read-Host', '$answer -cne', '$again.UniqueId -cne $identity',
                      '$again.Number -ne $diskNumber', '$again.Size -ne $diskSize'):
            self.assertIn(token, SCRIPT)
        self.assertEqual(SCRIPT.count('Get-SafeUsbDisk $UsbDriveLetter'), 2)

    def test_copy_never_overwrites(self):
        self.assertIn('[IO.File]::Copy($Source, $Destination, $false)', SCRIPT)
        self.assertIn('Refusing to overwrite different file', SCRIPT)

    def test_local_output_cannot_bypass_media_checks(self):
        self.assertIn("$root -ine ($env:SystemDrive + '\\')", SCRIPT)
        self.assertIn('if (-not $UsbDriveLetter) { Assert-LocalOutput $OutputPath }', SCRIPT)
        self.assertIn('positively identified internal disk', SCRIPT)

    def test_all_conflicts_preflight_and_instructions_travel(self):
        self.assertIn("Name = 'INSTALL-WINDOWS.md'", SCRIPT)
        self.assertIn('Get-ChildItem -LiteralPath $Directory -Force', SCRIPT)
        self.assertLess(SCRIPT.index('Assert-DestinationFiles $OutputPath $sources'),
                        SCRIPT.index('Copy-VerifiedFile $file'))

    def test_only_official_browser_urls(self):
        self.assertEqual(set(re.findall(r'https://[^\s\']+', SCRIPT)), {
            'https://libreelec.tv/downloads/raspberry/',
            'https://www.raspberrypi.com/software/'})

    def test_documented_limits(self):
        readme = (ROOT / 'README.md').read_text()
        for phrase in ('have not been tested here', 'no unattended first-boot',
                       'all partitions', 'Do not bypass', 'Unknown sources'):
            self.assertIn(phrase, readme)


if __name__ == '__main__':
    unittest.main()
