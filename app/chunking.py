import re
from dataclasses import dataclass

SLUG = re.compile(r'^[a-z0-9_-]{2,40}$')
SECTION = re.compile(r'^##[ ]+([0-9]+)[.][ ]+(.+?)[ ]*$')
VERSION = re.compile(r'^version:[ ]*([0-9]+)[ ]*$')


class PolicyFormatError(ValueError):
    '''The policy file is malformed. Nothing has been stored.'''


@dataclass(frozen=True)
class Chunk:
    company: str
    version: int
    doc_title: str
    section_no: str
    section_title: str
    text: str

    @property
    def chunk_id(self):
        return f'{self.company}-v{self.version}-s{self.section_no}'

    @property
    def embed_text(self):
        # the title helps retrieval: 'escort' appears in the title and the body
        return f'{self.section_title}. {self.text}'


def parse_policy(company, raw):
    if not SLUG.match(company):
        raise PolicyFormatError('company id must be lowercase letters, digits, - or _')
    title, version = None, None
    sections = []  # each item: [number, title, [body lines]]
    for line in raw.splitlines():
        line = line.rstrip()
        m = SECTION.match(line)
        if m:
            sections.append([m.group(1), m.group(2), []])
        elif line.startswith('# ') and title is None:
            title = line[2:].strip()
        elif VERSION.match(line) and version is None:
            version = int(VERSION.match(line).group(1))
        elif sections and line.strip():
            sections[-1][2].append(line.strip())
    if not title:
        raise PolicyFormatError('missing title line (# Title)')
    if version is None:
        raise PolicyFormatError('missing version line (version: N)')
    if not sections:
        raise PolicyFormatError('no sections found (## 1. Title)')
    seen, chunks = set(), []
    for no, sec_title, body in sections:
        if no in seen:
            raise PolicyFormatError(f'duplicate section {no}')
        seen.add(no)
        text = ' '.join(body)
        if not text:
            raise PolicyFormatError(f'section {no} is empty')
        chunks.append(Chunk(company, version, title, no, sec_title, text))
    return chunks