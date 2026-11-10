"""Validate only the JSON Schema vocabulary used by this skill's bundled schemas.

This is NOT a general JSON Schema implementation. Supported assertions are type,
const, enum, required, properties, additionalProperties, items, min/maxItems,
uniqueItems, minLength, pattern, allOf, anyOf, oneOf, and if/then/else. $ref resolves
only local schema files and JSON pointers; unsupported keywords fail explicitly.
Use a standards-compliant Draft 2020-12 validator for arbitrary external schemas.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


class SchemaError(ValueError):
    pass


SUPPORTED = {
    '$schema', '$id', '$defs', '$ref', '$comment', 'title', 'description',
    'type', 'const', 'enum', 'required', 'properties', 'additionalProperties',
    'items', 'minItems', 'maxItems', 'uniqueItems', 'minLength', 'pattern',
    'allOf', 'anyOf', 'oneOf', 'if', 'then', 'else',
}


def _equal(left: Any, right: Any) -> bool:
    # JSON booleans are not numeric values, unlike Python's bool subclass.
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


class SchemaChecker:
    def __init__(self, schema_dir: Path):
        self.schema_dir = schema_dir.resolve()
        self._cache: dict[Path, Any] = {}

    def _load(self, path: Path) -> Any:
        path = path.resolve()
        if not path.is_relative_to(self.schema_dir):
            raise SchemaError('Schema references must stay inside the bundled schema directory')
        if path not in self._cache:
            self._cache[path] = json.loads(path.read_text(encoding='utf-8'))
        return self._cache[path]

    def _reference(self, reference: str, current: Path) -> tuple[Any, Path]:
        if '://' in reference:
            raise SchemaError('Remote schema references are unsupported')
        filename, _, fragment = reference.partition('#')
        path = (current.parent / filename).resolve() if filename else current
        schema = self._load(path)
        if fragment:
            if not fragment.startswith('/'):
                raise SchemaError('Only JSON Pointer fragments are supported')
            try:
                for part in fragment[1:].split('/'):
                    schema = schema[part.replace('~1', '/').replace('~0', '~')]
            except (KeyError, TypeError) as exc:
                raise SchemaError(f'Unresolved schema reference: {reference}') from exc
        return schema, path

    def validate(self, value: Any, filename: str) -> list[str]:
        path = (self.schema_dir / filename).resolve()
        return self._check(value, self._load(path), path, '$')

    def _check(self, value: Any, schema: Any, path: Path, location: str) -> list[str]:
        if schema is True:
            return []
        if schema is False:
            return [f'{location}: value is forbidden']
        unknown = set(schema) - SUPPORTED
        if unknown:
            raise SchemaError(f'Unsupported schema keywords: {", ".join(sorted(unknown))}')
        errors: list[str] = []
        if '$ref' in schema:
            target, target_path = self._reference(schema['$ref'], path)
            errors += self._check(value, target, target_path, location)
        expected = schema.get('type')
        types = {
            'object': isinstance(value, dict),
            'array': isinstance(value, list),
            'string': isinstance(value, str),
            'boolean': isinstance(value, bool),
            'null': value is None,
            'number': isinstance(value, (int, float)) and not isinstance(value, bool),
            'integer': isinstance(value, (int, float)) and not isinstance(value, bool) and (not isinstance(value, float) or math.isfinite(value)) and int(value) == value,
        }
        if expected and not any(types.get(t, False) for t in ([expected] if isinstance(expected, str) else expected)):
            return errors + [f'{location}: expected {expected}']
        if 'const' in schema and not _equal(value, schema['const']):
            errors.append(f'{location}: expected constant {schema["const"]!r}')
        if 'enum' in schema and not any(_equal(value, item) for item in schema['enum']):
            errors.append(f'{location}: value is not in {schema["enum"]!r}')
        if isinstance(value, dict):
            for key in schema.get('required', []):
                if key not in value:
                    errors.append(f'{location}: missing required field {key}')
            properties = schema.get('properties', {})
            for key, item in value.items():
                if key in properties:
                    errors += self._check(item, properties[key], path, f'{location}.{key}')
                elif schema.get('additionalProperties') is False:
                    errors.append(f'{location}: unknown field {key}')
                elif isinstance(schema.get('additionalProperties'), dict):
                    errors += self._check(item, schema['additionalProperties'], path, f'{location}.{key}')
        if isinstance(value, list):
            if len(value) < schema.get('minItems', 0):
                errors.append(f'{location}: requires at least {schema["minItems"]} items')
            if 'maxItems' in schema and len(value) > schema['maxItems']:
                errors.append(f'{location}: allows at most {schema["maxItems"]} items')
            if schema.get('uniqueItems') and any(_equal(value[i], value[j]) for i in range(len(value)) for j in range(i)):
                errors.append(f'{location}: duplicate array items')
            if 'items' in schema:
                for i, item in enumerate(value):
                    errors += self._check(item, schema['items'], path, f'{location}[{i}]')
        if isinstance(value, str):
            if len(value) < schema.get('minLength', 0):
                errors.append(f'{location}: string is too short')
            if 'pattern' in schema and re.search(schema['pattern'], value) is None:
                errors.append(f'{location}: does not match {schema["pattern"]!r}')
        for branch in schema.get('allOf', []):
            errors += self._check(value, branch, path, location)
        for combinator in ('anyOf', 'oneOf'):
            if combinator in schema:
                count = sum(not self._check(value, branch, path, location) for branch in schema[combinator])
                if (combinator == 'anyOf' and count == 0) or (combinator == 'oneOf' and count != 1):
                    errors.append(f'{location}: failed {combinator}')
        if 'if' in schema:
            branch = 'then' if not self._check(value, schema['if'], path, location) else 'else'
            if branch in schema:
                errors += self._check(value, schema[branch], path, location)
        return errors
