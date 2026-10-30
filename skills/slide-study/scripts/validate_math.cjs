#!/usr/bin/env node
// Check mathematical syntax with the exact bundled renderer used by the webpage.
const fs = require('node:fs');
const path = require('node:path');
const katex = require(path.join(__dirname, '..', 'assets', 'vendor', 'katex', 'katex.min.js'));

function validateMath(lesson) {
  const errors = [];
  let formulas = 0;
  function visit(value, location) {
    if (typeof value === 'string') {
      const text = value.replace(/```[^\n]*\n[\s\S]*?```/g, '').replace(/`[^`\n]*`/g, '');
      const regex = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|(?<!\\)\$([^$]+?)\$/g;
      for (const match of text.matchAll(regex)) {
        formulas += 1;
        try {
          katex.renderToString(match[1] ?? match[2] ?? match[3] ?? match[4], { throwOnError: true, trust: false, strict: 'ignore' });
        } catch (error) {
          errors.push({ location, formula: match[0], error: error.message });
        }
      }
    } else if (Array.isArray(value)) value.forEach((item, i) => visit(item, `${location}[${i}]`));
    else if (value && typeof value === 'object') Object.entries(value).forEach(([key, item]) => visit(item, `${location}.${key}`));
  }
  visit(lesson, 'lesson');
  return { valid: errors.length === 0, formulas, errors };
}

if (require.main === module) {
  try {
    if (process.argv.length !== 3) throw new Error('Usage: node validate_math.cjs LESSON_JSON');
    const result = validateMath(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')));
    console.log(JSON.stringify(result, null, 2));
    process.exitCode = result.valid ? 0 : 1;
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
module.exports = { validateMath };
