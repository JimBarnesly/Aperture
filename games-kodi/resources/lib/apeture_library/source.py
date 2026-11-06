"""Conservative Linux local-source identity; no VFS availability guesses.

Mount IDs detect detach/re-attach during a scan. Persistent identity includes
all mounts below the ROM root, so losing only a nested game volume also fails
closed. Unsupported platforms/providers return no proof, never 'available'.
"""
import hashlib
import json
import os
import re


def _unescape(value):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def inspect_source(root):
    if not root or "://" in str(root) or not os.path.isabs(root):
        return None
    try:
        path = os.path.realpath(root)
        stat = os.stat(root)
        if not os.path.isdir(root):
            return None
        with open("/proc/self/mountinfo", encoding="utf-8") as stream:
            entries = []
            for line in stream:
                fields = line.split()
                separator = fields.index("-")
                mount = _unescape(fields[4])
                if path == mount or path.startswith(mount.rstrip("/") + "/") or mount.startswith(path.rstrip("/") + "/"):
                    entries.append((mount, fields, separator))
        ancestors = [entry for entry in entries if path == entry[0] or path.startswith(entry[0].rstrip("/") + "/")]
        if not ancestors:
            return None
        anchor = max(ancestors, key=lambda entry: len(entry[0]))
        selected = [anchor] + [entry for entry in entries if entry[0].startswith(path.rstrip("/") + "/")]
        device = "{}:{}".format(os.major(stat.st_dev), os.minor(stat.st_dev))
        if anchor[1][2] != device:
            return None
        # A locally mounted SMB/NFS/FUSE provider can report an empty list
        # while keeping its mount alive. Its mount identity is not availability.
        local_types = {"ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "vfat", "exfat", "ntfs3", "tmpfs", "ramfs"}
        if any(fields[separator + 1] not in local_types for _, fields, separator in selected):
            return None
        stable, sessions = [], []
        for mount, fields, separator in sorted(selected):
            stable.append((mount, fields[2], fields[3], fields[separator + 1], fields[separator + 2]))
            sessions.append(fields[0])
        final = os.stat(root)
        if (stat.st_dev, stat.st_ino) != (final.st_dev, final.st_ino):
            return None
        def digest(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()
        return {"identity": digest((path, stat.st_dev, stat.st_ino, stable)),
                "session": digest(sessions)}
    except (OSError, ValueError, IndexError, AttributeError):
        return None
