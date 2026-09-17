'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { loadMusicXmlFunctions } = require('./musicxml_harness');
const { fixture, note, voice } = require('./musicxml_fixture');

const {
  buildMusicXml,
  parseMusicXmlText,
  isMusicReaderCanonicalXml,
  buildAnswerMusicXml,
  answerIntegrityReport
} = loadMusicXmlFunctions();

test('frontend MusicXML preserves four independent staff/voice timelines', () => {
  const xml = buildMusicXml(fixture());
  assert.equal(isMusicReaderCanonicalXml(xml), true);
  assert.equal(isMusicReaderCanonicalXml('<score-partwise version="4.0"/>'), false);
  const backups = [...xml.matchAll(/<backup>[\s\S]*?<duration>(\d+)<\/duration>[\s\S]*?<\/backup>/g)]
    .map((match) => Number(match[1]));
  assert.deepEqual(backups, [192, 192, 192]);

  const parsed = parseMusicXmlText(xml);
  assert.equal(parsed.title, 'Frontend roundtrip');
  assert.equal(parsed.tempo, 96);
  assert.equal(parsed.anacrusis, true);
  assert.equal(parsed.staffMode, 'piano');
  assert.equal(parsed.measureCount, 1);
  assert.equal(parsed.keySignature, 'Am');
  assert.equal(parsed.timeSignature, '4/4');
  assert.equal(parsed.staves.treble[0].number, '1');
  assert.deepEqual(Array.from(parsed.staves.treble[0].voices, (item) => item.id), ['1', '2']);
  assert.deepEqual(Array.from(parsed.staves.bass[0].voices, (item) => item.id), ['1', '2']);

  const soprano = parsed.staves.treble[0].voices[0].entries;
  assert.equal(soprano[0].pitches[0].accidental, '#');
  assert.equal(soprano[0].pitches.length, 3);
  assert.equal(soprano[1].pitches[0].accidental, 'n');
  assert.equal(soprano[0].dynamic, 'mf');
  assert.equal(soprano[0].textMark, 'dolce & cantabile');
  assert.equal(soprano[0].articulation, 'accent');
  assert.equal(soprano[0].chordSymbol, 'F#maj7/C#');
  assert.equal(soprano[0].fingering, '2');
  assert.equal(soprano[0].grace.accidental, 'n');
  assert.equal(soprano[0].breath, true);
  assert.equal(soprano[0].arpeggiate, true);
  assert.equal(soprano[0].rehearsalMark, 'A1');
  assert.equal(soprano[0].volta, 1);
  assert.equal(soprano[1].ornament, 'trill');
  assert.equal(soprano[2].fermata, true);
  assert.equal(soprano[2].phraseStart, true);
  assert.equal(soprano[2].phraseStop, true);
  assert.equal(parsed.staves.treble[0].voices[1].entries[0].chordSymbol, 'D7/F#');

  const bassVoice = parsed.staves.bass[0].voices[1].entries;
  assert.equal(bassVoice[0].kind, 'rest');
  assert.equal(bassVoice[0].dynamic, 'p');
  assert.equal(bassVoice[0].pedal, 'start');
  assert.equal(bassVoice[0].textMark, 'rest cue');
  assert.equal(bassVoice[0].chordSymbol, 'Fm');
  assert.equal(bassVoice[1].pedal, 'stop');
  assert.equal(bassVoice[1].hairpin, 'cresc-start');
  assert.equal(bassVoice[1].chordSymbol, 'Cm7/G');
});

test('tuplet identity and custom ornaments survive roundtrip', () => {
  const data = fixture();
  data.staves = [data.staves[0]];
  data.staffMode = 'single';
  data.staves[0].measures[0].voices = [voice('1', [
    note('C', 5, { duration: '8', units: 8 / 3, tupletType: 'triplet', tupletGroup: 'triplet-group-1', tupletPosition: 'start', ornament: 'upprall' }),
    note('D', 5, { duration: '8', units: 8 / 3, tupletType: 'triplet', tupletGroup: 'triplet-group-1', tupletPosition: 'middle', ornament: 'downprall' }),
    note('E', 5, { duration: '8', units: 8 / 3, tupletType: 'triplet', tupletGroup: 'triplet-group-1', tupletPosition: 'end', ornament: 'lineprall' })
  ])];
  const parsedEntries = parseMusicXmlText(buildMusicXml(data)).staves.treble[0].voices[0].entries;
  assert.deepEqual(Array.from(parsedEntries, (entry) => entry.tupletPosition), ['start', 'middle', 'end']);
  assert.deepEqual(Array.from(parsedEntries, (entry) => entry.tupletGroup), ['triplet-group-1', 'triplet-group-1', 'triplet-group-1']);
  assert.deepEqual(Array.from(parsedEntries, (entry) => entry.ornament), ['upprall', 'downprall', 'lineprall']);
});

test('empty piano measure rewinds before writing the second staff rest', () => {
  const data = fixture();
  data.staves.forEach((staff) => { staff.measures[0].voices.forEach((item) => { item.entries = []; }); });
  const xml = buildMusicXml(data);
  assert.equal((xml.match(/<rest measure="yes"\/>/g) || []).length, 2);
  assert.match(xml, /<backup>[\s\S]*?<duration>192<\/duration>[\s\S]*?<\/backup>/);
});

test('single bass staff remains a bass staff after roundtrip', () => {
  const data = fixture();
  const bass = data.staves[1];
  bass.staffNumber = 1;
  data.staves = [bass];
  data.staffMode = 'single';

  const parsed = parseMusicXmlText(buildMusicXml(data));
  assert.equal(parsed.staffMode, 'single');
  assert.equal(parsed.staves.treble.length, 0);
  assert.equal(parsed.staves.bass.length, 1);
  assert.deepEqual(Array.from(parsed.staves.bass[0].voices, (item) => item.id), ['1', '2']);
  assert.equal(parsed.staves.bass[0].voices[1].entries[1].chordSymbol, 'Cm7/G');
});

test('generated SATB answer exports as a lossless two-staff MusicXML document', () => {
  const answerNote = (step, octave) => note(step, octave, { duration: '1', units: 32 });
  const result = {
    summary: { analyzedKey: { label: 'A minor' } },
    fourPart: {
      timeSignature: '4/4',
      voices: [
        { id: 'soprano', measures: [{ entries: [answerNote('E', 5)] }] },
        { id: 'alto', measures: [{ entries: [answerNote('C', 5)] }] },
        { id: 'tenor', measures: [{ entries: [answerNote('A', 3)] }] },
        { id: 'bass', measures: [{ entries: [answerNote('A', 2)] }] }
      ]
    }
  };

  const xml = buildAnswerMusicXml(result);
  assert.equal(isMusicReaderCanonicalXml(xml), true);
  assert.match(xml, /<staves>2<\/staves>/);
  assert.equal((xml.match(/<backup>/g) || []).length, 3);

  const parsed = parseMusicXmlText(xml);
  assert.equal(parsed.staffMode, 'piano');
  assert.equal(parsed.timeSignature, '4/4');
  assert.equal(parsed.keySignature, 'Am');
  assert.deepEqual(Array.from(parsed.staves.treble[0].voices, (item) => item.id), ['1', '2']);
  assert.deepEqual(Array.from(parsed.staves.bass[0].voices, (item) => item.id), ['1', '2']);
  assert.equal(parsed.staves.treble[0].voices[0].entries[0].pitches[0].display, 'E5');
  assert.equal(parsed.staves.treble[0].voices[1].entries[0].pitches[0].display, 'C5');
  assert.equal(parsed.staves.bass[0].voices[0].entries[0].pitches[0].display, 'A3');
  assert.equal(parsed.staves.bass[0].voices[1].entries[0].pitches[0].display, 'A2');
});

test('SATB answer rejects a missing voice before notation or export', () => {
  const answerNote = (step, octave) => note(step, octave, { duration: '1', units: 32 });
  const result = {
    fourPart: {
      timeSignature: '4/4',
      voices: [
        { id: 'soprano', measures: [{ entries: [answerNote('E', 5)] }] },
        { id: 'alto', measures: [{ entries: [answerNote('C', 5)] }] },
        { id: 'bass', measures: [{ entries: [answerNote('A', 2)] }] }
      ]
    }
  };

  assert.equal(answerIntegrityReport(result).valid, false);
  assert.throws(() => buildAnswerMusicXml(result), /声部必须齐全/);
});
