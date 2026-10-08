"""Check launch-document links and tracked media without system writes/network."""
from pathlib import Path
import re
from urllib.parse import unquote
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    'README.md', 'README.en.md', 'CONTRIBUTING.md', 'SECURITY.md', 'SUPPORT.md', 'PRIVACY.md',
    'docs/README.md', 'docs/getting-started.md', 'docs/commercial-readiness.md',
    'docs/launch-kit.md', 'docs/media/README.md', 'docs/releases/main-publication.md',
)


def check(root=ROOT):
    failures = []
    links = 0
    for name in DOCUMENTS:
        path = root/name
        if not path.is_file():
            failures.append(f'Missing document: {name}')
            continue
        text = path.read_text(encoding='utf8')
        public_text = re.sub(r'```.*?```', '', text, flags=re.S)
        if re.search(r'[A-Za-z]:[\\/][^\n]*[\\/]Desktop[\\/]', public_text):
            failures.append(f'Private desktop path in public copy: {name}')
        for match in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)', public_text):
            target = match.group(1).strip('<>')
            if target.startswith(('https://', 'http://', '#', 'mailto:')):
                continue
            target = unquote(target.split('#')[0])
            resolved = (path.parent/target).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                failures.append(f'Broken/escaping local link in {name}: {target}')
            links += 1
    for name, size in (('cover.png', (1920, 1080)), ('cover-portrait.png', (1080, 1920)),
                       ('app-appearance.png', (1180, 800)), ('app-motion.png', (1180, 800)),
                       ('app-tests.png', (1180, 800)), ('app-settings.png', (1180, 800))):
        with Image.open(root/'docs/media'/name) as image:
            if image.size != size:
                failures.append(f'Unexpected size: {name}: {image.size}')
            image.verify()
    with Image.open(root/'docs/media/click-motion.gif') as image:
        if image.n_frames != 30 or image.info.get('loop') != 0:
            failures.append('GIF must have 30 frames and loop indefinitely')
    subtitles = (root/'docs/media/pointer-demo.zh-en.srt').read_text(encoding='utf8')
    if subtitles.count(' --> ') != 6 or '00:00:50,000' not in subtitles:
        failures.append('Subtitle schedule does not match the 50-second film')
    if failures:
        raise RuntimeError('\n'.join(failures))
    print(f'Publication checks passed: {len(DOCUMENTS)} documents, {links} local links, 7 media files, subtitles.')


if __name__ == '__main__':
    check()
