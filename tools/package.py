#!/usr/bin/env python3
"""Create a source-only archive using the same checked public file list."""
import zipfile
from check_release import ROOT, check


if __name__ == '__main__':
    files = check()
    output = ROOT / '.build/ffalcon-tv-control-source.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'ffalcon-tv-control/' + str(path.relative_to(ROOT)))
    print(output)
