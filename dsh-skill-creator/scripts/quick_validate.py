#!/usr/bin/env python3
# Modified for DeepSeek Harness. Upstream: Anthropic's skill-creator (Apache-2.0, see LICENSE.txt).
"""
Quick validation script for skills - minimal version
"""

import sys
import os
import re
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import safe_console

def _parse_scalar(value):
    """Convert a raw frontmatter scalar to a Python value."""
    if value == '':
        return None
    if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'"):
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace('\\\\', '\\')
        return inner.replace("''", "'")
    lowered = value.lower()
    if lowered in ('true', 'yes', 'on'):
        return True
    if lowered in ('false', 'no', 'off'):
        return False
    if lowered in ('null', '~'):
        return None
    return value


def _parse_frontmatter(text):
    """Parse the frontmatter subset skills use: scalars, quoted strings, and block values."""
    data = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line[0] in (' ', '\t'):
            raise ValueError(f"Unexpected indentation on line {i}")
        key, sep, rest = line.partition(':')
        key = key.strip()
        rest = rest.strip()
        if not sep or not key:
            raise ValueError(f"Invalid frontmatter line {i}: {line.strip()}")
        if rest in ('|', '>', '|-', '>-', '|+', '>+'):
            block = []
            while i < len(lines) and (not lines[i].strip() or lines[i][0] in (' ', '\t')):
                block.append(lines[i])
                i += 1
            while block and not block[-1].strip():
                block.pop()
            indents = [len(b) - len(b.lstrip()) for b in block if b.strip()]
            indent = min(indents) if indents else 0
            parts = [b[indent:] if b.strip() else '' for b in block]
            data[key] = ' '.join(p for p in parts if p) if rest[0] == '>' else '\n'.join(parts)
        elif rest == '' and i < len(lines) and lines[i][:1] in (' ', '\t'):
            nested = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in (' ', '\t')):
                nested.append(lines[i])
                i += 1
            indents = [len(n) - len(n.lstrip()) for n in nested if n.strip()]
            indent = min(indents) if indents else 0
            data[key] = _parse_frontmatter('\n'.join(n[indent:] for n in nested))
        else:
            data[key] = _parse_scalar(rest)
    return data


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith('---'):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Parse YAML frontmatter
    try:
        frontmatter = _parse_frontmatter(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except ValueError as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    # Define allowed properties
    ALLOWED_PROPERTIES = {'name', 'description', 'whenToUse', 'metadata', 'disable-model-invocation', 'user-invocable'}

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}. "
            f"DSH only reads name, description, whenToUse, metadata, disable-model-invocation and user-invocable; record anything else under metadata."
        )

    # Check required fields
    if 'name' not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if 'description' not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        # Check naming convention (kebab-case: lowercase with hyphens)
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."

    # Extract and validate description
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        # Check for angle brackets
        if '<' in description or '>' in description:
            return False, "Description cannot contain angle brackets (< or >)"
        # Check description length (max 1024 characters per spec)
        if len(description) > 1024:
            return False, f"Description is too long ({len(description)} characters). Maximum is 1024 characters."

    # Validate boolean flags if present (optional)
    accepted_booleans = ('true', 'false', 'yes', 'no', 'on', 'off', '1', '0')
    for flag in ('disable-model-invocation', 'user-invocable'):
        if flag in frontmatter:
            value = frontmatter[flag]
            if not (isinstance(value, bool)
                    or (isinstance(value, int) and value in (0, 1))
                    or (isinstance(value, str) and value.strip().lower() in accepted_booleans)):
                return False, (
                    f"'{flag}' must be a boolean (true/false, yes/no, on/off, 1/0), got {value!a}. "
                    f"DSH drops the entire skill when this value is invalid."
                )

    return True, "Skill is valid!"

if __name__ == "__main__":
    safe_console()
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.quick_validate <skill_directory>")
        sys.exit(1)
    
    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)