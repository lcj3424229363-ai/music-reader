'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const APP_JS = path.join(__dirname, '..', 'web', 'app.js');

function declarationEnd(source, start, terminator) {
  let quote = '';
  let escaped = false;
  let lineComment = false;
  let blockComment = false;
  let regex = false;
  let regexClass = false;
  const depth = { '(': 0, '[': 0, '{': 0 };

  for (let i = start; i < source.length; i += 1) {
    const char = source[i];
    const next = source[i + 1];
    if (lineComment) {
      if (char === '\n') lineComment = false;
      continue;
    }
    if (blockComment) {
      if (char === '*' && next === '/') {
        blockComment = false;
        i += 1;
      }
      continue;
    }
    if (quote) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === quote) quote = '';
      continue;
    }
    if (regex) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '[') regexClass = true;
      else if (char === ']') regexClass = false;
      else if (char === '/' && !regexClass) regex = false;
      continue;
    }
    if (char === '/' && next === '/') {
      lineComment = true;
      i += 1;
      continue;
    }
    if (char === '/' && next === '*') {
      blockComment = true;
      i += 1;
      continue;
    }
    if (char === '/') {
      let previous = '';
      for (let j = i - 1; j >= start && !previous; j -= 1) {
        if (!/\s/.test(source[j])) previous = source[j];
      }
      if (!previous || '=(:,![{;?|&'.includes(previous)) {
        regex = true;
        regexClass = false;
        escaped = false;
        continue;
      }
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
      continue;
    }
    if (char === '(' || char === '[' || char === '{') depth[char] += 1;
    if (char === ')') depth['('] -= 1;
    if (char === ']') depth['['] -= 1;
    if (char === '}') depth['{'] -= 1;
    if (terminator === '}' && char === '}' && depth['{'] === 0) return i + 1;
    if (terminator === ';' && char === ';' && Object.values(depth).every((value) => value === 0)) return i + 1;
  }
  throw new Error(`Unterminated declaration at offset ${start}`);
}

function extractFunction(source, name) {
  const match = new RegExp(`function\\s+${name}\\s*\\(`).exec(source);
  if (!match) throw new Error(`Function not found: ${name}`);
  const brace = source.indexOf('{', match.index);
  return source.slice(match.index, declarationEnd(source, brace, '}'));
}

function extractConst(source, name) {
  const match = new RegExp(`const\\s+${name}\\s*=`).exec(source);
  if (!match) throw new Error(`Constant not found: ${name}`);
  return source.slice(match.index, declarationEnd(source, match.index, ';'));
}

function loadMusicXmlFunctions() {
  const source = fs.readFileSync(APP_JS, 'utf8');
  const constants = [
    'stepIndex', 'durationUnits', 'musicXmlTypes', 'MUSICXML_DIVISIONS', 'DIVISIONS_PER_UNIT', 'tupletRatios',
    'articulationXml', 'ornamentXml', 'keyFifths', 'typeToDuration',
    'xmlToArticulation', 'xmlToOrnament', 'xmlToDynamics', 'xmlToBarline',
    'xmlRepeatToBarline', 'fifthsToKey', 'fifthsToMinorKey'
  ];
  const functions = [
    'meterForTimeSignature', 'dotCount', 'normalizeUnitValue', 'displayAccidental',
    'buildMusicXml', 'musicXmlAttributes', 'musicXmlEntry', 'musicXmlSingleNote',
    'musicXmlNotations', 'musicXmlBarlines', 'parseChordSymbol', 'chordKind',
    'musicXmlHarmony', 'musicXmlVoiceNumber', 'parseMusicXmlText',
    'parseMusicXmlMeasure', 'parseMusicXmlDirection', 'parseMusicXmlHarmony',
    'parseMusicXmlNote', 'noteToEntry', 'keyFromFifths', 'xmlEscape', 'xmlUnescape',
    'isMusicReaderCanonicalXml', 'unitsForDuration', 'unitsForEntry', 'sumEntryUnits',
    'entryVoice', 'sortPitches', 'normalizeEntryForExport', 'exportVoiceEntries',
    'normalizeKeyForSelect', 'normalizeAnswerEntryForEditor',
    'buildAnswerScoreDocument', 'buildAnswerMusicXml'
  ];
  const declarations = [
    ...constants.map((name) => extractConst(source, name)),
    ...functions.map((name) => extractFunction(source, name))
  ];
  declarations.forEach((declaration, index) => {
    try {
      new vm.Script(declaration);
    } catch (error) {
      const name = index < constants.length ? constants[index] : functions[index - constants.length];
      throw new Error(`Invalid extracted declaration ${name}: ${error.message}`);
    }
  });
  const sandbox = {
    editorTime: { value: '4/4' },
    editorKey: { value: 'C' },
    scoreDocumentTitle: 'Test score',
    lastFourPartResult: null
  };
  vm.createContext(sandbox);
  vm.runInContext(
    `${declarations.join('\n\n')}\nthis.__exports = { ${functions.join(', ')} };`,
    sandbox,
    { filename: APP_JS }
  );
  return sandbox.__exports;
}

module.exports = { loadMusicXmlFunctions };
